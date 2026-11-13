import sys, re; sys.path.insert(0,".")
import filmarks as F
bad=0; n=0
for url in [f"{F.BASE}/list/vod/netflix?page=9", f"{F.BASE}/list-drama/vod/unext?page=3", f"{F.BASE}/list-anime/vod/prime_video"]:
    for it in F.parse(F.get(url))[:8]:
        h=F.detail(it["path"]); t=re.search(r'"@type":"(?:Movie|TVSeason)","title":"([^"]+)"',h)
        real=t.group(1) if t else "?"; n+=1
        ok=F.norm(real)==F.norm(it["title"]); bad+= not ok
        print("OK " if ok else "NG ", it["path"], it["title"][:25], "|", real[:25])
print("mismatch",bad,"/",n)
