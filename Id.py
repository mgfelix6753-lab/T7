import os
import time
from threading import Thread
import telebot
from flask import Flask

TOKEN = "9195845034:AAHuAFvtn0V9-OF9chD8F5IASBVM3EtBUQg"
bot = telebot.TeleBot(TOKEN)

# Render အတွက် Web Server (Port ဖွင့်ရန် Flask သုံးခြင်း)
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)


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
      f"🆔 **Telegram Chat ID:** `{user_id}`\n\n"
      f"👤 **Telegram Name:** {full_name}\n\n"
      f"🏷 **Telegram Username:** {username_str}"
  )
  
  # Reply လုပ်မည့်အစား Chat ID ဆီသို့ သက်သက်ပို့ရန် send_message ကို သုံးခြင်း
  bot.send_message(message.chat.id, reply_text, parse_mode="Markdown")


# Background မှာ Flask Server ကို အရင် run မည်
if __name__ == '__main__':
  t = Thread(target=run_web)
  t.start()

  # Bot ကို Error တက်ရင် ပြန်စနေအောင် infinite loop ဖြင့် run မည်
  while True:
    try:
      print('Bot စတင်အလုပ်လုပ်နေပါပြီ...')
      bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
      print(f'Error ဖြစ်သွားပါသည်: {e}')
      time.sleep(5)
        
