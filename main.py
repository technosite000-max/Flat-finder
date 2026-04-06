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
client_ai = genai.Client(api_key=gemini_api_key)

# ===== TELEGRAM CLIENT =====
client = TelegramClient("session", api_id, api_hash)

# ===== DEDUP STORAGE =====
seen_messages = set()

# ===== SEND ALERT =====
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message})


# ===== SMART RENT EXTRACTION =====
def extract_rent(msg):
    msg = msg.lower()
    rents = []

    # Match 5k, 10k, 6.5k
    k_matches = re.findall(r'(\d+(\.\d+)?)\s*k', msg)
    for match in k_matches:
        rents.append(int(float(match[0]) * 1000))

    # Match ₹5000, 10000 etc.
    num_matches = re.findall(r'(?:₹|rs)?\s*(\d{4,5})', msg)
    for num in num_matches:
        rents.append(int(num))

    # Remove unrealistic values (deposit etc.)
    rents = [r for r in rents if r <= 50000]

    return rents


# ===== BASIC FILTER =====
def basic_filter(msg):
    msg_lower = msg.lower()

    # Normalize message
    msg_lower = re.sub(r'\s+', ' ', msg_lower.strip())

    # AREA CHECK
    if not any(area in msg_lower for area in AREAS):
        return False

    # VACANCY INTENT
    if not any(word in msg_lower for word in [
        "vacancy", "flatmate", "sharing", "replacement", "room"
    ]):
        return False

    # REJECT FULL FLAT POSTS
    if any(word in msg_lower for word in ["1bhk", "2bhk", "3bhk"]):
        if not any(word in msg_lower for word in [
            "vacancy", "sharing", "per person", "flatmate", "room"
        ]):
            return False

    # REJECT FEMALE ONLY
    if any(word in msg_lower for word in [
        "female only", "girls only", "only for girls"
    ]):
        return False

    # RENT CHECK
    rents = extract_rent(msg_lower)

    if rents:
        if all(r > MAX_RENT for r in rents):
            return False

    # UNFURNISHED REJECT
    if "unfurnished" in msg_lower:
        return False

    return True


# ===== AI FILTER =====
def ai_filter(msg):
    prompt = f"""
You are a strict classifier for rental messages.

USER REQUIREMENTS:
- Male or mixed allowed
- Reject only if strictly female only
- Single vacancy / flatmate / shared
- Rent <= 10000 per person
- Areas near Bavdhan Pune
- Must NOT be unfurnished
- Reject full flats

MESSAGE:
{msg}

OUTPUT:
MATCH: YES or NO
CONFIDENCE: HIGH / MEDIUM / LOW
"""

    try:
        response = client_ai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = getattr(response, "text", "")

        if "MATCH: YES" in text and "CONFIDENCE: HIGH" in text:
            return True

        return False

    except:
        return False


# ===== HANDLER =====
@client.on(events.NewMessage)
async def handler(event):
    msg = event.message.message

    if not msg:
        return

    # UNIQUE KEY (BEST DEDUP)
    unique_key = f"{event.chat_id}_{event.message.id}"

    if unique_key in seen_messages:
        return
    seen_messages.add(unique_key)

    # BASIC FILTER
    if not basic_filter(msg):
        return

    # AI FILTER
    if not ai_filter(msg):
        return

    # PHONE EXTRACTION
    phones = re.findall(r'\b\d{10}\b', msg)
    phone_text = f"\n📞 {phones[0]}" if phones else ""

    # CLEAN FINAL OUTPUT
    alert = f"{msg}{phone_text}"

    send_telegram_alert(alert)


# ===== START =====
client.start()
print("🚀 Bot Running Cleanly...")
client.run_until_disconnected()
