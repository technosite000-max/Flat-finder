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
AREAS = [
    "bavdhan", "bhugaon", "bhukum",
    "sus", "pashan",
    "baner", "balewadi",
    "kothrud", "warje", "mahalunge"
]

MAX_RENT = 10000

# ===== INIT GEMINI =====
print("🔑 Initializing Gemini...")
client_ai = genai.Client(api_key=gemini_api_key)

# ===== TELEGRAM CLIENT =====
print("📡 Connecting Telegram client...")
client = TelegramClient("session", api_id, api_hash)

# ===== DEDUP STORAGE =====
seen_messages = set()

# ===== SEND ALERT =====
def send_telegram_alert(message):
    print("📤 Sending alert...")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    res = requests.post(url, data={"chat_id": chat_id, "text": message})
    print("📬 Response:", res.status_code)

# ===== BASIC FILTER =====
def basic_filter(msg):
    msg_lower = msg.lower()
    print("🔍 Running basic filter...")

    # AREA CHECK
    if not any(area in msg_lower for area in AREAS):
        print("❌ Area not matched")
        return False

    # VACANCY INTENT
    if not any(word in msg_lower for word in [
        "vacancy", "flatmate", "sharing", "replacement", "room"
    ]):
        print("❌ No vacancy intent")
        return False

    # REJECT FULL FLAT POSTS
    if any(word in msg_lower for word in ["1bhk", "2bhk", "3bhk"]):
        if not any(word in msg_lower for word in [
            "vacancy", "sharing", "per person", "flatmate", "room"
        ]):
            print("🏠 Full flat rejected")
            return False

    # ONLY REJECT FEMALE-ONLY POSTS
    if any(word in msg_lower for word in [
        "female only", "girls only", "only for girls"
    ]):
        print("❌ Female-only rejected")
        return False

    # RENT CHECK
    rent = re.findall(r'\d{3,5}', msg_lower)
    print("💰 Rent found:", rent)

    if rent:
        try:
            if int(rent[0]) > MAX_RENT:
                print("💸 Rent too high")
                return False
        except:
            pass

    # UNFURNISHED REJECT
    if "unfurnished" in msg_lower:
        print("🪑 Unfurnished rejected")
        return False

    print("✅ Basic filter passed")
    return True

# ===== AI FILTER =====
def ai_filter(msg):
    print("🧠 Sending to AI...")

    prompt = f"""
You are a strict classifier for rental messages.

USER REQUIREMENTS:
- Male or mixed allowed (girls allowed is OK)
- Only reject if strictly "female only"
- Single vacancy / flatmate / shared room / one room in flat
- Rent must be <= 10000 per person
- Areas near Bavdhan Pune:
  Bavdhan, Bhugaon, Bhukum, Sus, Pashan, Baner, Balewadi, Kothrud
- Must NOT be unfurnished
- Reject full flat listings unless sharing clearly mentioned

RULES:
- "vacancy available" → ACCEPT
- "1 room available in 2BHK" → ACCEPT
- "girls allowed" → ACCEPT
- "female only" → REJECT
- "2BHK full flat rent 25k" → REJECT
- If unclear → REJECT

MESSAGE:
{msg}

OUTPUT FORMAT STRICT:
MATCH: YES or NO
CONFIDENCE: HIGH / MEDIUM / LOW
REASON: short reason
TYPE: vacancy/full/room/unknown
RENT: number or NA
AREA: detected area or NA
GENDER: male/female/mixed/unknown
"""

    try:
        response = client_ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = getattr(response, "text", "")
        print("🤖 AI Response:", text)

        # Only accept high confidence
        if "MATCH: YES" in text and "CONFIDENCE: LOW" not in text:
            return True, text

        return False, text

    except Exception as e:
        print("❌ AI Error:", e)
        # fallback → allow if basic filter passed
        return True, "AI failed but basic filter passed"

# ===== HANDLER =====
@client.on(events.NewMessage)
async def handler(event):
    msg = event.message.message

    print("\n==============================")
    print("📩 NEW MESSAGE")
    print("💬", msg)

    if not msg:
        return

    # DEDUP
    if msg in seen_messages:
        print("⚠️ Duplicate skipped")
        return
    seen_messages.add(msg)

    # BASIC FILTER
    if not basic_filter(msg):
        print("❌ Rejected by basic filter")
        return

    # AI FILTER
    match, analysis = ai_filter(msg)

    if match:
        print("🎯 MATCH FOUND")

        # PHONE EXTRACTION
        phones = re.findall(r'\b\d{10}\b', msg)
        phone_text = f"\n📞 Contact: {phones[0]}" if phones else ""

        alert = f"""🏠 MATCH FOUND

{msg}{phone_text}

📊 {analysis}
"""

        send_telegram_alert(alert)

    else:
        print("❌ Rejected by AI")

# ===== START =====
client.start()
print("🚀 Production Bot Running...")
client.run_until_disconnected()
