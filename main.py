import logging
import random
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- PROMPTLAR ---
SMART_PROMPT = """
Sen Viyana AI Bot'usun. Yapımcın Ehed'dir.
Kullanıcı seninle konuştuğunda samimi, doğal ve eğlenceli cevap ver.
Cevabını 3 dilde bayraklarla yaz:
🇹🇷 [Türkçe Cevabın]
🇷🇺 [Rusça Cevabın]
🇩🇪 [Almanca Cevabın]
"""

TRANSLATION_SYSTEM_PROMPT = """
Sen ana dili düzeyinde Türkçe, Rusça ve Almanca bilen profesyonel bir mütercim-tercümansın.
Görevin kelimesi kelimesine çeviri yapmak DEĞİL; cümlenin anlamını ve konuşma diline uygunluğunu en üst düzey kalitede aktarmaktır.

Sana verilen mesajın dilini tespit et ve ŞU KESİN KURALLARA UY:

1. Mesaj TÜRKÇE ise:
   - KESİNLİKLE Türkçe çeviri veya yanıt verme!
   - KESİNLİKLE "Rusça:", "Almanca:" gibi kelimeler/başlıklar YAZMA!
   - Format:
   🇷🇺 [En doğal Rusça çeviri - Gerçek Kiril Alfabesiyle]
   🇩🇪 [En doğal Almanca çeviri]

2. Mesaj ALMANCA ise:
   - KESİNLİKLE Almanca çeviri veya yanıt verme!
   - KESİNLİKLE "Türkçe:", "Rusça:" gibi kelimeler/başlıklar YAZMA!
   - Format:
   🇹🇷 [En doğal Türkçe çeviri]
   🇷🇺 [En doğal Rusça çeviri - Gerçek Kiril Alfabesiyle]

3. Mesaj RUSÇA ise:
   - KESİNLİKLE Rusça çeviri veya yanıt verme!
   - KESİNLİKLE "Türkçe:", "Almanca:" gibi kelimeler/başlıklar YAZMA!
   - Format:
   🇹🇷 [En doğal Türkçe çeviri]
   🇩🇪 [En doğal Almanca çeviri]

YASAKLAR:
- "Türkçe:", "Rusça:", "Almanca:", "Dil:", "Çeviri:" gibi kelimeleri ASLA KULLANMA. SADECE BAYRAK EMOJİSİ KULLAN.
- Parantez [...] veya (...) yazma.
- Rusça için asla okunuş/Latin harfi yazma, tamamen Kiril yaz.
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

# --- BÜTÜN EĞLENCE KOMUTLARI ---
async def cmd_fun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.split()[0].replace("/", "").split("@")[0].lower()
    args = " ".join(context.args) if context.args else ""
    
    prompts = {
        "burc": f"Kullanıcı {args if args else 'genel'} için eğlenceli ve komik bir günlük burç yorumu istiyor.",
        "fal": "Kullanıcı için eğlenceli, komik ve biraz da gizemli bir kahve falı yorumu yap.",
        "joke": "Türkçe, Rusça ve Almanca kültürüne uygun çok komik ve eğlenceli bir fıkra/espri anlat.",
        "sarcasm": f"Şu mesaja aşırı laf sokucu, alaycı ve komik (sarkastik) bir cevap ver: '{args}'",
        "kader": "Kader çarkını çevir! Kullanıcının bugünkü şansını, uğurlu sayısını ve günün tavsiyesini söyle.",
        "dedikodu": "Sanki bir magazin muhabirisin gibi grup için komik ve uydurma bir magazin haberi/dedikodusu üret.",
        "kral": "Günün Kralını ilan et! Ona övgüler yağdır ve krallığına uygun komik bir ferman yayınla.",
        "kurban": "Günün Kurbanını seç! Onunla esprili bir şekilde dalga geç ama kırmadan eğlendir.",
        "bilgi": "Kullanıcıya hiç duymadığı çok ilginç, şaşırtıcı ve eğlenceli bir genel kültür bilgisi ver."
    }

    p = prompts.get(cmd, "Eğlenceli bir cevap ver.")
    await update.message.chat.send_action(action="typing")
    ans = await query_grok(p, SMART_PROMPT)
    await update.message.reply_text(ans)

# --- TEMEL KOMUTLAR ---
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **VİYANA AI BİLGİ MENÜSÜ**\n"
        "👑 *Creator: Ehed*\n\n"
        "📌 **Kullanılabilir Komutlar:**\n"
        "• `/burc <burcunuz>` - Günlük Burç Yorumu\n"
        "• `/fal` - Kahve Falı\n"
        "• `/joke` - Espri / Fıkra\n"
        "• `/sarcasm <mesaj>` - Alaycı / Sarkastik Cevap\n"
        "• `/kader` - Kader Çarkı\n"
        "• `/dedikodu` - Magazin Haberi\n"
        "• `/kral` - Günün Kralı\n"
        "• `/kurban` - Günün Kurbanı\n"
        "• `/bilgi` - Bilgi Yarışması / Genel Kültür\n"
        "• `/siralama` veya `/puan` - Puan Sıralaması\n\n"
        "🌐 *Otomatik Bayraklı Çeviri Modu Aktif!*"
    )
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
        text += f"{idx}. **{u['name']}** — {u['points']} Puan\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# --- MESAJ İŞLEME VE OTOMATİK ÇEVİRİ ---
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

        # Filtreler (Kısa kelimeler ve linkler)
        words = text.split()
        if len(words) < 2 or len(text) < 4 or "http" in text:
            return

        translated = await query_grok(text, TRANSLATION_SYSTEM_PROMPT)
        if translated and len(translated) > 3:
            await message.reply_text(translated)

    except Exception as e:
        logger.error(f"Handle message hatası: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Temel Komutlar
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("puan", cmd_siralama))
    app.add_handler(CommandHandler("siralama", cmd_siralama))

    # Tüm Eğlence Komutları
    fun_commands = ["burc", "fal", "joke", "sarcasm", "kader", "dedikodu", "kral", "kurban", "bilgi"]
    for c in fun_commands:
        app.add_handler(CommandHandler(c, cmd_fun))

    # Mesaj Dinleyici
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Viyana AI Bot (Tüm Özellikler Aktif) Başlatıldı...")
    app.run_polling(drop_pending_updates=True)
