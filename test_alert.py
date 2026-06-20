import requests # The library that lets Python talk to the internet

def send_telegram_alert(message):
    # 1. Your unique security keys
    bot_token = '8858841052:AAFlAuPfHqFscFxlRA2qZRjjoRBofMFWXqw' # <-- PASTE YOUR BOTFATHER TOKEN HERE
    chat_id = '8066843956'            # <-- Your confirmed Chat ID

    # 2. The exact URL destination on Telegram's servers
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # 3. The data package we are sending to Telegram
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown" # Allows us to use bold text and emojis
    }

    # 4. Executing the action: Firing the package across the internet
    response = requests.post(url, json=payload)

    # 5. A quick check to tell our Ubuntu terminal if it worked
    if response.status_code == 200:
        print("✅ Success: The engine just pinged your phone!")
    else:
        print(f"❌ Failed to send: {response.text}")

# 6. The actual command that runs when we start the script
send_telegram_alert("🚀 *Engine Online:* Phase 1 diagnostics are running perfectly.")