import logging
import random
from datetime import datetime, timedelta
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- AYARLAR VE TOKENLAR ---
TELEGRAM_TOKEN = "8363449973:AAFWPie-yjpJn1vHQxSKeykVKjq2Pt3Lo1k"
XAI_API_KEY = "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"

XAI_URL = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL = "llama-3.1-8b-instant"

USER_SCORES = {}           
DAILY_KING = {}            

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SMART_PROMPT = """
Sen Viyana AI Bot'usun. Yapımcın Ehed'dir.
Kullanıcının sorusuna veya mesajına SADECE aşağıdaki 3 dilde ayrı ayrı yanıt ver:

Türkçe: [Yanıtın]
Rusça: [Yanıtın]
Almanca: [Yanıtın]
"""

TRANSLATION_SYSTEM_PROMPT = """
Sen profesyonel ve insan gibi doğal çeviri yapan bir yapay zekasın.
Görevin sana verilen metni analiz etmek ve şu kurallara %100 uymaktır:

1. Metnin yazıldığı dili tespit et (Türkçe, Rusça veya Almanca).
2. Metni, YAZILDIĞI DİL HARİÇ diğer 2 dile çevir.
   - Eğer Türkçe yazıldıysa ➔ SADECE Rusça ve Almanca çevir.
   - Eğer Rusça yazıldıysa ➔ SADECE Türkçe ve Almanca çevir.
   - Eğer Almanca yazıldıysa ➔ SADECE Türkçe ve Rusça çevir.
3. KESİNLİKLE metnin yazıldığı kendi dilini cevaba ekleme!
4. Rusça çevirileri KESİNLİKLE gerçek Kiril alfabesiyle yaz (Latin okunuşu yazma).
5. KESİNLİKLE [...] veya (...) gibi parantezler, köşeli parantezler kullanma.
6. "Dil 1", "Çeviri" gibi ekstra kelimeler yazma. Direct başlık at.

Format örneği (Türkçe yazılmış bir mesaj için):
Rusça: [Buraya gerçek Kiril Rusça]
Almanca: [Buraya Almanca]
"""

async def query_grok(prompt: str, system_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY.strip()}",
        "Content-Type": "application/json",
    }
    data = {
        "model": GROK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(XAI_URL, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Groq API Error Status: {response.status_code}")
            raise Exception(f"API_ERROR_{response.status_code}")

def add_point(chat_id: int, user):
    if user.is_bot: return
    if chat_id not in USER_SCORES: USER_SCORES[chat_id] = {}
    uid = user.id
    if uid not in USER_SCORES[chat_id]:
        USER_SCORES[chat_id][uid] = {"name": user.first_name, "points": 0, "messages": 0}
    USER_SCORES[chat_id][uid]["points"] += random.randint(5, 15)
    USER_SCORES[chat_id][uid]["messages"] += 1
    USER_SCORES[chat_id][uid]["name"] = user.first_name

def get_level(points: int) -> str:
    if points < 100: return "🥉 Çaylak"
    if points < 500: return "🥈 Bronz"
    if points < 1500: return "🥇 Gümüş"
    if points < 3000: return "💎 Altın"
    if points < 7000: return "👑 Viyana Savaşçısı"
    return "🔥 Viyana Efsanesi"

# --- OTOMATİK ÇEVİRİ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.effective_message
        if not message or not message.text: return
        text = message.text.strip()
        chat_id = message.chat_id
        user = update.effective_user

        if user.is_bot or text.startswith("/"):
            return

        add_point(chat_id, user)
        bot_username = context.bot.username or ""

        # Bot Etiketlendiyse
        if bot_username and f"@{bot_username}".lower() in text.lower():
            clean_text = text.replace(f"@{bot_username}", "").strip()
            if not clean_text: return
            await message.chat.send_action(action="typing")
            ans = await query_grok(clean_text, SMART_PROMPT)
            await message.reply_text(ans)
            return

        # Çok kısa kelimeler ve linkler filtrelenir
        words = text.split()
        if len(words) < 2 or len(text) < 5 or "http" in text:
            return

        translated = await query_grok(text, TRANSLATION_SYSTEM_PROMPT)
        if translated and len(translated) > 3:
            await message.reply_text(translated)

    except Exception as e:
        logger.error(f"Handle message hatası: {e}")

# --- KOMUTLAR ---
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🤖 **VİYANA AI**\n👑 *Creator: Ehed*\n\nBot aktif ve çalışıyor!"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("🏆 Henüz puan yok!")
        return
    sorted_users = sorted(scores.values(), key=lambda x: x["points"], reverse=True)[:10]
    text = "🏆 **PUAN SIRALAMASI** 🏆\n\n"
    for idx, u in enumerate(sorted_users, 1):
        lvl = get_level(u["points"])
        text += f"{idx}. **{u['name']}** — {u['points']} Puan ({lvl})\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# --- ÇÖKMEYEN BAŞLATMA YAPISI ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("puan", cmd_siralama))
    app.add_handler(CommandHandler("siralama", cmd_siralama))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot başlatılıyor...")
    app.run_polling(drop_pending_updates=True)
