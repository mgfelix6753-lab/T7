import time
import telebot

TOKEN = "9195845034:AAHuAFvtn0V9-OF9chD8F5IASBVM3EtBUQg"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name or ""
    username = message.from_user.username
    
    full_name = f"{first_name} {last_name}".strip()
    username_str = f"@{username}" if username else "Username မရှိပါ"
    
    reply_text = (
        f"👋 မင်္ဂလာပါ!\n\n"
        f"🆔 **Your ID:** `{user_id}`\n\n"
        f"👤 **Telegram Name:** {full_name}\n\n"
        f"🏷 **Telegram Username:** {username_str}"
    )
    bot.reply_to(message, reply_text, parse_mode="Markdown")

# Error တက်ပြီး Bot မရပ်သွားစေရန် infinite loop ဖြင့် အမြဲ run ထားခြင်း
while True:
    try:
        print("Bot စတင်အလုပ်လုပ်နေပါပြီ...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Error ဖြစ်သွားပါသည်: {e}")
        print("5 စက္ကန့်အတွင်း Bot ကို ပြန်စတင်နေပါသည်...")
        time.sleep(5)
