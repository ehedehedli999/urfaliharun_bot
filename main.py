import logging
import random
import re
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
TELEGRAM_TOKEN = "8363449973:AAEel1P8fp1b3eRhnbpDNM4Z6vdEbFQR8h0"
XAI_API_KEY = "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"

XAI_URL = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL = "llama-3.1-8b-instant"

USER_SCORES = {}
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

# --- PROFESYONEL PROMPTLAR ---

DAHI_BOT_PROMPT = """
Sen Viyana AI'sın. Yapımcın Ehed'dir.
Sen son derece dahi, profesyonel ve üstün zekalı bir yapay zekasın.
Kullanıcı seninle konuştuğunda HANGİ DİLDE YAZDIYSA SADECE O DİLDE CEVAP VER.
(Türkçe yazdıysa Türkçe, Rusça yazdıysa Rusça, Almanca yazdıysa Almanca).
Doğrudan, mantıklı, profesyonel ve net cevap ver.
"""

PROFESSIONAL_TRANSLATION_PROMPT = """
Sen profesyonel, yüksek hassasiyetli ve uzman bir mütercim-tercümansın.
Görevin verilen metni hedef dillere %100 AMACA UYGUN, DİL BİLGİSİ YÖNÜNDEN KUSURSUZ VE DOĞAL bir şekilde çevirmektir.

ÇEVİRİ İLKELERİ:
1. KELİME KELİME BİREBİR ÇEVİRİ YAPMA! Metnin ifade ettiği gerçek anlamı ve bağlamı hedef dilin gramerine ve yapısına göre profesyonelce aktar.
   - (Örn: "Herkese selam arkadaşlar nasılsınız" -> Rusça: "Всем привет, arkadaşlar, как дела?" | Almanca: "Hallo zusammen, wie geht es euch?")
2. METNE KESİNLİKLE EKLEME, YORUM VEYA SÜSLEME YAPMA.
3. BAŞLIK, YAZI VEYA "Türkçe:" GİBİ İFADELER EKLEME. Sadece bayrak emojisi koy.

KATI FORMAT KURALLARI:
Girdi TÜRKÇE ise çıktın KESİNLİKLE sadece şu 2 satırdan oluşacak:
🇷🇺 [Kusursuz Rusça Çevirisi - Kiril]
🇩🇪 [Kusursuz Almanca Çevirisi]

Girdi RUSÇA ise çıktın KESİNLİKLE sadece şu 2 satırdan oluşacak:
🇹🇷 [Kusursuz Türkçe Çevirisi]
🇩🇪 [Kusursuz Almanca Çevirisi]

Girdi ALMANCA ise çıktın KESİNLİKLE sadece şu 2 satırdan oluşacak:
🇹🇷 [Kusursuz Türkçe Çevirisi]
🇷🇺 [Kusursuz Rusça Çevirisi - Kiril]
"""

async def query_grok(prompt: str, system_prompt: str) -> str:
    try:
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
            "temperature": 0.0,  # SIFIR YARATICILIK: Kesin ve hatasız çeviri garantisi
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(XAI_URL, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                logger.error(f"Groq API Error: {response.status_code}")
                return ""
    except Exception as e:
        logger.error(f"API Sorgu Hatası: {e}")
        return ""

def detect_language_simple(text: str) -> str:
    # Kiril Harfi kontrolü (Rusça)
    if re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    # Almanca Özgü Harfler ve Temel Kelimeler
    elif re.search(r'[äöüßäÖÜß]', text) or any(w in text.lower().split() for w in ["ich", "ist", "und", "nicht", "das", "die", "der", "wie", "hallo"]):
        return "de"
    # Varsayılan Türkçe
    else:
        return "tr"

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

COMMAND_3LANG_PROMPT = """
Şu görevi 3 dilde (Türkçe, Rusça, Almanca) bayraklı profesyonelce hazırla:
🇹🇷 [Türkçe Metin]
🇷🇺 [Rusça Metin - Kiril]
🇩🇪 [Almanca Metin]
"""

# --- TEMEL KOMUTLAR ---
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = "Hakkımda metnini yaz: Ben Viyana Ai Yapay zeka botu Ehed Tarafından Tasarlandım en Üst düzey Ai Teknolojisiyle çalışıyorum."
    await update.message.chat.send_action(action="typing")
    ans = await query_grok(p, COMMAND_3LANG_PROMPT)
    if ans:
        await update.message.reply_text(ans)

async def cmd_burc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args) if context.args else "genel"
    p = f"Kullanıcının belirttiği burç ({args}) için kısa ve zeki bir burç yorumu yaz."
    await update.message.chat.send_action(action="typing")
    ans = await query_grok(p, COMMAND_3LANG_PROMPT)
    if ans:
        await update.message.reply_text(ans)

async def cmd_kral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    p = f"Bugünün Kralı ilan edilen kişi: {user}. Onun için kısa ve görkemli bir övgü fermanı yaz."
    await update.message.chat.send_action(action="typing")
    ans = await query_grok(p, COMMAND_3LANG_PROMPT)
    if ans:
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

# --- MESAJ İŞLEME KODU ---
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

        # Dahi Bot Modu (Sadece Etiket veya Yanıt Durumunda)
        if (bot_username and f"@{bot_username}".lower() in text.lower()) or (message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id):
            clean_text = text.replace(f"@{bot_username}", "").strip()
            if not clean_text: return
            await message.chat.send_action(action="typing")
            ans = await query_grok(clean_text, DAHI_BOT_PROMPT)
            if ans:
                await message.reply_text(ans)
            return

        # Filtre: Çok kısa metinler ve linkler
        words = text.split()
        if len(words) < 2 or len(text) < 4 or "http" in text:
            return

        # Mesajın Dilini Kod Seviyesinde Algıla
        src_lang = detect_language_simple(text)

        # Profesyonel Çeviriyi İste
        translated = await query_grok(text, PROFESSIONAL_TRANSLATION_PROMPT)
        
        if translated and len(translated) > 3:
            lines = translated.split('\n')
            clean_lines = []

            for line in lines:
                line_str = line.strip()
                if not line_str: continue

                # 1. KOD SEVİYESİNDE ORİJİNAL DİLİ SİLME
                if src_lang == "tr" and "🇹🇷" in line_str: continue
                if src_lang == "ru" and "🇷🇺" in line_str: continue
                if src_lang == "de" and "🇩🇪" in line_str: continue

                # 2. BUTONLA KAPATILAN DİLLERİ SİLME
                if not LANG_STATUS["tr"] and "🇹🇷" in line_str: continue
                if not LANG_STATUS["ru"] and "🇷🇺" in line_str: continue
                if not LANG_STATUS["de"] and "🇩🇪" in line_str: continue

                clean_lines.append(line_str)

            final_output = "\n\n".join(clean_lines).strip()

            if final_output:
                await message.reply_text(final_output)

    except Exception as e:
        logger.error(f"Handle message hatası: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Dil Komutları
    app.add_handler(CommandHandler("turkce", cmd_toggle_lang))
    app.add_handler(CommandHandler("rusca", cmd_toggle_lang))
    app.add_handler(CommandHandler("almanca", cmd_toggle_lang))

    # Temel Komutlar
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("burc", cmd_burc))
    app.add_handler(CommandHandler("kral", cmd_kral))
    app.add_handler(CommandHandler("siralama", cmd_siralama))
    app.add_handler(CommandHandler("puan", cmd_siralama))

    # Mesaj Dinleyici
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Viyana AI Profesyonel Çeviri Modunda Aktif...")
    app.run_polling(drop_pending_updates=True, poll_interval=1.0)
