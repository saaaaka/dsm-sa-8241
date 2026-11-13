import urllib.request, urllib.parse, re
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
def get(u):
    r=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"ja","Accept":"text/html,*/*"})
    return urllib.request.urlopen(r,timeout=30).read().decode("utf-8","replace")
for p in ["/dramas/10059/14109","/dramas/6086/8629","/dramas/16371/22062","/movies/16327","/movies/5711","/animes/1453/1928"]:
    print("===",p)
    h=get("https://filmarks.com"+p)
    for m in list(re.finditer(r'country|製作国|国・地域', h))[:6]:
        print(repr(h[max(0,m.start()-200):m.start()+300]))
    print(sorted(set(re.findall(r'href="(/list[^"]*/country/[^"]+)"',h))))
s=get("https://filmarks.com/search/movies?q="+urllib.parse.quote("パラサイト 半地下の家族"))
m=re.search(r'data-href="(/movies/\d+)"',s); print("parasite",m and m.group(1))
if m:
    h=get("https://filmarks.com"+m.group(1)); print(sorted(set(re.findall(r'href="(/list[^"]*/country/[^"]+)"',h))))
