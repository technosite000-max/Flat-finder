from telethon import TelegramClient, events
import requests
import re
import os
from google import genai

# ===== ENV VARIABLES =====
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
chat_id = os.getenv("CHAT_ID")
gemini_api_key = os.getenv("GEMINI_API_KEY")

# ===== CONFIG =====
AREAS = ["baner", "bavdhan", "bhugaon", "pashan", "sus"]
MAX_RENT = 10000

# ===== INIT GEMINI =====
print("🔑 Initializing Gemini...")
client_ai = genai.Client(api_key=gemini_api_key)

# ===== TELEGRAM CLIENT =====
print("📡 Connecting Telegram client...")
client = TelegramClient("session", api_id, api_hash)

# ===== SEND ALERT =====
def send_telegram_alert(message):
    print("📤 Sending alert to Telegram...")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    res = requests.post(url, data={"chat_id": chat_id, "text": message})

    print("📬 Telegram Response:", res.status_code, res.text)

# ===== BASIC FILTER =====
def basic_filter(msg):
    msg_lower = msg.lower()
    print("🔍 Running basic filter...")

    # Area check
    area_match = any(area in msg_lower for area in AREAS)
    print("📍 Area match:", area_match)

    if not area_match:
        return False

    # Flat rejection logic
    if "2bhk" in msg_lower or "3bhk" in msg_lower:
        if "per person" not in msg_lower and "sharing" not in msg_lower:
            print("🏠 Rejected full flat")
            return False

    # Unfurnished reject
    if "unfurnished" in msg_lower:
        print("🪑 Rejected unfurnished")
        return False

    # Rent extraction
    rent = re.findall(r'\d{3,5}', msg_lower)
    print("💰 Rent extracted:", rent)

    if rent:
        try:
            if int(rent[0]) > MAX_RENT:
                print("💸 Rent too high:", rent[0])
                return False
        except Exception as e:
            print("⚠️ Rent parse error:", e)

    print("✅ Basic filter passed")
    return True

# ===== AI FILTER =====
def ai_filter(msg):
    print("🧠 Sending to AI...")

    prompt = f"""
User is looking for:
- ONLY single vacancy / sharing
- Rent <= 10000
- Locations: Baner, Pashan, Bavdhan, Bhugaon, Sus
- Reject unfurnished

Message:
{msg}

Reply:
MATCH: YES or NO
"""

    try:
        response = client_ai.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )

        text = getattr(response, "text", "")
        print("🤖 AI Response:", text)

        return "MATCH: YES" in text, text

    except Exception as e:
        print("❌ AI Error:", e)
        return False, str(e)

# ===== HANDLER =====
@client.on(events.NewMessage)
async def handler(event):
    msg = event.message.message

    print("\n==============================")
    print("📩 NEW MESSAGE RECEIVED")
    print("🆔 Chat ID:", event.chat_id)
    print("💬 Message:", msg)

    if not msg:
        print("⚠️ Empty message")
        return

    # BASIC FILTER
    if not basic_filter(msg):
        print("❌ Rejected by basic filter")
        return

    # AI FILTER
    match, analysis = ai_filter(msg)

    if match:
        print("🎯 MATCH FOUND")

        alert = f"🏠 MATCH FOUND\n\n{msg}\n\n📊 {analysis}"
        send_telegram_alert(alert)

    else:
        print("❌ Rejected by AI")

# ===== START =====
client.start()
print("🚀 Production Bot Running...")
client.run_until_disconnected()
