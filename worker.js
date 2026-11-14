export default {
  async fetch(request, env, ctx) {
    if (request.method !== 'POST') {
      return new Response('Bot is running!', { status: 200 });
    }

    try {
      const update = await request.json();

      if (update.message && update.message.text === '/start') {
        const chatId = update.message.chat.id;
        const userId = update.message.from.id;
        
        // First Name (နာမည်အပြည့်အစုံလိုချင်ရင် last_name ပါ ပေါင်းထည့်နိုင်ပါတယ်)
        const firstName = update.message.from.first_name || '';
        const safeFirstName = escapeHTML(firstName);

        // Username စစ်ဆေးခြင်း
        const username = update.message.from.username 
          ? `@${update.message.from.username}` 
          : 'No username';

        // သင်လိုချင်တဲ့ စာသားပုံစံအတိုင်း စီစဉ်ခြင်း
        const responseText = `${username}\n` +
                             `Id: <code>${userId}</code>\n` +
                             `First: ${safeFirstName}`;

        await sendTelegramMessage(env.BOT_TOKEN, chatId, responseText);
      }

      return new Response('OK', { status: 200 });
    } catch (err) {
      return new Response('Error: ' + err.message, { status: 500 });
    }
  },
};

// နာမည်ထဲမှာ <, >, & စတဲ့ သင်္ကေတတွေပါရင် HTML Error မတက်အောင် ကာကွယ်ပေးတဲ့ Function
function escapeHTML(str) {
  return str.replace(/[&<>'"]/g, 
    tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag])
  );
}

async function sendTelegramMessage(token, chatId, text) {
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: 'HTML',
    }),
  });
}
