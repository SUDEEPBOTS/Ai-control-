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

# --- PYROGRAM SETUP WITH ERROR CHECKING ---
try:
    print("STATUS: Pyrogram Client object bana raha hai...")
    app = Client("my_clone_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
    print("STATUS: Pyrogram Client object successfully ban gaya.")
except Exception as e:
    print("\n\n🚨 CRITICAL ERROR 1: PYROGRAM CLIENT SETUP FAILED 🚨")
    print(f"Error: {e}")
    print("FIX: API_ID, API_HASH, ya SESSION_STRING check karein.")
    exit(1) # Agar yahan fail hua to aage code nahi chalega


# --- MONGO DB SETUP WITH ERROR CHECKING ---
try:
    print("STATUS: MongoDB connection check kar raha hai...")
    mongo_client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000) # 5 sec timeout
    
    # Quick check to ensure connection is valid
    mongo_client.admin.command('ping') 
    
    db = mongo_client["my_digital_clone"]
    msg_collection = db["user_messages"]
    status_collection = db["bot_status"] 
    print("STATUS: MongoDB connection successful.")
except Exception as e:
    print("\n\n🚨 CRITICAL ERROR 2: MONGODB CONNECTION FAILED 🚨")
    print(f"Error: {e}")
    print("FIX: MONGO_URL check karein aur Atlas mein IP Whitelist (0.0.0.0/0) on karein.")
    exit(1)


# --- GEMINI SETUP WITH ERROR CHECKING ---
try:
    print("STATUS: Gemini API key check kar raha hai...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    # Simple call to check if key works
    model.generate_content("hi", generation_config=genai.types.GenerateContentConfig(
        max_output_tokens=5
    ))
    print("STATUS: Gemini API key successful.")
except Exception as e:
    print("\n\n🚨 CRITICAL ERROR 3: GEMINI API KEY FAILED 🚨")
    print(f"Error: {e}")
    print("FIX: GEMINI_API_KEY (Google AI Studio Key) check karein.")
    exit(1)


# --- REMAINDER OF YOUR CODE (HELPERS AND HANDLERS) ---

# --- HELPERS ---

async def get_ai_status():
    status = await status_collection.find_one({"_id": "main_status"})
    return status.get("active", False) if status else False

async def set_ai_status(active: bool):
    await status_collection.update_one(
        {"_id": "main_status"}, 
        {"$set": {"active": active}}, 
        upsert=True
    )

async def get_my_style():
    cursor = msg_collection.find({}).sort("_id", -1).limit(30)
    messages = await cursor.to_list(length=30)
    if not messages:
        return "Speak casually in Hinglish."
    return "\n".join([m['text'] for m in messages if 'text' in m])

# --- 1. LEARNING (Messages Save Karna) ---
@app.on_message(filters.me & ~filters.service)
async def learn_handler(client, message):
    if message.text and not message.text.startswith("."): 
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

# --- 3. AUTO REPLY HANDLER (Logic same hai) ---
@app.on_message(
    ~filters.me & ~filters.bot & ~filters.service & 
    (filters.private | filters.mentioned | filters.reply)
)
async def auto_reply(client, message):
    is_active = await get_ai_status()
    if not is_active:
        return

    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        is_relevant = False
        if message.mentioned:
            is_relevant = True
        elif message.reply_to_message and message.reply_to_message.from_user.is_self:
            is_relevant = True
        
        if not is_relevant:
            return

    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    
    my_style = await get_my_style()
    incoming = message.text or "[Media/Sticker]"
    sender_name = message.from_user.first_name if message.from_user else "Unknown"

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
        
        await asyncio.sleep(2) 
        
        if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            await message.reply_text(reply_text)
        else:
            await message.reply_text(reply_text)
            
    except Exception as e:
        print(f"AI Response Generation Error: {e}")

# --- START BOT ---
print("\n--- ATTEMPTING TO START BOT ---")

try:
    print("STATUS: Pyrogram connection shuru...")
    app.run()
    
# Agar Pyrogram chalu hone ke baad turant ruk jaye (most likely Session String ka error)
except Exception as e: 
    print("\n\n🚨 CRITICAL ERROR 4: PYROGRAM RUNTIME FAILED 🚨")
    print(f"Error: {e}")
    print("FIX: API_ID, API_HASH, ya SESSION_STRING me koi galti hai.")


