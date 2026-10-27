"""複数ショップの新着を確認し、新商品があれば ntfy でスマホに通知する。

監視先を増やすときは SITES に1行追加する。
  type="shopify" : Shopify製ショップ（url は products.json の場所）
  type="cibone"  : CIBONE の新着一覧ページ
"""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

SITES = [
    {"name": "DSM", "type": "shopify",
     "base": "https://shop-jp.doverstreetmarket.com",
     "json": "/collections/whats-new/products.json?limit=250",
     "page": "/collections/whats-new"},
    {"name": "NEIGHBORHOOD", "type": "shopify",
     "base": "https://www.neighborhood.jp",
     "json": "/products.json?limit=250",
     "page": "/"},
    {"name": "CIBONE", "type": "cibone",
     "base": "https://www.cibone.com",
     "page": "/category/NEW/"},
    {"name": "THE TOKYO", "type": "thetokyo",
     "base": "https://the-tokyo.jp",
     "page": "/shop/e/eTT-M-N-A_ssd/?f12=0"},
]

SEEN_FILE = "seen.json"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_shopify(site):
    data = json.loads(get(site["base"] + site["json"]))
    items = {}
    for p in data.get("products", []):
        v = (p.get("variants") or [{}])[0]
        price = v.get("price", "")
        if price:
            price = f"¥{int(float(price)):,}"
        items[str(p["id"])] = {
            "title": f'{p.get("vendor", "")} {p.get("title", "")}'.strip(),
            "url": f'{site["base"]}/products/{p["handle"]}',
            "price": price,
        }
    return items


def fetch_cibone(site):
    page = get(site["base"] + site["page"])
    items = {}
    pattern = (r'<a href="(https://www\.cibone\.com/category/NEW/(\d+)\.html)" title="([^"]*)">'
               r'.*?<span class="price_en">([^<]*)</span>')
    for url, pid, title, price in re.findall(pattern, page, re.S):
        items[pid] = {"title": html.unescape(title), "url": url, "price": price.strip()}
    return items


def fetch_thetokyo(site):
    page = get(site["base"] + site["page"])
    items = {}
    pattern = (r'<a href="(/shop/g/g([0-9A-Za-z]+)/)"[^>]*>.*?<div class="name-til"><p>([^<]*)</p>'
               r'.*?<div class="type-til"><p>([^<]*)</p>.*?goods-price">([^<]*)<')
    for path, pid, brand, name, price in re.findall(pattern, page, re.S):
        items[pid] = {"title": html.unescape(f"{brand} {name}").strip(),
                      "url": site["base"] + path, "price": price.strip()}
    return items


FETCHERS = {"shopify": fetch_shopify, "cibone": fetch_cibone, "thetokyo": fetch_thetokyo}


def notify(title, body, click):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC未設定のため通知スキップ:", title, body)
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=body.encode("utf-8"),
        headers={
            "Title": urllib.parse.quote(title),
            "Click": click,
            "Priority": "high",
            "Tags": "shopping_bags",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30)


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}
    data = json.load(open(SEEN_FILE))
    if isinstance(data, list):  # 旧形式（DSMのみ）からの移行
        return {"DSM": data}
    return data


def main():
    seen = load_seen()
    errors = 0
    for site in SITES:
        name = site["name"]
        try:
            products = FETCHERS[site["type"]](site)
        except Exception as e:
            print(f"[{name}] 取得失敗: {e}")
            errors += 1
            continue
        if not products:
            print(f"[{name}] 商品が取れませんでした（ページ構成が変わった可能性）")
            errors += 1
            continue

        page_url = site["base"] + site["page"]
        first_run = name not in seen
        known = set(seen.get(name, []))
        new_ids = [pid for pid in products if pid not in known]

        if first_run:
            notify(f"{name} 監視スタート", f"現在の {len(products)} 件を記録しました。次回から新商品を通知します。", page_url)
        elif new_ids:
            unique = list({products[pid]["title"]: products[pid] for pid in reversed(new_ids)}.values())[::-1]
            for p in unique[:10]:  # 色違いなど同名商品は1通にまとめる
                notify(f"{name} 新商品", f"{p['title']} {p['price']}".strip(), p["url"])
            if len(unique) > 10:
                notify(f"{name} 新商品", f"ほかに {len(unique) - 10} 件追加されています", page_url)

        print(f"[{name}] 取得 {len(products)} 件 / 新規 {len(new_ids)} 件")
        seen[name] = sorted(known | set(products))

    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)
    if errors == len(SITES):
        sys.exit(1)


if __name__ == "__main__":
    main()
