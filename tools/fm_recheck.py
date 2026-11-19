"""一時: 11/19 の通知（filmarks_weekly.md）を新しい条件で選び直して再通知する。"""
import re, sys, datetime
sys.path.insert(0, ".")
import filmarks as F
rows = [l for l in open(F.REPORT_FILE, encoding="utf-8") if re.match(r"\| \d", l)]
keep = {}
for l in rows:
    c = [x.strip() for x in l.strip().strip("|").split("|")]
    m = re.match(r"\[(.*)\]\(https://filmarks\.com(/[^)]+)\)", c[1])
    title, path, kind = m.group(1), m.group(2), c[2]
    services = [x.strip() for x in c[3].split("/")]
    score = float(c[4].lstrip("★"))
    if len(services) > 1:
        print("複数:", title); continue
    try:
        rel = F.release_date(path)
    except Exception as e:
        rel = None; print("読めず:", title, e)
    if rel and (datetime.date.today() - rel).days > F.RECENT_DAYS[kind]:
        print("古い:", title, rel); continue
    r = F.available_elsewhere(path, title, services)
    if r:
        print("他で見放題:", title, r); continue
    keep[path] = {"title": title, "kind": kind, "services": services, "score": score, "marks": 0}
    print("残す:", title, rel)
F.send_report(keep, datetime.date.today().isoformat(), "【修正版】前回からの追加")
print(len(rows), "→", len(keep))
