import re, urllib.request, html
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
def get(u):
    r=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"ja"})
    return urllib.request.urlopen(r,timeout=30).read().decode("utf-8","replace")
def txt(s): return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",s)))
for u in ["https://filmarks.com/list-drama/vod/unext","https://filmarks.com/list-anime/vod/unext"]:
    p=get(u); print("=====",u)
    print(sorted(set(re.findall(r'href="([^"]*(?:order|sort|vod/unext\?)[^"]*)"',p)))[:40])
    for m in re.finditer(r'(並び|順)',p):
        print("  ..",txt(p[max(0,m.start()-200):m.start()+100])[-160:])
        break
    i=p.find('p-content-cassette'); print("CARD:",txt(p[i:i+2500])[:600])
for u in ["/dramas/11621/24726","/dramas/5784/8256","/dramas/5784/12539","/animes/1326/1766","/animes/1326/3629","/movies/122653","/dramas/6934/9948"]:
    p=get("https://filmarks.com"+u); print("=====",u)
    for k in ['datePublished','dateCreated','startDate','"releasedEvent"','放送','配信開始','製作の','上映日','公開']:
        for m in list(re.finditer(re.escape(k),p))[:2]:
            print(f"  [{k}]",txt(p[max(0,m.start()-120):m.start()+160]))
    print("  SEASONS:",sorted(set(re.findall(r'href="(/(?:dramas|animes)/\d+/\d+)"',p)))[:20])
    vb=re.findall(r'c2-list-vod-detail[^>]*data-gtm-info="([^"]+)"(.{0,800}?)</a>',p,re.S)
    for n,b in vb[:8]: print("  VOD",n,txt(b)[:150])
