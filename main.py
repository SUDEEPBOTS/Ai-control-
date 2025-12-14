import os
import asyncio
import sys
import re
from pyrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient
import google.generativeai as genai
from dotenv import load_dotenv

# ================== LOAD ENV ==================
load_dotenv()

try:
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    SESSION_STRING = os.getenv("SESSION_STRING")
    MONGO_URL = os.getenv("MONGO_URL")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
except Exception:
    print("❌ ENV missing or API_ID not int")
    sys.exit(1)

# ================== PYROGRAM ==================
app = Client(
    "ai_clone_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ================== MONGO ==================
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["my_digital_clone"]
msg_collection = db["user_messages"]
status_collection = db["bot_status"]

# ================== GEMINI ==================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# ================== DB HELPERS ==================
async def get_ai_status():
    doc = await status_collection.find_one({"_id": "main"})
    return doc["active"] if doc else False

async def set_ai_status(active: bool):
    await status_collection.update_one(
        {"_id": "main"},
        {"$set": {"active": active}},
        upsert=True
    )

async def get_my_style():
    cursor = msg_collection.find({}).sort("_id", -1).limit(25)
    msgs = await cursor.to_list(length=25)
    if not msgs:
        return "Speak casually in Hinglish, short replies."
    return "\n".join(m["text"] for m in msgs if "text" in m)

# ================== LEARN STYLE ==================
@app.on_message(filters.outgoing & ~filters.command(["ai"]))
async def learn_handler(_, message):
    if message.text and not message.text.startswith("."):
        await msg_collection.insert_one({"text": message.text})

# ================== AI ON / OFF ==================
@app.on_message(
    filters.outgoing &
    filters.regex(r"^\.ai\s+(on|off)$", flags=re.IGNORECASE)
)
async def ai_toggle(_, message):
    cmd = message.text.split()[-1].lower()
    print("AI TOGGLE:", cmd)

    if cmd == "on":
        await set_ai_status(True)
        await message.edit("🟢 **AI Ghost Mode ON**")
    else:
        await set_ai_status(False)
        await message.edit("🔴 **AI Ghost Mode OFF**")

# ================== AUTO REPLY ==================
@app.on_message(
    ~filters.outgoing &
    ~filters.bot &
    ~filters.service &
    (filters.private | filters.mentioned | filters.reply)
)
async def auto_reply(client, message):
    if not await get_ai_status():
        return

    # group safety
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not (message.mentioned or
                (message.reply_to_message and
                 message.reply_to_message.from_user and
                 message.reply_to_message.from_user.is_self)):
            return

    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

    style = await get_my_style()
    text = message.text or "Reply naturally to this message."
    name = message.from_user.first_name if message.from_user else "Someone"

    prompt = f"""
You are ME.
Reply exactly like my style.

PAST STYLE:
{style}

User ({name}) said:
{text}

Rules:
- Hinglish / Hindi
- 1–2 lines
- Casual
- No AI mention
"""

    try:
        res = model.generate_content(prompt)
        await asyncio.sleep(2)
        await message.reply_text(res.text.strip())
    except Exception as e:
        print("Gemini Error:", e)

# ================== START ==================
print("🚀 AI CLONE USERBOT STARTED")
app.run()
