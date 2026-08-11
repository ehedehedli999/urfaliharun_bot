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

# --- TOKENLAR ---
TELEGRAM_TOKEN = "8363449973:AAFWPie-yjpJn1vHQxSKeykVKjq2Pt3Lo1k"
XAI_API_KEY = "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"

XAI_URL = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL = "llama-3.1-8b-instant"

USER_SCORES = {}
# Dil Çeviri Açma/Kapatma Durumları (Varsayılan: Açık)
LANG_STATUS = {
    "tr": True,
    "ru": True,
    "de": True
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# AŞIRI ZEKİ / DAHİ BOT PROMPT'U
DAHI_BOT_PROMPT = """
Sen Viyana AI'sın. Ehed tarafından en üst düzey yapay zeka teknolojisiyle tasarlandın.
Sen son derece zeki, dahi, derin bilgiye sahip, mantıklı ve kusursuz yanıtlar veren bir yapay zekasın.
Kullanıcı hangi dilde yazdıysa SADECE O DİLDE cevap ver (Türkçe yazdıysa Türkçe, Rusça yazdıysa Rusça, Almanca yazdıysa Almanca).
Asla saçmalama, kısa ve en net/dahi cevabı ver.
"""

# OTOMATİK ÇEVİRİ PROMPT'U
TRANSLATION_SYSTEM_PROMPT = """
Sen ana dili düzeyinde Türkçe, Rusça ve Almanca bilen kusursuz bir mütercim-tercümansın.
Metnin anlamını, ruhunu ve dilbilgisini en üst düzey kalitede çevir.

Sana verilen mesajın dilini tespit et ve ŞU KESİN KURALLARA UY:

1. Mesaj TÜRKÇE ise (eğer Rusça veya Almanca aktifse):
   - KESİNLİKLE Türkçe replay yazma!
   - KESİNLİKLE "Rusça:", "Almanca:" başlıkları YAZMA!
   - Format:
   🇷🇺 [Kusursuz Rusça çeviri - Gerçek Kiril]
   🇩🇪 [Kusursuz Almanca çeviri]

2. Mesaj ALMANCA ise (eğer Türkçe veya Rusça aktifse):
   - KESİNLİKLE Almanca replay yazma!
   - KESİNLİKLE başlık YAZMA!
   - Format:
   🇹🇷 [Kusursuz Türkçe çeviri]
   🇷🇺 [Kusursuz Rusça çeviri - Gerçek Kiril]

3. Mesaj RUSÇA ise (eğer Türkçe veya Almanca aktifse):
   - KESİNLİKLE Rusça replay yazma!
   - KESİNLİKLE başlık YAZMA!
   - Format:
   🇹🇷 [Kusursuz Türkçe çeviri]
   🇩🇪 [Kusursuz Almanca çeviri]

GENEL YASAKLAR:
- "Türkçe:", "Rusça:", "Almanca:" kelimelerini ASLA yazma. Sadece bayrak emoji kullan.
- Parantez [...] veya (...) kullanma.
- Aktif olmayan dili çıktıya dahil etme.
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
        "temperature": 0.1,
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

# --- DİL AÇMA / KAPATMA KOMUTLARI ---
async def cmd_toggle_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.split()[0].replace("/", "").split("@")[0].lower()
    if cmd == "turkce":
        LANG_STATUS["tr"] = not LANG_STATUS["tr"]
        st = "Açıldı / On" if LANG_STATUS["tr"] else "Kapatıldı / Off"
        msg = f"🇹🇷 Türkçe Çeviri: {st}"
    elif cmd == "rusca":
        LANG_STATUS["ru"] = not LANG_STATUS["ru"]
        st = "Açıldı / On" if LANG_STATUS["ru"] else "Kapatıldı / Off"
        msg = f"🇷🇺 Rusça Çeviri: {st}"
    elif cmd == "almanca":
        LANG_STATUS["de"] = not LANG_STATUS["de"]
        st = "Açıldı / On" if LANG_STATUS["de"] else "Kapatıldı / Off"
        msg = f"🇩🇪 Almanca Çeviri: {st}"
    else:
        return
    await update.message.reply_text(msg)

# --- 3 DİLDE KOMUT CEVAPLARI PROMPT'U ---
COMMAND_3LANG_PROMPT = """
Aşağıdaki görevi veya çıktıyı 3 dilde (Türkçe, Rusça, Almanca) bayraklı olarak hazırla:
🇹🇷 [Türkçe İçerik]
🇷🇺 [Rusça İçerik]
🇩🇪 [Almanca İçerik]
"""

# --- KALAN KOMUTLAR ---
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = "Hakkımda metnini bas: Ben Viyana Ai Yapay zeka botu Ehed Tarafından Tasarlandım en Üst düzey Ai Texnolojisiyle calisiyorum."
    await update.message.chat.send_action(action="typing")
    ans = await query_grok(p, COMMAND_3LANG_PROMPT)
    await update.message.reply_text(ans)

async def cmd_burc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args) if context.args else "genel"
    p = f"Kullanıcının belirttiği burç ({args}) için kısa, zeki ve eğlenceli bir burç yorumu yaz."
    await update.message.chat.send_action(action="typing")
    ans = await query_grok(p, COMMAND_3LANG_PROMPT)
    await update.message.reply_text(ans)

async def cmd_kral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    p = f"Bugünün Kralı ilan edilen kişi: {user}. Onun için kısa ve görkemli bir övgü fermanı yaz."
    await update.message.chat.send_action(action="typing")
    ans = await query_grok(p, COMMAND_3LANG_PROMPT)
    await update.message.reply_text(ans)

async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("🇹🇷 Henüz puan yok!\n🇷🇺 Пока нет очков!\n🇩🇪 Noch keine Punkte!")
        return
    sorted_users = sorted(scores.values(), key=lambda x: x["points"], reverse=True)[:5]
    
    text = "🏆 **PUAN SIRALAMASI / РЕЙТИНГ / RANGLISTE** 🏆\n\n"
    for idx, u in enumerate(sorted_users, 1):
        text += f"{idx}. **{u['name']}** — {u['points']} Pts\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# --- MESAJ İŞLEME ---
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

        # Bot Etiketlendiyse VEYA Yanıt Verildiyse (Dahi Mod: Yazılan Dilde Cevap)
        if (bot_username and f"@{bot_username}".lower() in text.lower()) or (message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id):
            clean_text = text.replace(f"@{bot_username}", "").strip()
            if not clean_text: return
            await message.chat.send_action(action="typing")
            ans = await query_grok(clean_text, DAHI_BOT_PROMPT)
            await message.reply_text(ans)
            return

        # Çok kısa mesajlar/linkler çevrilmez
        words = text.split()
        if len(words) < 2 or len(text) < 4 or "http" in text:
            return

        # Otomatik Çeviri Kuralları
        active_langs_prompt = f"{TRANSLATION_SYSTEM_PROMPT}\n"
        active_langs_prompt += f"Aktif Diller: TR={LANG_STATUS['tr']}, RU={LANG_STATUS['ru']}, DE={LANG_STATUS['de']}. Kapalı olan dilde çeviri üretme!"

        translated = await query_grok(text, active_langs_prompt)
        if translated and len(translated) > 3:
            await message.reply_text(translated)

    except Exception as e:
        logger.error(f"Handle message hatası: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Dil Komutları
    app.add_handler(CommandHandler("turkce", cmd_toggle_lang))
    app.add_handler(CommandHandler("rusca", cmd_toggle_lang))
    app.add_handler(CommandHandler("almanca", cmd_toggle_lang))

    # Temel Komutlar (3 Dilde Çıktı Verenler)
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("burc", cmd_burc))
    app.add_handler(CommandHandler("kral", cmd_kral))
    app.add_handler(CommandHandler("siralama", cmd_siralama))
    app.add_handler(CommandHandler("puan", cmd_siralama))

    # Mesaj Dinleyici
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Viyana AI (Sade, Dahi Mod & Kusursuz Çeviri) Başlatıldı...")
    app.run_polling(drop_pending_updates=True)
