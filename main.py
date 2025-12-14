import os
import asyncio
import re
import sys
from pyrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

print("🔥 SUDEEP BOT - DEBUG MODE 🔥")

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
MONGO_URL = os.getenv("MONGO_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- CLIENT ---
app = Client(
    "sudeep_debug",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

# --- DB ---
mongo = AsyncIOMotorClient(MONGO_URL)
db = mongo.sudeep_ai
msgs = db.messages
status_db = db.status

# --- GEMINI ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- SIMPLE STATUS ---
AI_MODE = False  # In-memory status

# --- 1. ALL MESSAGES CATCHER (DEBUG) ---
@app.on_message(filters.all)
async def catch_all(client, message):
    """Saare messages log karo debugging ke liye"""
    
    # Message info
    sender = "ME" if message.from_user and message.from_user.is_self else "OTHER"
    chat_type = "PRIVATE" if message.chat.type == enums.ChatType.PRIVATE else "GROUP"
    
    print(f"\n📥 [{chat_type}] [{sender}] >> {message.text if message.text else '[Media/Sticker]'}")
    
    # Agar maine bheja hai
    if message.from_user and message.from_user.is_self:
        print(f"   🎯 THIS IS MY MESSAGE!")
        
        # Command check
        if message.text and message.text.startswith('.'):
            print(f"   💻 DETECTED COMMAND: {message.text}")
            
            # .ai on/off handle
            if message.text.lower().startswith('.ai'):
                parts = message.text.lower().split()
                if len(parts) > 1:
                    cmd = parts[1]
                    
                    global AI_MODE
                    if cmd == "on":
                        AI_MODE = True
                        print("   🟢 AI MODE SET TO: ON")
                        await message.edit("✅ **AI GHOST ACTIVATED!**\n\nAb mai teri jagah baat karunga. Koi message bhejo test karne ke liye!")
                        
                    elif cmd == "off":
                        AI_MODE = False
                        print("   🔴 AI MODE SET TO: OFF")
                        await message.edit("❌ **AI GHOST DEACTIVATED**")
                        
                    elif cmd == "status":
                        await message.edit(f"🤖 **AI Status:** {'🟢 ON' if AI_MODE else '🔴 OFF'}")
                        
                    elif cmd == "test":
                        await message.reply_text("Test reply from AI!")

# --- 2. AUTO REPLY (WORKING VERSION) ---
@app.on_message(
    ~filters.me & 
    ~filters.bot & 
    filters.private  # Temporary: Sirf DMs mein reply karo
)
async def auto_reply_simple(client, message):
    """Sirf DMs ka reply karo"""
    
    print(f"\n💌 DM from {message.from_user.first_name}: {message.text[:50] if message.text else '[Media]'}")
    print(f"   AI MODE: {'ON' if AI_MODE else 'OFF'}")
    
    if not AI_MODE:
        print("   ❌ AI is OFF, ignoring...")
        return
    
    # Typing show karo
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    
    # Simple prompt
    sender = message.from_user.first_name if message.from_user else "Bhai"
    msg = message.text or "Kuch bheja hai"
    
    prompt = f"""Reply as Sudeep would on WhatsApp.

{sender} ne message bheja: "{msg}"

Sudeep ka reply (1-2 lines, Hinglish mein, casual):"""
    
    try:
        print("   🤖 Generating reply...")
        response = model.generate_content(prompt)
        reply = response.text.strip() if response.text else "Arey, baad mein baat karte hain."
        
        # Clean
        reply = re.sub(r'\*|\#', '', reply)
        reply = re.sub(r'\n', ' ', reply).strip()
        
        if len(reply) < 3:
            reply = "Hmm... okay."
        
        print(f"   💭 Reply: {reply}")
        
        # Delay
        await asyncio.sleep(1)
        
        # Send
        await message.reply_text(reply)
        print("   ✅ Reply sent!")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        await message.reply_text("Arey, baad mein baat karte hain yaar.")

# --- BOT START ---
print("\n" + "="*60)
print("🤖 **SUDEEP AI BOT - DEBUG VERSION**")
print("="*60)
print("\n📱 **TELEGRAM MEIN KARO YE STEPS:**")
print("1. Kisi bhi chat mein type karo: `.ai on`")
print("2. Console pe 'AI MODE SET TO: ON' dikhega")
print("3. Kisi friend ko bolo tumhe DM kare")
print("4. AI reply karega")
print("\n🔄 **Testing:**")
print("- `.ai on` -> Activate")
print("- `.ai off` -> Deactivate")
print("- `.ai status` -> Check")
print("="*60 + "\n")

if __name__ == "__main__":
    app.run()
