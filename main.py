from telethon import TelegramClient, events
import requests
import google.generativeai as genai
import re
import os

# ===== ENV VARIABLES =====
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("CHAT_ID")
gemini_api_key = os.getenv("GEMINI_API_KEY")

# ===== CONFIG =====
AREAS = ["baner", "bavdhan", "bhugaon"]
MAX_RENT = 10000

# ===== INIT GEMINI =====
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

# ===== TELEGRAM CLIENT =====
client = TelegramClient("session", api_id, api_hash)

# ===== SEND ALERT =====
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message})

# ===== BASIC FILTER =====
def basic_filter(msg):
    msg_lower = msg.lower()

    if not any(area in msg_lower for area in AREAS):
        return False

    rent = re.findall(r'\d{3,5}', msg_lower)
    if rent:
        try:
            if int(rent[0]) > MAX_RENT:
                return False
        except:
            pass

    return True

# ===== AI FILTER =====
def ai_filter(msg):
    prompt = f"""
User wants:
- Single sharing / 1 vacancy
- Rent below 10000
- Areas: Bavdhan, Baner, Bhugaon
- Prefer semi-furnished

Message:
{msg}

Reply ONLY:
MATCH: YES or NO
RENT: value or NA
AREA: value or NA
TYPE: single sharing or not
"""

    try:
        response = model.generate_content(prompt)
        text = response.text
        return "MATCH: YES" in text, text
    except Exception as e:
        print("AI Error:", e)
        return False, str(e)

# ===== HANDLER =====
@client.on(events.NewMessage)
async def handler(event):
    msg = event.message.message

    if not msg:
        return

    if not basic_filter(msg):
        return

    match, analysis = ai_filter(msg)

    if match:
        alert = f"🏠 MATCH FOUND\n\n{msg}\n\n📊 {analysis}"
        send_telegram_alert(alert)
        print("✅ MATCH SENT")
    else:
        print("❌ Not relevant")

# ===== START =====
client.start()
print("🚀 Production Bot Running...")
client.run_until_disconnected()
