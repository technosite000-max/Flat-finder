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
client_ai = genai.Client(api_key=gemini_api_key)

# ===== TELEGRAM CLIENT =====
client = TelegramClient("session", api_id, api_hash)

# ===== SEND ALERT =====
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message})

# ===== BASIC FILTER (FASTER + SMARTER) =====
def basic_filter(msg):
    msg_lower = msg.lower()

    # Area check
    if not any(area in msg_lower for area in AREAS):
        return False

    # Reject obvious full-flat posts
    if "2bhk" in msg_lower or "3bhk" in msg_lower:
        if "per person" not in msg_lower and "sharing" not in msg_lower:
            return False

    # Reject unfurnished early
    if "unfurnished" in msg_lower:
        return False

    # Rent check (basic)
    rent = re.findall(r'\d{3,5}', msg_lower)
    if rent:
        try:
            if int(rent[0]) > MAX_RENT:
                return False
        except:
            pass

    return True

# ===== AI FILTER (STRONG LOGIC) =====
def ai_filter(msg):
    prompt = f"""
User is looking for:

STRICT REQUIREMENTS:
- ONLY single vacancy / flatmate / sharing (NOT full flat)
- Rent must be <= 10000 per person
- Locations: Baner, Pashan, Bavdhan, Bhugaon, Sus
- Must be semi-furnished or fully furnished
- REJECT unfurnished
- REJECT full flat unless clearly "per person" or "sharing"

SMART DETECTION:
- If 2BHK/3BHK but mentions "vacancy" or "sharing" → ACCEPT
- If rent looks too low for full flat → treat carefully
- Prefer genuine flatmate posts

Message:
{msg}

Reply STRICTLY in this format:
MATCH: YES or NO
REASON: short reason
TYPE: vacancy/full/unknown
RENT: value or NA
AREA: value or NA
FURNISHING: furnished/semi/unfurnished/unknown
"""

    try:
        response = client_ai.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )

        text = getattr(response, "text", "")
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

    print("📩 Incoming:", msg[:80])

    if not basic_filter(msg):
        print("❌ Basic filter rejected")
        return

    match, analysis = ai_filter(msg)

    if match:
        alert = f"🏠 MATCH FOUND\n\n{msg}\n\n📊 {analysis}"
        send_telegram_alert(alert)
        print("✅ MATCH SENT")
    else:
        print("❌ AI rejected")

# ===== START =====
client.start()
print("🚀 Production Bot Running...")
client.run_until_disconnected()
