import os
import asyncio
import sys
from pyrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv

# Environment Variables Load
load_dotenv()

# --- CONFIGURATION (Ensure these are set in Railway Variables) ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
MONGO_URL = os.getenv("MONGO_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- 1. PYROGRAM CLIENT SETUP WITH ERROR CHECKING ---
try:
    print("STATUS: Pyrogram Client object bana raha hai...")
    # Initialize Client with provided credentials
    app = Client("my_clone_bot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
    print("STATUS: Pyrogram Client object successfully ban gaya.")
except Exception as e:
    print("\n\n🚨 CRITICAL ERROR 1: PYROGRAM CLIENT SETUP FAILED 🚨")
    print(f"Error: {e}")
    print("FIX: API_ID, API_HASH, ya SESSION_STRING check karein. Session string naya generate karein.")
    sys.exit(1) # Stop deployment

# --- 2. MONGO DB SETUP WITH ERROR CHECKING ---
try:
    print("STATUS: MongoDB connection check kar raha hai...")
    # Add serverSelectionTimeoutMS for quick fail on connection error
    mongo_client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000) 
    
    # Quick check to ensure connection is valid
    mongo_client.admin.command('ping') 
    
    db = mongo_client["my_digital_clone"]
    msg_collection = db["user_messages"]
    status_collection = db["bot_status"] 
    print("STATUS: MongoDB connection successful.")
except Exception as e:
    print("\n\n🚨 CRITICAL ERROR 2: MONGODB CONNECTION FAILED 🚨")
    print(f"Error: {e}")
    print("FIX: MONGO_URL check karein aur MongoDB Atlas mein Network Access (IP Whitelist 0.0.0.0/0) on karein.")
    sys.exit(1)


# --- 3. GEMINI SETUP WITH ERROR CHECKING AND FIX ---
try:
    print("STATUS: Gemini API key check kar raha hai...")
    genai.configure(api_key=GEMINI_API_KEY)
    # Using the specified model
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Simple check to ensure API key is valid (Fix for GenerateContentConfig error)
    response = model.generate_content("Hi") 
    if not response.text:
         raise Exception("API key check failed to return text.")
         
    print("STATUS: Gemini API key successful.")
except Exception as e:
    print("\n\n🚨 CRITICAL ERROR 3: GEMINI API KEY FAILED 🚨")
    print(f"Error: {e}")
    print("FIX: GEMINI_API_KEY (Google AI Studio Key) check karein. Key galat ho sakti hai ya quota khatam ho gaya hoga.")
    sys.exit(1)


# --- HELPERS (Database Functions) ---

async def get_ai_status():
    """Fetches the current AI mode status from MongoDB."""
    status = await status_collection.find_one({"_id": "main_status"})
    return status.get("active", False) if status else False

async def set_ai_status(active: bool):
    """Sets the AI mode status in MongoDB."""
    await status_collection.update_one(
        {"_id": "main_status"}, 
        {"$set": {"active": active}}, 
        upsert=True
    )

async def get_my_style():
    """Fetches past user messages to define the AI's speaking style."""
    cursor = msg_collection.find({}).sort("_id", -1).limit(30)
    messages = await cursor.to_list(length=30)
    if not messages:
        return "Speak casually and shortly in Hinglish."
    return "\n".join([m['text'] for m in messages if 'text' in m])

# --- 4. LEARNING (Messages Save Karna) ---
@app.on_message(filters.me & ~filters.service)
async def learn_handler(client, message):
    """Saves user's outgoing messages to MongoDB to learn personality."""
    if message.text and not message.text.startswith("."): 
        await msg_collection.insert_one({
            "text": message.text,
            "date": message.date
        })

# --- 5. CONTROLS (.ai on / .ai off) ---
@app.on_message(filters.me & filters.command("ai", prefixes="."))
async def mode_handler(client, message):
    """Toggles the AI Ghost Mode."""
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

# --- 6. AUTO REPLY HANDLER ---
@app.on_message(
    ~filters.me & ~filters.bot & ~filters.service & 
    (filters.private | filters.mentioned | filters.reply)
)
async def auto_reply(client, message):
    """Handles incoming messages and generates AI replies when mode is ON."""
    is_active = await get_ai_status()
    if not is_active:
        return

    # Group Protection Logic
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        is_relevant = False
        if message.mentioned:
            is_relevant = True
        elif message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.is_self:
            is_relevant = True
        
        if not is_relevant:
            return

    # Action: Show typing status
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    
    # 1. Load style
    my_style = await get_my_style()
    
    # 2. Context
    incoming = message.text or "[Media/Sticker sent. Respond naturally.]"
    sender_name = message.from_user.first_name if message.from_user else "Unknown User"

    # 3. Prompt Engineering (The personality injection)
    prompt = f"""
    You are roleplaying as ME (The user). You are currently offline, handling chats via AI.
    
    **My Past Messages (Copy this style, tone, and language):**
    {my_style}
    
    **Context:**
    - I am currently away.
    - User '{sender_name}' sent: "{incoming}"
    
    **Instructions:**
    - Reply exactly like I would.
    - Keep it short (1-2 sentences), casual, and use Hinglish/Hindi as per my past messages.
    - Do NOT mention you are an AI or bot.
    
    **Reply to the user:**
    """
    
    try:
        response = model.generate_content(prompt)
        reply_text = response.text.strip()
        
        await asyncio.sleep(2) # Human delay for realism
        
        # Send reply
        await message.reply_text(reply_text)
            
    except Exception as e:
        print(f"AI Response Generation Error (Gemini): {e}")

# --- START BOT ---
print("\n--- STARTING BOT LISTENER ---")

try:
    print("STATUS: Pyrogram listener shuru...")
    app.run()
    
# Agar Pyrogram chalu hone ke baad turant ruk jaye (most likely Session String ka error)
except Exception as e: 
    print("\n\n🚨 CRITICAL ERROR 4: PYROGRAM RUNTIME FAILED 🚨")
    print(f"Error: {e}")
    print("FIX: Bot chalu hone ke baad turant band ho gaya. Session String ya API/HASH check karein.")


