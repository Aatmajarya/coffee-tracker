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
        json={"chat_id": chat_id, "text": text}
    )

def add_subscriber(chat_id):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/subscribers",
        headers={**HEADERS, "Prefer": "resolution=ignore-duplicates"},
        json={"chat_id": chat_id}
    )
    return r.status_code in [200, 201]

def remove_subscriber(chat_id):
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/subscribers?chat_id=eq.{chat_id}",
        headers=HEADERS
    )

def process_updates():
    r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?timeout=5")
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

    # Clear processed updates
    if last_update_id:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}")

if __name__ == "__main__":
    process_updates()
