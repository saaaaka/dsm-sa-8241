"""【方式】通知する日（3日に1回 18時）に、各サブスクの見放題作品を全ページ読んで
前回の記録（filmarks_catalog.json）と比べ、新しく見られるようになった作品だけを通知する。
古い作品でも「今まで契約中のどのサブスクでも見られなかった」なら通知する。
ドラマ・アニメの最新話追加はページが増えないので通知されない。新シーズンは別ページなので通知される。
（以下は旧方式の説明を含む）

Filmarks の「動画配信サービス別」一覧を確認し、
契約中のサブスクに新しく入った高評価作品（スコア3.8以上）を3日に1回まとめて通知する。

  毎日: 一覧をチェックして、新しく見つけた作品を「前回からの追加」にためる（通知しない）
  3日に1回 18時（REPORT=1）: たまった作品をスコア順のランキングにして
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
MIN_SCORE = 3.8
MIN_MARKS = 20      # 評価件数（Mark数）がこれ未満の作品は通知しない（件数が少ないとスコアが不安定なため）
WAIT_DAYS = 90      # 件数不足の作品は、この日数のあいだ毎回見直し、基準の件数に届いたら通知する
# 新しさの判定（Filmarks には「配信開始日」がないため、公開日で代用する）
#   ドラマ・アニメ: そのシーズンの開始日がこの日数以内なら「新シーズン」として通知。
#     古いシーズンが一覧に浮上しただけのもの・放送中の最新話追加は通知しない
#   映画: 公開（上映）日がこの日数以内のものだけ通知
RECENT_DAYS = {"映画": 730, "ドラマ": 180, "アニメ": 180}
EXCLUDE_COUNTRIES = ["韓国"]   # この国の作品は通知しない（ドラマ・映画）
PAGES = 10            # 各一覧の何ページ目まで見るか（おすすめ順の上位）
MAX_LINES = 15        # 通知本文に載せる件数（全件は filmarks_weekly.md で見る）
# 作品ページの確認に使う時間の上限（分）。超えた分は記録せず次回に回す
# （新着が大量にたまってもタイムアウトで何も保存されない、を防ぐ）
CHECK_MINUTES = 25
START = time.time()

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


RELEASE_LD = re.compile(r'"releaseDate":"(\d{4})-(\d{2})-(\d{2})')
RELEASE_TXT = re.compile(r'(?:上映日|公開日?|放送開始)[：:]?\s*(\d{4})年(\d{1,2})月(\d{1,2})日|(\d{4})年(\d{1,2})月(\d{1,2})日(?:公開|放送|配信)')


def ymd(m):
    g = [x for x in m.groups() if x]
    return datetime.date(int(g[0]), int(g[1]), int(g[2]))


def release_date(path):
    """作品ページから公開日（ドラマ・アニメはそのシーズンの開始日）を返す。"""
    page = detail(path)
    m = RELEASE_LD.search(page) or RELEASE_TXT.search(re.sub(r"<[^>]+>", " ", page))
    if m:
        return ymd(m)
    m = re.search(r'"startDate":"(\d{4})-(\d{2})-(\d{2})', page)   # シリーズの開始日
    if m:
        return ymd(m)
    m = re.search(r'(\d{4})年製作', page)                            # 製作年（年末扱い）
    return datetime.date(int(m.group(1)), 12, 31) if m else None


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
        if p == path and len(services) > 1:
            return " / ".join(sorted(services)) + "の複数で見放題"
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
        rd = RELEASE_TXT.search(re.sub(r"<[^>]+>", " ", c))
        items.append({"path": link.group(1), "title": title,
                      "marks": int(mk.group(1)) if mk else 0,
                      "score": float(s) if s != "-" else None,
                      "released": ymd(rd).isoformat() if rd else None,
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


def country_text(p):
    return "・".join(p.get("countries") or []) or "不明"


def send_report(pending, today, label="前回からの追加"):
    ranked = sorted(pending.items(), key=lambda kv: (-kv[1]["score"], -kv[1]["marks"]))
    lines = [f"# Filmarks {label}（{today}）", "",
             f"契約中のサブスクで見放題になった、スコア{MIN_SCORE}以上・評価{MIN_MARKS}件以上の作品です（スコア順）。", ""]
    if ranked:
        lines += ["| 順位 | 作品 | 種類 | 作成国 | 配信 | スコア | 評価件数 |",
                  "|---:|---|---|---|---|---:|---:|"]
        for i, (path, p) in enumerate(ranked, 1):
            t = p["title"].replace("|", "｜")
            lines.append(f"| {i} | [{t}]({BASE}{path}) | {p['kind']} | {country_text(p)} | "
                         f"{' / '.join(p['services'])} | ★{p['score']} | {p.get('marks', 0):,}件 |")
    else:
        lines.append("前回の通知から、該当する作品はありませんでした。")
    with open(REPORT_FILE, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")

    if ranked:
        body = "\n".join(f"{i}. ★{p['score']}（{p.get('marks', 0):,}件） {p['title']}"
                         f"（{p['kind']}｜{country_text(p)}｜{' / '.join(p['services'])}）"
                         for i, (_, p) in enumerate(ranked[:MAX_LINES], 1))
        if len(ranked) > MAX_LINES:
            body += f"\n…ほか{len(ranked) - MAX_LINES}作品（タップで全件）"
        notify(f"{label} {len(ranked)}作品", body, REPORT_URL)
    else:
        notify(f"{label} 0作品", f"スコア{MIN_SCORE}以上の新着はありませんでした。", REPORT_URL)


CATALOG_FILE = "filmarks_catalog.json"
WORKERS = 4          # 同時に読む一覧の数
MAX_PAGES = 3000     # 念のための上限


def crawl(kind_slug, svc_slug):
    """1つの一覧を最終ページまで読み、見放題作品を返す。(items, 読めなかったページ数)"""
    items, failed, p = [], 0, 1
    while p <= MAX_PAGES:
        url = f"{BASE}/{kind_slug}/vod/{svc_slug}" + (f"?page={p}" if p > 1 else "")
        page = None
        for attempt in range(3):
            try:
                page = parse(get(url))
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    page = []
                    break
                time.sleep(5)
            except Exception:
                time.sleep(5)
        if page is None:
            failed += 1
            if failed > 20:
                break
            p += 1
            continue
        if not page:
            break
        items += [it for it in page if it["svod"]]
        p += 1
        time.sleep(0.5)
    print(f"{kind_slug}/{svc_slug}: {p - 1}ページ, 見放題{len(items)}件, 失敗{failed}ページ", flush=True)
    return items, failed


def load_catalog():
    if os.path.exists(CATALOG_FILE):
        return json.load(open(CATALOG_FILE, encoding="utf-8"))
    cat = {"lists": {}, "titles": {}}
    # 旧方式の記録（filmarks_seen.json）も「既知」として取り込む
    if os.path.exists(SEEN_FILE):
        old = json.load(open(SEEN_FILE, encoding="utf-8"))
        kind_of = {"movies": "list", "dramas": "list-drama", "animes": "list-anime"}
        slug_of = {v: k for k, v in SERVICES.items()}
        for path, w in old.get("works", {}).items():
            k = kind_of.get(path.split("/")[1])
            for name in w.get("services", []):
                if k and name in slug_of:
                    cat["lists"].setdefault(f"{k}/{slug_of[name]}", []).append(path)
            cat["titles"][path] = w.get("title", "")
        # 旧方式で一部しか読んでいない一覧は「未完成」扱い（初回は通知しない）
        cat["partial"] = True
    return cat


def main():
    from concurrent.futures import ThreadPoolExecutor
    today = datetime.date.today().isoformat()
    cat = load_catalog()
    building = cat.pop("partial", False) or not cat["lists"]
    known = {lid: set(v) for lid, v in cat["lists"].items()}
    titles = cat["titles"]
    waiting = cat.get("waiting", {})   # 件数不足で保留中の作品 path -> 初めて見つけた日
    new_waiting = {}
    # 保留中の作品自身のタイトルは「記録済み」に数えない
    known_titles = {norm(t) for pth, t in titles.items()
                    if not pth.startswith("/movies/") and pth not in waiting}
    # 以前から契約中サブスクのどれかで見られた作品（＝新着ではない）
    known_any = set().union(*known.values()) if known else set()

    jobs = [(k, s) for k in KINDS for s in SERVICES]
    with ThreadPoolExecutor(WORKERS) as ex:
        results = dict(zip(jobs, ex.map(lambda j: crawl(*j), jobs)))

    found = {}     # path -> 作品情報（今回の全一覧）
    complete = set()
    for (k, sv), (items, failed) in results.items():
        lid = f"{k}/{sv}"
        if items and failed == 0:
            complete.add(lid)
        for it in items:
            f = found.setdefault(it["path"], {**it, "kind": KINDS[k], "services": [], "lists": []})
            if SERVICES[sv] not in f["services"]:
                f["services"].append(SERVICES[sv])
            f["lists"].append(lid)

    if not found:
        print("エラー: 一覧を読めませんでした")
        sys.exit(1)

    hits = {}
    if not building:
        for path, f in found.items():
            if path in known_any and path not in waiting:
                continue      # 前から契約中のどこかで見られた
            new_lists = [l for l in f["lists"] if l in known]   # 前回も読めた一覧で初登場
            if not new_lists:
                continue
            if f["score"] is None or f["score"] < MIN_SCORE:
                continue
            if f["marks"] < MIN_MARKS:
                first = waiting.get(path, today)
                if (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(first)).days < WAIT_DAYS:
                    new_waiting[path] = first     # スコアが基準以上なら、次回また見直す
                print("評価件数が少ないので保留:", f["title"], f["marks"])
                continue
            if len(f["services"]) > 1:
                print("複数の契約中サブスクで見放題なので対象外:", f["title"], f["services"])
                continue
            if not path.startswith("/movies/") and norm(f["title"]) in known_titles:
                print("同じタイトルを記録済みなので対象外:", f["title"])
                continue
            try:
                cs = countries(path)
            except Exception as e:
                cs = set()
                print("作品ページを読めませんでした:", f["title"], e)
            c = next((x for x in cs for ex in EXCLUDE_COUNTRIES if ex in x), None)
            if c:
                print("除外する国の作品なので対象外:", f["title"], c)
                continue
            reason = available_elsewhere(path, f["title"], f["services"])
            if reason:
                print("他の契約中サブスクで見放題なので対象外:", f["title"], reason)
                continue
            hits[path] = {k2: f[k2] for k2 in ("title", "kind", "services", "score", "marks")}
            hits[path]["countries"] = sorted(cs)
            print("新着:", f["title"], f["score"], f["services"])

    # 記録を更新（一度見られた作品は残し続ける：読み漏れで誤って新着扱いしないため）
    for path, f in found.items():
        titles[path] = f["title"]
        for l in f["lists"]:
            known.setdefault(l, set()).add(path)
    cat = {"lists": {l: sorted(v) for l, v in known.items()}, "titles": titles,
           "waiting": new_waiting}
    if building:
        print(f"初回: {len(found)}件を記録（通知なし）")
        notify("Filmarks 新着通知の準備完了",
               f"見放題作品{len(found)}件を記録しました。次回から新しく見られるようになった作品を通知します。",
               REPORT_URL)
    elif REPORT:
        send_report(hits, today)
    print(f"新着: {len(hits)}件 / 読めた一覧 {len(complete)}/{len(jobs)}")
    with open(CATALOG_FILE, "w", encoding="utf-8") as fp:
        json.dump(cat, fp, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


if __name__ == "__main__":
    main()
