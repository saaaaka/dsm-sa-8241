import re, urllib.request
from collections import Counter
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
u="https://the-tokyo.jp/shop/e/eTT-M-N-A_ssd/?f12=0"
try:
    r=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"ja"}),timeout=30)
    s,h,b=r.status,dict(r.headers),r.read().decode("utf-8","replace")
except Exception as e:
    s,h,b=getattr(e,"code",None),dict(getattr(e,"headers",{}) or {}),str(e)
print(s,{k:v for k,v in h.items() if k.lower() in("server","x-amzn-waf-action","content-type")},len(b))
print(re.findall(r"<title>(.*?)</title>",b,re.S)[:1])
links=re.findall(r'href="([^"]+)"',b)
print(Counter(re.sub(r"[0-9A-Za-z_\-]{4,}","X",l.split("?")[0]) for l in links).most_common(15))
g=[l for l in links if "/shop/g/" in l]
print("GOODS",len(set(g)),list(dict.fromkeys(g))[:6])
if g:
    i=b.find(g[0]); print(b[i-600:i+2200])
