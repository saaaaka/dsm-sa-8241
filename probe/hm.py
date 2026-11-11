import re, collections
from playwright.sync_api import sync_playwright
U = "https://www.humanmade.jp/new-arrivals/"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(locale="ja-JP", user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
    for url in [U, "https://www.humanmade.jp/products.json?limit=3"]:
        r = pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        print("=====", url, r.status if r else None, dict((k,v) for k,v in (r.headers if r else {}).items() if k in ("server","content-type","cf-mitigated","x-shopid","powered-by")))
        h = ""
        for i in range(6):
            pg.wait_for_timeout(3000)
            h = pg.content()
            if "/products/" in h: break
        print("len", len(h), "title", pg.title())
        hs = re.findall(r'href="([^"]+)"', h)
        print(collections.Counter(re.sub(r"[0-9]+","N",x)[:60] for x in hs).most_common(25))
        i = h.find('/products/')
        print(h[max(0,i-1500):i+2500] if i>=0 else h[:1500])
    b.close()
