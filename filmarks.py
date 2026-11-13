"""Filmarks の「動画配信サービス別」一覧を確認し、
契約中のサブスクに新しく入った高評価作品（スコア3.9以上）を週1回まとめて通知する。

  毎日: 一覧をチェックして、新しく見つけた作品を「今週の追加」にためる（通知しない）
  金曜11時30分（REPORT=1）: たまった作品をスコア順のランキングにして
        filmarks_weekly.md に書き出し、ntfy で1通だけ通知する

仕組み:
  Filmarks の配信サービス別一覧（おすすめ順）の上位ページを読み、
  「見放題」の作品のうち、まだ一度も見たことのない作品でスコアが MIN_SCORE 以上なら通知する。
  （レンタル・購入のみの作品は対象外。レンタルから見放題に変わった作品は新着として扱う）
  初回は「今ある作品」を記録するだけで通知しない（大量通知を防ぐため）。
  すでに他の契約中サブスクで見放題だった作品は通知しない:
    ・作品ページの配信情報を見て、新しく入ったサービス以外の契約中サブスクでも
      見放題なら対象外
    ・ドラマ・アニメは、同じタイトルを別ページで記録済みなら対象外
      （Filmarks はサービスごとに別ページを作ることがあるため）
    ・韓国のドラマ・映画は通知しない（EXCLUDE_COUNTRIES）
    ・さらにドラマ・アニメは Filmarks の検索で同じタイトルの別ページを探し、
      そちらで他の契約中サブスクが見放題なら対象外

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
import urllib.parse
import urllib.error
import urllib.request

SERVICES = {
    "prime_video": "Prime Video",
    "netflix": "Netflix",
    "unext": "U-NEXT",
    "disneyplus": "ディズニープラス",
}
# 作品ページでの表記ゆれ（表示名 -> 作品ページに出る名前）
SERVICE_ALIASES = {
    "Prime Video": ["Prime Video", "Amazon Prime Video", "プライムビデオ"],
    "Netflix": ["Netflix"],
    "U-NEXT": ["U-NEXT"],
    "ディズニープラス": ["ディズニープラス", "Disney+", "Disney Plus"],
}
KINDS = {
    "list": "映画",
    "list-drama": "ドラマ",
    "list-anime": "アニメ",
}
MIN_SCORE = 3.9
EXCLUDE_COUNTRIES = ["韓国"]   # この国の作品は通知しない（ドラマ・映画）
PAGES = 10            # 各一覧の何ページ目まで見るか（おすすめ順の上位）
MAX_LINES = 15        # 通知本文に載せる件数（全件は filmarks_weekly.md で見る）

BASE = "https://filmarks.com"
SEEN_FILE = "filmarks_seen.json"
REPORT_FILE = "filmarks_weekly.md"
REPORT_URL = "https://github.com/saaaaka/dsm-sa-8241/blob/main/filmarks_weekly.md"
REPORT = os.environ.get("REPORT", "") == "1"
# SAMPLE=1: 見た目確認用。各一覧の1ページ目にある★基準以上の作品でランキングを作る（記録は変えない）
SAMPLE = os.environ.get("SAMPLE", "") == "1"
if SAMPLE:
    PAGES = 1
    REPORT_FILE = "filmarks_sample.md"
    REPORT_URL = REPORT_URL.replace("filmarks_weekly.md", REPORT_FILE)
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()

WORK_LINK = re.compile(r'href="(?:https://filmarks\.com)?(/(?:movies|dramas|animes)/\d+(?:/\d+)?)(?:\?[^"]*)?"')
SCORE = re.compile(r'c-rating__score[^>]*>\s*([0-9]\.[0-9]|-)')
TITLE = re.compile(r'p-content-cassette__title[^>]*>(.*?)</h3>', re.S)
IMG_ALT = re.compile(r'<img[^>]*alt="([^"]+)"')
MARKS = re.compile(r'action--mark[^>]*>\s*<span>(\d+)')
VOD_BLOCK = re.compile(r'<a[^>]*class="c2-list-vod-detail[^"]*"[^>]*data-gtm-info="([^"]+)"(.*?)</a>', re.S)


def norm(s):
    return re.sub(r"[\s　・:：!！?？+＋\-－~～()（）「」『』]", "", s).lower()


ALIAS_TO_SERVICE = {norm(a): name for name, al in SERVICE_ALIASES.items() for a in al}


_pages = {}


def detail(path):
    if path not in _pages:
        _pages[path] = get(BASE + path)
        time.sleep(1)
    return _pages[path]


def countries(path):
    """作品ページの製作国・地域（JSON-LD の countryOfOrigin とパンくず）を返す。"""
    page = detail(path)
    found = set()
    for m in re.finditer(r'"countries":\s*(\[[^\]]*\]|"[^"]*")', page):
        v = m.group(1)
        if v != '"countryOfOrigin"':   # JSON-LD の @context 部分は飛ばす
            found |= set(re.findall(r'"name":"([^"]+)"', v)) or set(re.findall(r'"([^"]+)"', v))
    m = re.search(r'"position":2,"item":\{"@id":"https://filmarks\.com/list[^/]*/country/\d+","name":"([^"]+)"', page)
    if m:
        found.add(re.sub(r"(映画|ドラマ|アニメ)$", "", m.group(1)))
    return found


def excluded_country(path):
    hit = [c for c in countries(path) for x in EXCLUDE_COUNTRIES if x in c]
    return hit[0] if hit else None


def svod_services(path):
    """作品ページから、契約中サブスクのうち見放題で配信しているサービス名を返す。
    読めなかったときは None。"""
    page = detail(path)
    blocks = VOD_BLOCK.findall(page)
    if not blocks:
        return None
    return {ALIAS_TO_SERVICE[norm(name)] for name, body in blocks
            if "c2-tag-svod" in body and norm(name) in ALIAS_TO_SERVICE}


SEARCH_HIT = re.compile(r'data-href="(/(?:dramas|animes)/\d+/\d+)".{0,600}?p-content-cassette__title">(.*?)</h3>', re.S)


def same_title_pages(path, title):
    """ドラマ・アニメで、同じタイトルの別ページを Filmarks の検索から探す。"""
    kind = path.split("/")[1]
    page = get(f"{BASE}/search/{kind}?q=" + urllib.parse.quote(title))
    key = norm(title)
    out = []
    for p, t in SEARCH_HIT.findall(page):
        if p != path and p not in out and norm(clean(t)) == key:
            out.append(p)
    return out[:5]


def available_elsewhere(path, title, services):
    """新しく入ったサービス（services）以外の契約中サブスクで、すでに見放題なら
    その理由を返す。そうでなければ None。読めないところは飛ばす。"""
    pages = [path]
    if not path.startswith("/movies/"):
        try:
            pages += same_title_pages(path, title)
        except Exception as e:
            print("検索を読めませんでした:", title, e)
    for p in pages:
        try:
            avail = svod_services(p)
        except Exception as e:
            print("作品ページを読めませんでした:", title, p, e)
            continue
        others = (avail or set()) - set(services)
        if others:
            where = "" if p == path else "（別ページ）"
            return " / ".join(sorted(others)) + "で見放題" + where
    return None


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "ja",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


DATA_HREF = re.compile(r'data-href="(/(?:movies|dramas|animes)/\d+(?:/\d+)?)(?:\?[^"]*)?"')


def chunks(page):
    """1作品ぶんずつのHTMLに分ける。
    作品のリンク（data-href）はカードの直前にあるので、前のかたまりの最後の data-href を
    その作品のリンクとして先頭に付けておく（隣の作品のリンクを拾わないため）。"""
    parts = re.split(r'class="p-content-cassette(?=[\s"])', page)
    if len(parts) > 3:
        out = []
        for prev, c in zip(parts, parts[1:]):
            own = DATA_HREF.findall(prev)
            out.append((f'<a href="{own[-1]}"></a>' if own else "") + c)
        return out
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
        mk = MARKS.search(c)
        items.append({"path": link.group(1), "title": title,
                      "marks": int(mk.group(1)) if mk else 0,
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


def send_report(pending, today, label="今週の追加"):
    ranked = sorted(pending.items(), key=lambda kv: (-kv[1]["score"], -kv[1]["marks"]))
    lines = [f"# Filmarks {label}（{today}）", "",
             f"契約中のサブスクで見放題になった、スコア{MIN_SCORE}以上の作品です（スコア順）。", ""]
    if ranked:
        lines += ["| 順位 | 作品 | 種類 | 配信 | スコア |", "|---:|---|---|---|---:|"]
        for i, (path, p) in enumerate(ranked, 1):
            t = p["title"].replace("|", "｜")
            lines.append(f"| {i} | [{t}]({BASE}{path}) | {p['kind']} | {' / '.join(p['services'])} | ★{p['score']} |")
    else:
        lines.append("今週は該当する作品はありませんでした。")
    with open(REPORT_FILE, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")

    if ranked:
        body = "\n".join(f"{i}. ★{p['score']} {p['title']}（{p['kind']}｜{' / '.join(p['services'])}）"
                         for i, (_, p) in enumerate(ranked[:MAX_LINES], 1))
        if len(ranked) > MAX_LINES:
            body += f"\n…ほか{len(ranked) - MAX_LINES}作品（タップで全件）"
        notify(f"{label} {len(ranked)}作品", body, REPORT_URL)
    else:
        notify("今週の追加 0作品", f"スコア{MIN_SCORE}以上の新着はありませんでした。", REPORT_URL)


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

    if SAMPLE:
        hits = {p: f for p, f in found.items() if f["score"] is not None and f["score"] >= MIN_SCORE}
        send_report(hits, today, "（サンプル）今週の追加")
        print(f"サンプル: {len(hits)}件")
        return

    pending = state.setdefault("pending", {})
    # ドラマ・アニメは同じ作品がサービスごとに別ページになっていることがあるので、タイトルでも照合
    known_titles = {norm(w["title"]) for p, w in seen.items() if not p.startswith("/movies/")}
    for path, f in found.items():
        if path in seen:
            continue
        seen[path] = {"title": f["title"], "first_seen": today, "services": f["services"]}
        if f["notifiable"] and f["score"] is not None and f["score"] >= MIN_SCORE:
            if not path.startswith("/movies/") and norm(f["title"]) in known_titles:
                print("記録済みの作品なので対象外:", f["title"])
                continue
            try:
                c = excluded_country(path)
            except Exception as e:
                c = None
                print("作品ページを読めませんでした:", f["title"], e)
            if c:
                print("除外する国の作品なので対象外:", f["title"], c)
                continue
            reason = available_elsewhere(path, f["title"], f["services"])
            if reason:
                print("他の契約中サブスクで見放題なので対象外:", f["title"], reason)
                continue
            pending[path] = {k: f[k] for k in ("title", "kind", "services", "score", "marks")}
            pending[path]["added"] = today
            print("今週の追加に記録:", f["title"], f["score"])
    # ためている作品のスコア・配信先を最新に
    for path, p in pending.items():
        if path in found:
            f = found[path]
            p.update(score=f["score"] or p["score"], marks=f["marks"] or p["marks"],
                     services=sorted(set(p["services"]) | set(f["services"])))

    if first_run:
        print(f"初回: {len(found)}件を記録（通知なし）")
    elif REPORT:
        send_report(pending, today)
        state["pending"] = {}
    print(f"今週の追加（未通知）: {len(state['pending'])}件")

    if errors:
        print("エラー:\n" + "\n".join(errors))

    state["lists"] = sorted(known_lists | ok_lists)
    with open(SEEN_FILE, "w", encoding="utf-8") as fp:
        json.dump(state, fp, ensure_ascii=False, indent=0, sort_keys=True)

    if errors and not found:
        sys.exit(1)


if __name__ == "__main__":
    main()
