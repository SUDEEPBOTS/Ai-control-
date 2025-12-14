import os
import asyncio
from pyrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
MONGO_URL = os.getenv("MONGO_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- SETUP ---
app = Client("my_clone_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["my_digital_clone"]
msg_collection = db["user_messages"]
status_collection = db["bot_status"] # AI Mode ka status save karne ke liye

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- HELPERS ---

async def get_ai_status():
    # Check karo ki AI mode ON hai ya OFF (Database se, taaki restart hone par bhi yaad rahe)
    status = await status_collection.find_one({"_id": "main_status"})
    return status.get("active", False) if status else False

async def set_ai_status(active: bool):
    await status_collection.update_one(
        {"_id": "main_status"}, 
        {"$set": {"active": active}}, 
        upsert=True
    )

async def get_my_style():
    # Tumhare last 30 messages uthayega style copy karne ke liye
    cursor = msg_collection.find({}).sort("_id", -1).limit(30)
    messages = await cursor.to_list(length=30)
    if not messages:
        return "Speak casually in Hinglish."
    return "\n".join([m['text'] for m in messages if 'text' in m])

# --- 1. LEARNING (Messages Save Karna) ---
@app.on_message(filters.me & ~filters.service)
async def learn_handler(client, message):
    if message.text and not message.text.startswith("."): # Commands save mat karna
        await msg_collection.insert_one({
            "text": message.text,
            "date": message.date
        })

# --- 2. CONTROLS (.ai on / .ai off) ---
@app.on_message(filters.me & filters.command("ai", prefixes="."))
async def mode_handler(client, message):
    if len(message.command) < 2:
        await message.edit("❌ **Usage:** `.ai on` or `.ai off`")
        return

    cmd = message.command[1].lower()
    
    if cmd == "on":
        await set_ai_status(True)
        await message.edit("🟢 **AI Ghost Mode: ACTIVATED**\nAb mai tumhari jagah reply karunga.")
    elif cmd == "off":
        await set_ai_status(False)
        await message.edit("🔴 **AI Ghost Mode: DEACTIVATED**\nWelcome back.")
    else:
        await message.edit("❌ Sirf `on` ya `off` use karein.")

# --- 3. AUTO REPLY HANDLER ---
# Logic: Incoming message ho, jo user (tum) ne na bheja ho.
# Groups me: Sirf Mention ya Reply hone par trigger ho.
# Private me: Sab messages par trigger ho.
@app.on_message(
    ~filters.me & ~filters.bot & ~filters.service & 
    (filters.private | filters.mentioned | filters.reply)
)
async def auto_reply(client, message):
    # Sabse pehle check karo AI ON hai ya nahi
    is_active = await get_ai_status()
    if not is_active:
        return

    # Group Protection: Agar group hai, toh check karo ki reply tumhare message pe hai ya tumhe tag kiya hai
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        is_relevant = False
        if message.mentioned: # Tumhara username tag kiya
            is_relevant = True
        elif message.reply_to_message and message.reply_to_message.from_user.is_self: # Tumhare msg pe reply kiya
            is_relevant = True
        
        if not is_relevant:
            return # Agar bas group me baat chal rahi hai aur tum involved nahi ho, toh ignore.

    # --- ACTION ---
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    
    # 1. Tumhara style load karo
    my_style = await get_my_style()
    
    # 2. Incoming text
    incoming = message.text or "[Media/Sticker]"
    sender_name = message.from_user.first_name if message.from_user else "Unknown"

    # 3. Prompt
    prompt = f"""
    You are roleplaying as ME (The user). You are currently offline, handling chats via AI.
    
    **My Past Messages (Copy this style, tone, and language):**
    {my_style}
    
    **Context:**
    - I am currently away.
    - User '{sender_name}' sent: "{incoming}"
    
    **Instructions:**
    - Reply exactly like I would.
    - If it's a casual greeting, reply casually.
    - If it's urgent, say I'll be back soon (but in my style).
    - Keep it short (1-2 sentences).
    - Use Hinglish/Hindi as per my past messages.
    
    **Reply:**
    """
    
    try:
        response = model.generate_content(prompt)
        reply_text = response.text.strip()
        
        await asyncio.sleep(2) # Human delay
        
        if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            # Group me reply karke (quote karke) bhejo
            await message.reply_text(reply_text)
        else:
            # DM me normal bhejo
            await message.reply_text(reply_text)
            
    except Exception as e:
        print(f"AI Error: {e}")

print("🔥 Bot Started. Use .ai on to activate.")
app.run()
  
