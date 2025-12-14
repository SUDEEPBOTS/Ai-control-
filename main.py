import os
import asyncio
import re
import sys
from pyrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient
import google.generativeai as genai
from dotenv import load_dotenv

# Load env
load_dotenv()

# --- DEBUG INFO ---
print("="*50)
print("🚀 SUDEEP AI BOT STARTING...")
print("="*50)

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
MONGO_URL = os.getenv("MONGO_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Validate
if not all([API_ID, API_HASH, SESSION_STRING, MONGO_URL, GEMINI_API_KEY]):
    print("❌ MISSING ENVIRONMENT VARIABLES!")
    sys.exit(1)

print(f"✅ API_ID: {API_ID}")
print(f"✅ API_HASH: {len(API_HASH)} chars")
print(f"✅ SESSION: {len(SESSION_STRING)} chars")
print(f"✅ MONGO: {MONGO_URL[:30]}...")
print(f"✅ GEMINI: {GEMINI_API_KEY[:10]}...")
print("="*50)

# --- CLIENT SETUP ---
try:
    app = Client(
        "sudeep_session",
        api_id=int(API_ID),
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )
    print("✅ Pyrogram Client Ready")
except Exception as e:
    print(f"❌ Client Error: {e}")
    sys.exit(1)

# --- DATABASE ---
try:
    mongo = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    # Test connection
    mongo.admin.command('ping')
    db = mongo.sudeep_db
    messages_db = db.messages
    status_db = db.status
    print("✅ MongoDB Connected")
except Exception as e:
    print(f"❌ MongoDB Error: {e}")
    sys.exit(1)

# --- GEMINI ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    # Test Gemini
    test = model.generate_content("Hello")
    if test.text:
        print("✅ Gemini API Working")
    else:
        raise Exception("No response from Gemini")
except Exception as e:
    print(f"❌ Gemini Error: {e}")
    sys.exit(1)

# --- SIMPLE STATUS FUNCTIONS ---
async def is_ai_on():
    """Check if AI is ON"""
    try:
        doc = await status_db.find_one({"_id": "ai_mode"})
        if doc:
            return doc.get("on", False)
        return False
    except:
        return False

async def set_ai_mode(on_off: bool):
    """Set AI mode"""
    try:
        await status_db.update_one(
            {"_id": "ai_mode"},
            {"$set": {"on": on_off}},
            upsert=True
        )
        return True
    except:
        return False

# --- 1. SAVE MESSAGES ---
@app.on_message(filters.me & ~filters.service)
async def save_my_messages(client, message):
    """Save Sudeep's messages"""
    try:
        if message.text and len(message.text.strip()) > 5:
            if not message.text.startswith('.'):
                await messages_db.insert_one({
                    "text": message.text,
                    "time": message.date,
                    "chat_id": message.chat.id
                })
                # Keep only last 50 messages
                count = await messages_db.count_documents({})
                if count > 50:
                    await messages_db.delete_one({})
    except Exception as e:
        print(f"Save Error: {e}")

# --- 2. AI CONTROL COMMAND (FIXED) ---
@app.on_message(filters.me & filters.text)
async def handle_ai_command(client, message):
    """Handle .ai commands"""
    
    # Debug print
    print(f"\n📩 Received: {message.text}")
    
    # Check if it's a command
    if message.text and message.text.startswith('.'):
        cmd_parts = message.text.lower().split()
        
        if cmd_parts[0] == ".ai" and len(cmd_parts) > 1:
            action = cmd_parts[1]
            
            if action == "on":
                success = await set_ai_mode(True)
                if success:
                    await message.edit("✅ **AI GHOST MODE: ACTIVATED**\n\nAb mai tere jaise reply karunga jab tu offline hoga.\nKisi ko pata nahi chalega! 😎")
                    print("🟢 AI Mode: ON")
                else:
                    await message.edit("❌ Failed to activate")
                    
            elif action == "off":
                success = await set_ai_mode(False)
                if success:
                    await message.edit("❌ **AI GHOST MODE: DEACTIVATED**\n\nAb tu khud baat karega.")
                    print("🔴 AI Mode: OFF")
                else:
                    await message.edit("❌ Failed to deactivate")
                    
            elif action == "status":
                status = await is_ai_on()
                await message.edit(f"📊 **AI STATUS:** {'🟢 ON' if status else '🔴 OFF'}")
                
            elif action == "clear":
                await messages_db.delete_many({})
                await message.edit("🗑️ **Messages cleared**")
                
            elif action == "test":
                await message.edit("🤖 **Bot is alive!**")
                
            else:
                await message.edit("❌ **Usage:** `.ai on` / `.ai off` / `.ai status`")

# --- 3. AUTO REPLY (SIMPLIFIED) ---
@app.on_message(
    ~filters.me & 
    ~filters.bot & 
    ~filters.service &
    (filters.private | filters.mentioned | (filters.group & filters.reply))
)
async def reply_as_sudeep(client, message):
    """Auto reply when AI mode is ON"""
    
    # Debug
    print(f"\n💬 New message from: {message.from_user.first_name if message.from_user else 'Unknown'}")
    print(f"   Text: {message.text[:50] if message.text else '[Media]'}")
    
    # Check AI mode
    ai_active = await is_ai_on()
    print(f"   AI Mode: {'ON' if ai_active else 'OFF'}")
    
    if not ai_active:
        return
    
    # Group protection
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not (message.mentioned or 
                (message.reply_to_message and 
                 message.reply_to_message.from_user and 
                 message.reply_to_message.from_user.is_self)):
            print("   ❌ Not relevant (no mention/reply)")
            return
    
    # Show typing
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    
    # Get sender info
    sender = message.from_user.first_name if message.from_user else "Bhai"
    msg_text = message.text or "Sent something"
    
    # SIMPLE PROMPT - No complications
    prompt = f"""You are Sudeep. You're replying to a message on WhatsApp.

Message from {sender}: "{msg_text}"

Reply as Sudeep would:
- Use Hinglish (Hindi+English mix)
- Be casual and friendly
- 1-2 sentences only
- Don't say you're AI
- Example: "Arey yaar, busy hu thodi der. Baad mein baat karte hain."

Your reply:"""
    
    try:
        print("   🤖 Generating AI response...")
        
        # Generate response
        response = model.generate_content(prompt)
        reply = response.text.strip() if response.text else ""
        
        # Clean response
        if not reply or len(reply) < 3:
            reply = "Arey, baad mein baat karte hain yaar."
        
        # Remove any weird formatting
        reply = re.sub(r'\*+', '', reply)
        reply = re.sub(r'\n+', ' ', reply)
        reply = reply.strip()
        
        print(f"   💭 AI Reply: {reply[:60]}...")
        
        # Small delay
        await asyncio.sleep(1)
        
        # Send reply
        await message.reply_text(reply)
        print("   ✅ Reply sent!")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        # Fallback
        fallbacks = [
            "Arey bhai, busy hu. Baad mein?",
            "Hmm... okay yaar",
            "Sahi hai",
            "Kya bol raha hai?"
        ]
        import random
        await asyncio.sleep(1)
        await message.reply_text(random.choice(fallbacks))

# --- STARTUP MESSAGE ---
@app.on_message(filters.me & filters.command("start"))
async def start_cmd(client, message):
    await message.edit("""
🤖 **SUDEEP AI GHOST BOT**

**Commands:**
`.ai on` - Activate AI mode
`.ai off` - Deactivate
`.ai status` - Check status
`.ai test` - Test bot
`.ai clear` - Clear saved messages

**How to use:**
1. Chat normally (I'll learn your style)
2. Type `.ai on` when you want AI to reply
3. When offline, AI will reply as you
4. Type `.ai off` to deactivate

Bot is ready! ✨
    """)

# --- BOT INFO ON START ---
print("\n" + "="*50)
print("✅ BOT IS RUNNING!")
print("="*50)
print("\n📱 **NEXT STEPS:**")
print("1. Open Telegram")
print("2. In ANY chat, type: .ai on")
print("3. Check console for confirmation")
print("4. Ask someone to message you")
print("5. AI will reply as Sudeep!")
print("\nType `.start` for help in Telegram")
print("="*50 + "\n")

# Run bot
if __name__ == "__main__":
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Runtime Error: {e}")
