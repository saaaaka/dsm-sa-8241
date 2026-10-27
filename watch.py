"""複数ショップの新着を確認し、新商品があれば ntfy でスマホに通知する。

監視先を増やすときは SITES に1行追加する。
  type="shopify" : Shopify製ショップ（url は products.json の場所）
  type="cibone"  : CIBONE の新着一覧ページ
  type="rss"     : WordPressなどのRSSフィード（feed にフィードの場所）
  type="links"   : 普通のページ。pattern に合うリンクが増えたら通知する
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
    {"name": "HUMAN MADE", "type": "shopify",
     "base": "https://www.humanmade.jp",
     "json": "/products.json?limit=250",
     "page": "/"},
    {"name": "MOC-O", "type": "shopify",
     "base": "https://store.moc-o.com",
     "json": "/collections/new-1/products.json?limit=250",
     "page": "/collections/new-1"},
    {"name": "メガホビ 遊戯王", "type": "links",
     "base": "https://www.megahobby.jp",
     "page": "/event/mh_yugioh/",
     # ページ内の商品ページへのリンクが増えたら通知
     "pattern": r"megahobby\.jp/products/item/(\d+)/"},
    {"name": "電撃ホビー デジモン", "type": "rss", "label": "新着記事",
     "base": "https://hobby.dengeki.com",
     "feed": "/tag/digimon/feed/",
     "page": "/tag/digimon/"},
    {"name": "コナミスタイル", "type": "links",
     "base": "https://www.konamistyle.jp",
     "page": "/products/list.php?mode=search&category_id=1001063",
     # 商品ページへのリンク（product_id を商品IDとして使う）
     "pattern": r"/products/detail(?:\.php\?product_id=|/)(\d+)"},
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


def fetch_rss(site):
    """WordPressなどのRSSフィード（新着記事）"""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(get(site["base"] + site["feed"]))
    items = {}
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        pid = (it.findtext("guid") or link).strip()
        items[pid] = {"title": (it.findtext("title") or "").strip(), "url": link, "price": ""}
    return items


def fetch_links(site):
    """普通のHTMLページ。pattern に合うリンクを1件として扱う（括弧があればその部分をIDにする）"""
    page_url = site["base"] + site["page"]
    page = get(page_url)
    items = {}
    for href, inner in re.findall(r'<a\b[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', page, re.S | re.I):
        url = urllib.parse.urljoin(page_url, html.unescape(href)).split("#")[0]
        m = re.search(site["pattern"], url)
        if not m:
            continue
        pid = m.group(1) if m.groups() else url
        title = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", inner)).split())
        if not title:  # 画像だけのリンクは alt を使う
            alt = re.search(r'alt=["\']([^"\']*)["\']', inner)
            title = html.unescape(alt.group(1)).strip() if alt else ""
        if pid not in items or (title and not items[pid]["title"]):
            items[pid] = {"title": title, "url": url, "price": ""}
    for p in items.values():
        p["title"] = p["title"] or p["url"]
    return items


FETCHERS = {"shopify": fetch_shopify, "cibone": fetch_cibone, "thetokyo": fetch_thetokyo,
            "rss": fetch_rss, "links": fetch_links}


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
    status = {}
    errors = 0
    for site in SITES:
        name = site["name"]
        try:
            products = FETCHERS[site["type"]](site)
        except Exception as e:
            print(f"[{name}] 取得失敗: {e}")
            status[name] = f"取得失敗: {e}"
            errors += 1
            continue
        if not products:
            print(f"[{name}] 商品が取れませんでした（ページ構成が変わった可能性）")
            status[name] = "0件（ページ構成が変わった可能性）"
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
                notify(f"{name} {site.get('label', '新商品')}", f"{p['title']} {p['price']}".strip(), p["url"])
            if len(unique) > 10:
                notify(f"{name} {site.get('label', '新商品')}", f"ほかに {len(unique) - 10} 件追加されています", page_url)

        sample = " | ".join(p["title"][:30] for p in list(products.values())[:3])
        print(f"[{name}] 取得 {len(products)} 件 / 新規 {len(new_ids)} 件 例: {sample}")
        status[name] = f"OK {len(products)}件"
        seen[name] = sorted(known | set(products))

    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)
    with open("status.json", "w") as f:  # 各サイトの最新の取得結果（GitHub上で確認用）
        json.dump(status, f, ensure_ascii=False, indent=1)
    if errors == len(SITES):
        sys.exit(1)


if __name__ == "__main__":
    main()
