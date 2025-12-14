import os
import re
import sys
import asyncio
from pyrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient
import google.generativeai as genai
from dotenv import load_dotenv

# ================= LOAD ENV =================
load_dotenv()

try:
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    SESSION_STRING = os.getenv("SESSION_STRING")
    MONGO_URL = os.getenv("MONGO_URL")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
except Exception as e:
    print("❌ ENV ERROR:", e)
    sys.exit(1)

# ================= PYROGRAM =================
app = Client(
    "sudeep_clone",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ================= DB =================
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["sudeep_clone"]
state_col = db["state"]
style_col = db["style"]

# ================= GEMINI =================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# ================= HELPERS =================
async def is_ai_on():
    d = await state_col.find_one({"_id": "ai"})
    return d["on"] if d else False

async def set_ai(on: bool):
    await state_col.update_one(
        {"_id": "ai"},
        {"$set": {"on": on}},
        upsert=True
    )

async def save_style(text):
    await style_col.insert_one({"text": text})

async def get_style():
    cur = style_col.find({}).sort("_id", -1).limit(25)
    data = await cur.to_list(25)
    return "\n".join(d["text"] for d in data) if data else "Casual Hinglish."

# ================= STYLE LEARN =================
@app.on_message(filters.outgoing)
async def learn(_, m):
    if m.text and not m.text.startswith("."):
        await save_style(m.text)

# ================= AI ON / OFF =================
@app.on_message(
    filters.outgoing &
    filters.regex(r"^\.ai\s+(on|off)$", flags=re.IGNORECASE)
)
async def ai_toggle(_, m):
    cmd = m.text.split()[-1].lower()

    if cmd == "on":
        await set_ai(True)
        await m.edit("🟢 AI ON")
    else:
        await set_ai(False)
        await m.edit("🔴 AI OFF")

# ================= AUTO REPLY =================
@app.on_message(
    ~filters.outgoing &
    ~filters.bot &
    ~filters.service &
    (filters.private | filters.mentioned | filters.reply)
)
async def auto_reply(client, m):
    if not await is_ai_on():
        return

    if m.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not (m.mentioned or (m.reply_to_message and m.reply_to_message.from_user.is_self)):
            return

    await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)

    style = await get_style()
    text = m.text or "Reply naturally."

    prompt = f"""
You are Sudeep.
You are a real human.

Style:
{style}

Message:
{text}

Rules:
- Hinglish
- Short
- Natural
- No AI mention

Reply:
"""

    try:
        res = model.generate_content(prompt)
        await asyncio.sleep(2)
        await m.reply_text(res.text.strip())
    except Exception as e:
        print("Gemini error:", e)

# ================= MAIN =================
async def main():
    await app.start()

    # ✅ STARTUP MESSAGE (Saved Messages)
    try:
        await app.send_message("me", "save")
    except Exception as e:
        print("Startup message failed:", e)

    print("🚀 AI CLONE USERBOT STARTED")
    await app.idle()

app.run(main())
