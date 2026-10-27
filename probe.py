import re, json, urllib.request, sys
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
def get(u):
    try:
        r=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"ja"}),timeout=30)
        return r.status, r.geturl(), r.read().decode("utf-8","replace")
    except Exception as e:
        return getattr(e,"code",None), u, str(e)
urls=["https://www.neighborhood.jp/","https://www.neighborhood.jp/products.json?limit=3",
"https://www.cibone.com/category/NEW/","https://www.cibone.com/products.json?limit=3",
"https://www.arknets.co.jp/goods/search.aspx?gender=men&goods_type=newarrival&search=x"]
for u in urls:
    s,f,b=get(u)
    print("\n=====",u,"->",s,f,"len",len(b))
    print("shopify" if "cdn.shopify" in b or "Shopify." in b else "not-shopify-marker")
    print("TITLE",re.findall(r"<title>(.*?)</title>",b,re.S)[:1])
    links=re.findall(r'href="([^"]+)"',b)
    from collections import Counter
    pat=Counter(re.sub(r"[0-9A-Za-z_\-]{4,}","X",l.split("?")[0]) for l in links)
    print("LINKPATTERNS",pat.most_common(25))
    print("HEAD",b[:400].replace("\n"," "))
    if "json" in u: print("JSON",b[:800])
    # sample product-like links
    print("SAMPLES",[l for l in links if re.search(r"goods|item|product|detail",l)][:15])
