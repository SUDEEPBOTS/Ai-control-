import os, sys, re, asyncio, random
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
    "sudeep_ai_clone",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# ================= DATABASE =================
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

async def save_style(text):
    await style_col.insert_one({"text": text})

async def get_style():
    cur = style_col.find({}).sort("_id", -1).limit(25)
    data = await cur.to_list(25)
    if not data:
        return "Casual Hinglish, short replies."
    return "\n".join(d["text"] for d in data)

def clean_reply(text):
    banned = ["ai", "assistant", "bot", "language model"]
    for b in banned:
        text = re.sub(b, "", text, flags=re.I)
    return text.strip()

def fallback():
    return random.choice([
        "acha",
        "hmm",
        "dekhte hai",
        "haan",
        "thik hai"
    ])

# ================= ON START =================
@app.on_startup()
async def startup(client):
    await client.send_message(
        "me",
        "✅ **Sudeep AI Clone Started**"
    )

# ================= LEARN STYLE =================
@app.on_message(filters.outgoing)
async def learn(_, m):
    if m.text and not m.text.startswith("."):
        await save_style(m.text)

# ================= AI COMMAND =================
@app.on_message(
    filters.outgoing &
    filters.regex(r"^\.ai[\s_]*(on|off)$", re.I)
)
async def ai_toggle(_, m):
    cmd = re.search(r"(on|off)", m.text, re.I).group(1).lower()
    print("AI COMMAND:", cmd)

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

    text = m.text or "Reply naturally"
    style = await get_style()

    prompt = f"""
You are Sudeep.
You are a real human, not an AI.

Talking style:
{style}

Message:
{text}

Rules:
- Hinglish
- Short
- Natural
- Human vibe
- No AI words

Reply:
"""

    try:
        res = model.generate_content(prompt)
        await asyncio.sleep(random.randint(2, 5))
        reply = clean_reply(res.text)
        await m.reply_text(reply)
    except:
        await m.reply_text(fallback())

# ================= START =================
print("🚀 AI CLONE USERBOT STARTED")
app.run()
