import os
import json
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ─── Telegram ────────────────────────────────────────────────────────────────

def get_subscribers():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/subscribers?select=chat_id", headers=HEADERS)
    data = r.json()
    if not isinstance(data, list):
        return []
    return [row["chat_id"] for row in data]

def send_message(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    )

def broadcast(text):
    subscribers = get_subscribers()
    for chat_id in subscribers:
        send_message(chat_id, text)
    print(f"Broadcasted to {len(subscribers)} subscribers")

# ─── Supabase snapshot helpers ────────────────────────────────────────────────

def get_snapshot(brand):
    brand_encoded = requests.utils.quote(brand)
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/product_snapshots?brand=eq.{brand_encoded}&select=product_name,price,available",
        headers=HEADERS
    )
    data = r.json()
    if not isinstance(data, list):
        print(f"  Snapshot fetch error for {brand}: {data}")
        return None
    if len(data) == 0:
        return None  # First run for this brand
    return {row["product_name"]: row for row in data}

def upsert_snapshot(brand, products):
    for p in products:
        row = {
            "brand": brand,
            "product_name": p["name"],
            "price": p["price"],
            "available": p["available"],
            "last_seen": datetime.utcnow().isoformat()
        }
        requests.post(
            f"{SUPABASE_URL}/rest/v1/product_snapshots",
            headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
            json=row
        )

# ─── Scraper (Shopify) ────────────────────────────────────────────────────────

def scrape_shopify(brand_name, shop_url):
    try:
        base = shop_url.rstrip("/")
        r = requests.get(f"{base}/products.json?limit=250", timeout=15)
        data = r.json()
        products = []
        for p in data.get("products", []):
            for v in p.get("variants", []):
                products.append({
                    "name": f"{p['title']} - {v['title']}" if v['title'] != 'Default Title' else p['title'],
                    "price": v.get("price", "N/A"),
                    "available": v.get("available", False)
                })
        return products
    except Exception as e:
        print(f"Error scraping {brand_name}: {e}")
        return []

# ─── Compare & notify ─────────────────────────────────────────────────────────

def check_brand(brand_name, shop_url):
    print(f"Checking {brand_name}...")
    old = get_snapshot(brand_name)
    new_products = scrape_shopify(brand_name, shop_url)

    if not new_products:
        print(f"  No products found for {brand_name}")
        return

    # First run — save baseline, no alerts
    if old is None:
        print(f"  First run for {brand_name} — saving {len(new_products)} products as baseline. No alerts.")
        upsert_snapshot(brand_name, new_products)
        return

    new_map = {p["name"]: p for p in new_products}
    alerts = []

    for name, data in new_map.items():
        if name not in old:
            status = "✅ In Stock" if data["available"] else "❌ Out of Stock"
            alerts.append(f"🆕 <b>New Product!</b>\n{brand_name}: {name}\nPrice: ₹{data['price']}\n{status}")
        else:
            prev = old[name]
            if not prev["available"] and data["available"]:
                alerts.append(f"🔔 <b>Restocked!</b>\n{brand_name}: {name}\nPrice: ₹{data['price']}")
            try:
                if float(data["price"]) < float(prev["price"]):
                    alerts.append(f"💰 <b>Price Drop!</b>\n{brand_name}: {name}\n₹{prev['price']} → ₹{data['price']}")
            except:
                pass

    for alert in alerts:
        broadcast(alert)
        print(f"  Alert sent: {alert[:60]}...")

    upsert_snapshot(brand_name, new_products)
    print(f"  Done. {len(new_products)} products, {len(alerts)} alerts.")

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    with open("brands.json") as f:
        brands = json.load(f)

    for brand in brands:
        check_brand(brand["name"], brand["url"])

if __name__ == "__main__":
    main()
