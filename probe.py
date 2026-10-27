import re, urllib.request, html
def get(u,ua):
    try:
        r=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":ua,"Accept":"text/html,application/xhtml+xml","Accept-Language":"ja,en;q=0.8"}),timeout=30)
        return r.status, dict(r.headers), r.read().decode("utf-8","replace")
    except Exception as e:
        return getattr(e,"code",None), dict(getattr(e,"headers",{}) or {}), str(e)
D="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
s,h,b=get("https://www.cibone.com/category/NEW/",D)
links=sorted(set(re.findall(r'https://www\.cibone\.com/category/NEW/[^"]+\.html',b)))
print("CIBONE",len(links),links[:5])
if links:
    i=b.find(links[0].split("/")[-1]); print(b[i-800:i+1500])
for ua in [D,"curl/8.0"]:
    s,h,b=get("https://www.arknets.co.jp/goods/search.aspx?gender=men&goods_type=newarrival&search=x",ua)
    print("\nARK",ua[:20],s,{k:v for k,v in h.items() if k.lower() in("server","x-amzn-waf-action","content-type","set-cookie","x-cache")},len(b),b[:300])
s,h,b=get("https://www.arknets.co.jp/",D); print("\nARKTOP",s,len(b),b[:300])
