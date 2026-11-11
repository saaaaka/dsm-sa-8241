import re
from playwright.sync_api import sync_playwright
U = "https://www.humanmade.jp/new-arrivals/"
with sync_playwright() as p:
    b = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(locale="ja-JP", viewport={"width":1280,"height":900}, user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    pg = ctx.new_page()
    r = pg.goto(U, wait_until="domcontentloaded", timeout=60000)
    print("status", r.status)
    for i in range(12):
        pg.wait_for_timeout(5000)
        try:
            h = pg.content(); t = pg.title()
        except Exception as e:
            print(i, "navigating"); continue
        print(i, len(h), t, pg.url)
        if "しばらく" not in t and "moment" not in t: break
    i = h.find('/products/') if '/products/' in h else h.find('href="/')
    print(h[max(0,i-500):i+3000])
    b.close()
