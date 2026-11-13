import urllib.request, urllib.parse, re
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
def get(u):
    r=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"ja","Accept":"text/html,*/*"})
    return urllib.request.urlopen(r,timeout=30).read().decode("utf-8","replace")
for kind,q in [("dramas","海に眠るダイヤモンド"),("animes","アイカツ!"),("dramas","GOOD LUCK!!")]:
    u=f"https://filmarks.com/search/{kind}?q="+urllib.parse.quote(q)
    print("===",u)
    try: h=get(u)
    except Exception as e: print("ERR",e); continue
    print(len(h))
    links=re.findall(r'href="(/(?:dramas|animes|movies)/\d+(?:/\d+)?)"',h)
    print(sorted(set(links))[:30])
    for m in list(re.finditer(r'p-content-cassette__title',h))[:8]:
        print(repr(h[m.start()-400:m.start()+200]))
