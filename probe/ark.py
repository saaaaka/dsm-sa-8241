import re, sys
from playwright.sync_api import sync_playwright
URL = "https://www.arknets.co.jp/goods/search.aspx?gender=men&goods_type=newarrival&search=x"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(locale="ja-JP", user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
    r = pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    print("first status", r.status if r else None)
    for i in range(6):
        pg.wait_for_timeout(5000)
        h = pg.content()
        links = set(re.findall(r'href="([^"]*goods/detail[^"]*)"', h, re.I))
        print(i, "len", len(h), "title", pg.title(), "detail links", len(links))
        if links: break
    print("\n".join(sorted(links)[:10]))
    i = h.find("detail")
    print(h[max(0,i-1500):i+2500] if i>=0 else h[:3000])
    b.close()
