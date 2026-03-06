import os
import requests

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def send_message(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10
    )

def add_subscriber(chat_id):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/subscribers",
        headers={**HEADERS, "Prefer": "resolution=ignore-duplicates"},
        json={"chat_id": chat_id},
        timeout=10
    )
    return r.status_code in [200, 201]

def remove_subscriber(chat_id):
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/subscribers?chat_id=eq.{chat_id}",
        headers=HEADERS,
        timeout=10
    )

def get_last_update_id():
    """Get the last processed update ID from Supabase"""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/bot_state?key=eq.last_update_id&select=value",
        headers=HEADERS,
        timeout=10
    )
    data = r.json()
    if isinstance(data, list) and len(data) > 0:
        return int(data[0]["value"])
    return None

def save_last_update_id(update_id):
    """Save the last processed update ID to Supabase"""
    requests.post(
        f"{SUPABASE_URL}/rest/v1/bot_state",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
        json={"key": "last_update_id", "value": str(update_id)},
        timeout=10
    )

def process_updates():
    last_id = get_last_update_id()
    
    # Build URL with offset to only get new updates
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?timeout=5&limit=100"
    if last_id is not None:
        url += f"&offset={last_id + 1}"
    
    r = requests.get(url, timeout=15)
    updates = r.json().get("result", [])

    if not updates:
        print("No new updates")
        return

    last_update_id = None

    for update in updates:
        last_update_id = update["update_id"]
        msg = update.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "").strip().lower()

        if not chat_id:
            continue

        if text == "/start":
            add_subscriber(chat_id)
            send_message(chat_id,
                "☕ Welcome to Coffee Drop!\n\n"
                "You're now subscribed. I'll notify you whenever your favourite Indian specialty coffee brands restock, launch new products, or drop prices.\n\n"
                "Send /stop to unsubscribe anytime."
            )
            print(f"New subscriber: {chat_id}")

        elif text == "/stop":
            remove_subscriber(chat_id)
            send_message(chat_id, "You've been unsubscribed. Send /start anytime to resubscribe. ☕")
            print(f"Unsubscribed: {chat_id}")

        elif text == "/status":
            send_message(chat_id, "✅ Bot is running! You'll be notified of any coffee drops.")

    if last_update_id:
        save_last_update_id(last_update_id)
        # Tell Telegram to mark all these as processed
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}",
            timeout=10
        )
        print(f"Processed updates up to {last_update_id}")

if __name__ == "__main__":
    process_updates()
