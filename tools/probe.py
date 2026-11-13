import sys, re; sys.path.insert(0,".")
import filmarks as F
for pg in range(1,11):
    h=F.get(f"{F.BASE}/list/vod/netflix"+(f"?page={pg}" if pg>1 else ""))
    for c in F.chunks(h):
        if "モノノ怪" in c or "ゴジラ" in c:
            print("page",pg, F.WORK_LINK.findall(c)[:6], re.findall(r'data-href="([^"]+)"',c)[:3], (F.TITLE.search(c) or F.IMG_ALT.search(c)).group(1)[:40])
