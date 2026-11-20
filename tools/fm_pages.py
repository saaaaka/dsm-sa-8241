import sys, time, urllib.error
sys.path.insert(0, ".")
import filmarks as F
def n(kind, svc, p):
    try:
        return len(F.parse(F.get(f"{F.BASE}/{kind}/vod/{svc}?page={p}")))
    except urllib.error.HTTPError as e:
        return 0
    finally:
        time.sleep(0.5)
tot = 0
t0 = time.time()
for kind in F.KINDS:
    for svc in F.SERVICES:
        lo, hi = 1, 2
        while n(kind, svc, hi) > 0 and hi < 20000:
            lo, hi = hi, hi * 2
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if n(kind, svc, mid) > 0: lo = mid
            else: hi = mid
        print(kind, svc, "最終ページ", lo, "見放題率(最終頁)", flush=True)
        tot += lo
print("合計ページ", tot, "計測", round(time.time() - t0), "秒")
t1 = time.time()
for p in range(1, 6): n("list", "unext", p)
print("1ページあたり", round((time.time() - t1) / 5, 2), "秒（待ち0.5秒込み）")
