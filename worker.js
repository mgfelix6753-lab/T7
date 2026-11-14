export default {
  async fetch(request, env, ctx) {
    // Bot Token ကို ဒီနေရာမှာ တိုက်ရိုက်ထည့်ပါ
    const BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE';

    if (request.method !== 'POST') {
      return new Response('Bot is running!', { status: 200 });
    }

    try {
      const update = await request.json();

      if (update.message && update.message.text) {
        const text = update.message.text.trim();
        
        if (text.startsWith('/start')) {
          const chatId = update.message.chat.id;
          const userId = update.message.from.id;
          
          const firstName = update.message.from.first_name || '';
          const safeFirstName = escapeHTML(firstName);

          const username = update.message.from.username 
            ? `@${update.message.from.username}` 
            : 'No username';

          // သင်တောင်းဆိုထားသော ပုံစံအတိုင်း
          const responseText = `${username}\n` +
                               `Id: <code>${userId}</code>\n` +
                               `First: ${safeFirstName}`;

          await sendTelegramMessage(BOT_TOKEN, chatId, responseText);
        }
      }

      return new Response('OK', { status: 200 });
    } catch (err) {
      return new Response('Error: ' + err.message, { status: 500 });
    }
  },
};

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
