"""Dover Street Market (JP) の新着ページを確認し、新商品があれば ntfy でスマホに通知する。"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

BASE = "https://shop-jp.doverstreetmarket.com"
COLLECTION = "whats-new"
SEEN_FILE = "seen.json"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_products():
    """{id: {"title", "url", "price"}} を返す。まずShopifyのJSON、だめならHTMLから拾う。"""
    try:
        data = json.loads(get(f"{BASE}/collections/{COLLECTION}/products.json?limit=250"))
        items = {}
        for p in data.get("products", []):
            v = (p.get("variants") or [{}])[0]
            items[str(p["id"])] = {
                "title": f'{p.get("vendor", "")} {p.get("title", "")}'.strip(),
                "url": f'{BASE}/products/{p["handle"]}',
                "price": v.get("price", ""),
            }
        if items:
            return items
    except Exception as e:  # JSONが無いサイト構成ならHTMLへ
        print(f"JSON取得失敗、HTMLで再試行: {e}")

    html = get(f"{BASE}/collections/{COLLECTION}")
    items = {}
    for handle in re.findall(r'href="(?:/collections/[^"/]+)?/products/([^"?#/]+)', html):
        items[handle] = {
            "title": urllib.parse.unquote(handle).replace("-", " "),
            "url": f"{BASE}/products/{handle}",
            "price": "",
        }
    return items


def notify(title, body, click):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC未設定のため通知スキップ:", title, body)
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=body.encode("utf-8"),
        headers={
            "Title": urllib.parse.quote(title),  # 日本語ヘッダー対策
            "Click": click,
            "Priority": "high",
            "Tags": "shopping_bags",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30)


def main():
    products = fetch_products()
    if not products:
        print("商品が1件も取れませんでした。サイト構成が変わった可能性があります。")
        sys.exit(1)

    first_run = not os.path.exists(SEEN_FILE)
    seen = set() if first_run else set(json.load(open(SEEN_FILE)))
    new_ids = [pid for pid in products if pid not in seen]

    if first_run:
        notify("DSM監視スタート", f"現在の新着 {len(products)} 件を記録しました。次回から新商品を通知します。", f"{BASE}/collections/{COLLECTION}")
    elif new_ids:
        for pid in new_ids[:10]:  # 一度に大量追加されたときは先頭10件だけ個別通知
            p = products[pid]
            price = f"¥{p['price']}" if p["price"] else ""
            notify("DSM 新商品", f"{p['title']} {price}".strip(), p["url"])
        if len(new_ids) > 10:
            notify("DSM 新商品", f"ほかに {len(new_ids) - 10} 件追加されています", f"{BASE}/collections/{COLLECTION}")

    print(f"取得 {len(products)} 件 / 新規 {len(new_ids)} 件")
    json.dump(sorted(seen | set(products)), open(SEEN_FILE, "w"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
