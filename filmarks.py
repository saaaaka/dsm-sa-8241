"""Filmarks の「動画配信サービス別」一覧を確認し、
契約中のサブスクに新しく入った高評価作品（スコア4.0以上）を ntfy で通知する。

仕組み:
  Filmarks の配信サービス別一覧（おすすめ順）の上位ページを読み、
  「見放題」の作品のうち、まだ一度も見たことのない作品でスコアが MIN_SCORE 以上なら通知する。
  （レンタル・購入のみの作品は対象外。レンタルから見放題に変わった作品は新着として扱う）
  初回は「今ある作品」を記録するだけで通知しない（大量通知を防ぐため）。

サブスクを増やす／減らすときは SERVICES を編集する。
  Filmarks の URL の slug: prime_video / netflix / unext / disneyplus / hulu
  / dmmtv / fod / telasa / lemino / abema / wowow など
"""
import datetime
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

SERVICES = {
    "prime_video": "Prime Video",
    "netflix": "Netflix",
    "unext": "U-NEXT",
    "disneyplus": "ディズニープラス",
}
KINDS = {
    "list": "映画",
    "list-drama": "ドラマ",
    "list-anime": "アニメ",
}
MIN_SCORE = 4.0
PAGES = 10            # 各一覧の何ページ目まで見るか（おすすめ順の上位）
MAX_PUSH = 8          # 1回の実行で個別に通知する上限（超えた分はまとめて1通）

BASE = "https://filmarks.com"
SEEN_FILE = "filmarks_seen.json"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()

WORK_LINK = re.compile(r'href="(?:https://filmarks\.com)?(/(?:movies|dramas|animes)/\d+(?:/\d+)?)(?:\?[^"]*)?"')
SCORE = re.compile(r'c-rating__score[^>]*>\s*([0-9]\.[0-9]|-)')
TITLE = re.compile(r'p-content-cassette__title[^>]*>(.*?)</h3>', re.S)
IMG_ALT = re.compile(r'<img[^>]*alt="([^"]+)"')


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "ja",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def chunks(page):
    """1作品ぶんずつのHTMLに分ける。"""
    parts = re.split(r'class="p-content-cassette(?=[\s"])', page)
    if len(parts) > 3:
        return parts[1:]
    # 予備: 作品リンクの出現位置で区切る
    pos, done = [], set()
    for m in WORK_LINK.finditer(page):
        if m.group(1) not in done:
            done.add(m.group(1))
            pos.append(m.start())
    return [page[a:b] for a, b in zip(pos, pos[1:] + [len(page)])]


def parse(page):
    items = []
    for c in chunks(page):
        link = WORK_LINK.search(c)
        score = SCORE.search(c)
        if not link or not score:
            continue
        t = TITLE.search(c) or IMG_ALT.search(c)
        title = clean(t.group(1)) if t else link.group(1)
        s = score.group(1)
        items.append({"path": link.group(1), "title": title,
                      "score": float(s) if s != "-" else None,
                      # 見放題（サブスクで観られる）かどうか。レンタル・購入のみは対象外
                      "svod": "label-svod" in c})
    return items


def notify(title, body, click):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC未設定のため通知スキップ:", title, body)
        return
    payload = {"topic": NTFY_TOPIC, "title": title, "message": body,
               "click": click, "priority": 3, "tags": ["movie_camera"]}
    req = urllib.request.Request(
        "https://ntfy.sh/",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=30)


def main():
    first_run = not os.path.exists(SEEN_FILE)
    state = {"works": {}, "lists": []} if first_run else json.load(open(SEEN_FILE, encoding="utf-8"))
    seen, known_lists = state["works"], set(state["lists"])
    today = datetime.date.today().isoformat()

    found = {}   # path -> {title, score, kind, services, notifiable}
    errors = []
    ok_lists = set()
    for kind_slug, kind_name in KINDS.items():
        for svc_slug, svc_name in SERVICES.items():
            list_id = f"{kind_slug}/{svc_slug}"
            # 初めて読む一覧（サブスク追加時など）は記録だけして通知しない
            notifiable = list_id in known_lists
            for p in range(1, PAGES + 1):
                url = f"{BASE}/{kind_slug}/vod/{svc_slug}" + (f"?page={p}" if p > 1 else "")
                try:
                    items = parse(get(url))
                except urllib.error.HTTPError as e:
                    if e.code != 404 or p == 1:   # 404 = 最終ページを過ぎただけ
                        errors.append(f"{kind_name}/{svc_name} p{p}: {e}")
                    break
                except Exception as e:
                    errors.append(f"{kind_name}/{svc_name} p{p}: {e}")
                    break
                if p == 1 and len(items) < 5:
                    errors.append(f"{kind_name}/{svc_name}: 作品を読み取れませんでした（{len(items)}件）")
                    break
                for it in items:
                    if not it["svod"]:
                        continue
                    f = found.setdefault(it["path"], {**it, "kind": kind_name, "services": [],
                                                      "notifiable": False})
                    if svc_name not in f["services"]:
                        f["services"].append(svc_name)
                    f["notifiable"] = f["notifiable"] or notifiable
                if p == 1:
                    ok_lists.add(list_id)
                print(f"{kind_name}/{svc_name} p{p}: {len(items)}件")
                if not items:
                    break
                time.sleep(1)

    if not found:
        print("エラー:\n" + "\n".join(errors))
        sys.exit(1)

    new_hits = []
    for path, f in found.items():
        if path in seen:
            continue
        seen[path] = {"title": f["title"], "first_seen": today}
        if f["notifiable"] and f["score"] is not None and f["score"] >= MIN_SCORE:
            new_hits.append(f)

    if first_run:
        print(f"初回: {len(found)}件を記録（通知なし）")
        notify("Filmarks監視を開始しました",
               f"{len(found)}作品を記録しました。次回から新しく入った★{MIN_SCORE}以上の作品を通知します。",
               BASE)
    else:
        new_hits.sort(key=lambda f: -f["score"])
        for f in new_hits[:MAX_PUSH]:
            notify(f"★{f['score']} {f['title']}",
                   f"{f['kind']}｜{' / '.join(f['services'])}",
                   BASE + f["path"])
        rest = new_hits[MAX_PUSH:]
        if rest:
            notify(f"ほかに{len(rest)}作品",
                   "\n".join(f"★{f['score']} {f['title']}（{' / '.join(f['services'])}）" for f in rest),
                   BASE)
        print(f"新着の高評価: {len(new_hits)}件")

    if errors:
        print("エラー:\n" + "\n".join(errors))

    state["lists"] = sorted(known_lists | ok_lists)
    with open(SEEN_FILE, "w", encoding="utf-8") as fp:
        json.dump(state, fp, ensure_ascii=False, indent=0, sort_keys=True)

    if errors and not found:
        sys.exit(1)


if __name__ == "__main__":
    main()
