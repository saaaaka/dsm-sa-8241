"""一時的なお試し: 今日の filmarks_weekly.md に新ルールを当てて通知する。"""
import datetime, json, re, sys, time
sys.path.insert(0, ".")
import filmarks as F

F.REPORT_FILE = "filmarks_test.md"
F.REPORT_URL = "https://github.com/saaaaka/dsm-sa-8241/blob/tmp-filmarks-test/filmarks_test.md"
row = re.compile(r'^\| \d+ \| \[(.*)\]\(https://filmarks\.com(/[^)]+)\) \| (\S+) \| (.*?) \| ★([\d.]+) \|$')
seen = json.load(open(F.SEEN_FILE, encoding="utf-8"))["works"]
kept, dropped = {}, []
for line in open("filmarks_weekly.md", encoding="utf-8"):
    m = row.match(line.strip())
    if not m:
        continue
    title, path, kind, svcs, score = m.groups()
    services = [s.strip() for s in svcs.split("/")]
    # 今日の一覧はリンクがずれている作品があるので、タイトルで正しいページを確かめる
    h = F.detail(path)
    t = re.search(r'"@type":"(?:Movie|TVSeason)","title":"([^"]+)"', h)
    if not t or F.norm(t.group(1)) != F.norm(title):
        kind_slug = {"映画": "movies", "ドラマ": "dramas", "アニメ": "animes"}[kind]
        sp = F.get(f"{F.BASE}/search/{kind_slug}?q=" + F.urllib.parse.quote(title))
        hits = [p for p, tt in re.findall(r'data-href="(/(?:movies|dramas|animes)/\d+(?:/\d+)?)".{0,600}?p-content-cassette__title">(.*?)</h3>', sp, re.S)
                if F.norm(F.clean(tt)) == F.norm(title)]
        print("リンク修正:", title, path, "->", hits[:1])
        if hits:
            path = hits[0]
    try:
        c = F.excluded_country(path)
    except Exception as e:
        c = None; print("読めず:", title, e)
    if c:
        dropped.append((title, kind, f"{c}の作品")); print("除外:", title, c); continue
    reason = F.available_elsewhere(path, title, services)
    if reason:
        dropped.append((title, kind, reason)); print("除外:", title, reason); continue
    kept[path] = {"title": title, "kind": kind, "services": services, "score": float(score), "marks": 0}
F.send_report(kept, datetime.date.today().isoformat(), "（お試し4）今週の追加")
with open(F.REPORT_FILE, "a", encoding="utf-8") as fp:
    fp.write(f"\n## 除外した作品（{len(dropped)}）\n\n| 作品 | 種類 | 理由 |\n|---|---|---|\n")
    for t, k, r in dropped:
        fp.write(f"| {t} | {k} | {r} |\n")
print(f"残り {len(kept)} / 除外 {len(dropped)}")
