import os
import asyncio
import re
import sys
from pyrogram import Client, filters, enums
from motor.motor_asyncio import AsyncIOMotorClient
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

print("🔥 SUDEEP AI - ULTIMATE FIX 🔥")

# --- CONFIG ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
MONGO_URL = os.getenv("MONGO_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- CLIENT ---
app = Client(
    "sudeep_final",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

# --- SIMPLE IN-MEMORY STATUS ---
AI_ACTIVE = False
MY_USER_ID = None  # Tumhara user ID store karenge

# --- GEMINI ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 1. GET MY USER ID ON START ---
@app.on_message(filters.me)
async def get_my_id(client, message):
    """Pehle message se apna ID le lo"""
    global MY_USER_ID
    if message.from_user:
        MY_USER_ID = message.from_user.id
        print(f"✅ My User ID: {MY_USER_ID}")

# --- 2. AI CONTROL COMMAND ---
@app.on_message(filters.me & filters.text)
async def handle_commands(client, message):
    """Handle .ai commands"""
    global AI_ACTIVE
    
    if message.text.startswith('.'):
        print(f"\n🎮 COMMAND: {message.text}")
        
        if message.text.lower().startswith('.ai'):
            parts = message.text.lower().split()
            
            if len(parts) > 1:
                cmd = parts[1]
                
                if cmd == "on":
                    AI_ACTIVE = True
                    print("🟢 AI MODE: ON")
                    await message.edit("""
✅ **AI GHOST ACTIVATED!**

Ab mai teri jagah reply karunga jab:
1. Koi tumhe DM karega
2. Koi tumhe group mein tag karega
3. Koi tumhare message pe reply karega

**Test karne ke liye:** Kisi friend ko bolo tumhe "Hi" bhejne! 🤖
                    """)
                    
                elif cmd == "off":
                    AI_ACTIVE = False
                    print("🔴 AI MODE: OFF")
                    await message.edit("❌ **AI GHOST DEACTIVATED**")
                    
                elif cmd == "status":
                    status_msg = "🟢 **AI STATUS: ON**" if AI_ACTIVE else "🔴 **AI STATUS: OFF**"
                    await message.edit(status_msg)
                    
                elif cmd == "test":
                    # Test reply
                    await message.reply_text("🤖 Test successful! AI is working.")

# --- 3. AUTO REPLY (PERFECTED) ---
@app.on_message()
async def handle_all_messages(client, message):
    """Saare messages handle karo"""
    global AI_ACTIVE, MY_USER_ID
    
    # Skip bots and service messages
    if message.from_user and message.from_user.is_bot:
        return
    
    # Debug info
    sender_name = message.from_user.first_name if message.from_user else "Unknown"
    chat_type = "DM" if message.chat.type == enums.ChatType.PRIVATE else "GROUP"
    
    print(f"\n📨 [{chat_type}] {sender_name}: {message.text[:40] if message.text else '[Media]'}")
    
    # CASE 1: Agar yeh message TUMNE bheja hai (commands handle)
    if message.from_user and message.from_user.is_self:
        print("   👤 This is MY message")
        # Commands already handled above
        return
    
    # CASE 2: Agar yeh incoming message hai
    print(f"   🤖 AI Status: {'ON' if AI_ACTIVE else 'OFF'}")
    
    if not AI_ACTIVE:
        print("   ❌ AI is OFF, ignoring...")
        return
    
    # Check if message is for us
    should_reply = False
    
    # Rule 1: Direct DM
    if message.chat.type == enums.ChatType.PRIVATE:
        should_reply = True
        print("   💌 This is a DM, will reply")
    
    # Rule 2: Group mention
    elif message.mentioned:
        should_reply = True
        print("   📢 Mentioned in group, will reply")
    
    # Rule 3: Reply to our message
    elif message.reply_to_message:
        if (message.reply_to_message.from_user and 
            message.reply_to_message.from_user.is_self):
            should_reply = True
            print("   ↩️ Replying to my message, will reply")
    
    if not should_reply:
        print("   ⏭️ Not relevant, skipping...")
        return
    
    # --- GENERATE REPLY ---
    print("   ⏳ Generating AI reply...")
    await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
    
    # Simple prompt
    msg_text = message.text or "Kuch bheja hai"
    
    prompt = f"""You are Sudeep. You're replying to a message.

Message: "{msg_text}"

Reply as Sudeep (young Indian guy):
- Use casual Hinglish (Hindi+English mix)
- 1-2 sentences only
- Sound natural like WhatsApp chat
- Examples: "Arey yaar!", "Sahi hai bhai", "Kya haal hai?"

Sudeep's reply:"""
    
    try:
        response = model.generate_content(prompt)
        reply_text = response.text.strip() if response.text else ""
        
        # Clean
        if not reply_text:
            reply_text = "Arey, baad mein baat karte hain."
        
        reply_text = re.sub(r'\*|#|`', '', reply_text)
        reply_text = re.sub(r'\n+', ' ', reply_text).strip()
        
        print(f"   💭 AI Reply: {reply_text[:60]}...")
        
        # Small delay
        await asyncio.sleep(1.5)
        
        # Send reply
        await message.reply_text(reply_text)
        print("   ✅ Reply sent successfully!")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        await message.reply_text("Hmm... thodi der mein baat karte hain.")

# --- STARTUP INFO ---
print("\n" + "="*60)
print("🤖 **SUDEEP AI GHOST BOT - READY**")
print("="*60)
print("\n📱 **TELEGRAM MEIN FOLLOW KARO:**")
print("1. Type: .ai on")
print("2. Wait for confirmation message")
print("3. Ask a FRIEND to message you (NOT yourself)")
print("4. AI will reply to their message")
print("\n⚠️ **IMPORTANT:** Friend se message bhejwao, khud se nahi!")
print("="*60 + "\n")

if __name__ == "__main__":
    app.run()
