import sys, re; sys.path.insert(0,".")
import filmarks as F
for p in ["/dramas/14697/20006","/dramas/11241/15608","/dramas/17312/23273","/movies/131637","/dramas/12296/16971"]:
    h=F.detail(p)
    t=re.search(r'"title":"([^"]+)"',h)
    print("===",p,t and t.group(1))
    print([m.group(0)[:200] for m in re.finditer(r'"countries":\s*(\[[^\]]*\]|"[^"]*")',h)])
    print(re.findall(r'"position":2,"item":\{"@id":"([^"]+)","name":"([^"]+)"',h))
    m=re.search(r'製作国・地域：</h3>(.{0,300})',h); print(m and re.sub(r"<[^>]+>"," ",m.group(1))[:150])
