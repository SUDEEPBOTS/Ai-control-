import os
import re
import asyncio
import random
from pyrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient
import google.generativeai as genai
from dotenv import load_dotenv

# ================= LOAD ENV =================
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
MONGO_URL = os.getenv("MONGO_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ================= CLIENT =================
app = Client(
    "sudeep_clone",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ================= DB =================
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo["sudeep_clone"]
style_col = db["style"]
state_col = db["state"]

# ================= GEMINI =================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# ================= HELPERS =================
async def get_state():
    d = await state_col.find_one({"_id": "main"})
    return d["active"] if d else False

async def set_state(val: bool):
    await state_col.update_one(
        {"_id": "main"},
        {"$set": {"active": val}},
        upsert=True
    )

async def get_style():
    cur = style_col.find({}).sort("_id", -1).limit(30)
    data = await cur.to_list(30)
    return "\n".join(d["text"] for d in data) if data else "Casual Hinglish."

# ================= SAVE STYLE =================
@app.on_message(filters.outgoing)
async def learn(_, m):
    if m.text and not m.text.startswith("."):
        await style_col.insert_one({"text": m.text})

# ================= AI ON / OFF =================
@app.on_message(
    filters.outgoing &
    filters.regex(r"^\.ai\s+(on|off)$", flags=re.I)
)
async def ai_toggle(_, m):
    cmd = m.text.split()[-1].lower()
    if cmd == "on":
        await set_state(True)
        await m.edit("🟢 AI ON")
    else:
        await set_state(False)
        await m.edit("🔴 AI OFF")

# ================= AUTO REPLY =================
@app.on_message(
    ~filters.outgoing &
    ~filters.bot &
    ~filters.service &
    (filters.private | filters.mentioned | filters.reply)
)
async def auto_reply(client, m):
    if not await get_state():
        return

    if m.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not (m.mentioned or
                (m.reply_to_message and m.reply_to_message.from_user.is_self)):
            return

    await client.send_chat_action(m.chat.id, enums.ChatAction.TYPING)

    prompt = f"""
You are Sudeep.
You are a real human, not AI.

My chat style:
{await get_style()}

Message:
{m.text}

Rules:
- Hinglish
- Short
- Natural
- Human mistakes allowed
"""

    try:
        res = model.generate_content(prompt)
        await asyncio.sleep(random.randint(2, 4))
        await m.reply_text(res.text.strip())
    except:
        await m.reply_text("hmm")

# ================= START MESSAGE =================
@app.on_message(filters.me & filters.private)
async def first_boot(_, m):
    if m.text == ".__boot__":
        await m.reply("save")

# ================= RUN =================
print("🚀 AI CLONE USERBOT STARTED")

with app:
    app.send_message("me", "save")
    app.run()
