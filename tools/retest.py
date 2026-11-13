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
    mine = seen.get(path, {}).get("first_seen", "9999")
    if not path.startswith("/movies/"):
        dup = [p for p, w in seen.items() if p != path and not p.startswith("/movies/")
               and F.norm(w["title"]) == F.norm(title) and w.get("first_seen", "") < mine]
        if dup:
            dropped.append((title, kind, "同じタイトルを記録済み")); print("除外(タイトル):", title); continue
    try:
        avail = F.svod_services(path); time.sleep(1)
    except Exception as e:
        avail = None; print("読めず:", title, e)
    if avail is not None and avail - set(services):
        o = " / ".join(sorted(avail - set(services)))
        dropped.append((title, kind, f"{o}で見放題")); print("除外(他サブスク):", title, o); continue
    kept[path] = {"title": title, "kind": kind, "services": services, "score": float(score), "marks": 0}
F.send_report(kept, datetime.date.today().isoformat(), "（お試し）今週の追加")
with open(F.REPORT_FILE, "a", encoding="utf-8") as fp:
    fp.write(f"\n## 除外した作品（{len(dropped)}）\n\n| 作品 | 種類 | 理由 |\n|---|---|---|\n")
    for t, k, r in dropped:
        fp.write(f"| {t} | {k} | {r} |\n")
print(f"残り {len(kept)} / 除外 {len(dropped)}")
