import logging
import os
import random
from datetime import datetime, timedelta
import httpx
from langdetect import detect, DetectorFactory
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Dil tespitini kararlı kılmak için
DetectorFactory.seed = 0

# Eski Token'ın Sabitlendi
TELEGRAM_TOKEN = "8363449973:AAFWPie-yjpJn1vHQxSKeykVKjq2Pt3Lo1k"
XAI_API_KEY = "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"

# Groq API Endpoint & Model
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
    if points < 100: return "🥉 Çaylak / Новичок / Anfänger"
    if points < 500: return "🥈 Bronz / Бронза / Bronze"
    if points < 1500: return "🥇 Gümüş / Серебро / Silber"
    if points < 3000: return "💎 Altın / Золото / Gold"
    if points < 7000: return "👑 Viyana Savaşçısı / Воин Вены / Wiener Krieger"
    return "🔥 Viyana Efsanesi / Легенда Вены / Wiener Legende"

# --- AKILLI ÇEVİRİ VE DİL FİLTRESİ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text: return
    text = message.text.strip()
    chat_id = message.chat_id
    user = update.effective_user

    # Bot veya Komutlar muaf tutulur
    if user.is_bot or text.startswith("/"):
        return

    add_point(chat_id, user)
    bot_username = context.bot.username or ""

    # 1. BOT ETİKETLENDİYSE (Doğrudan Yapay Zeka Cevabı)
    if bot_username and f"@{bot_username}".lower() in text.lower():
        clean_text = text.replace(f"@{bot_username}", "").strip()
        if not clean_text: return
        await message.chat.send_action(action="typing")
        try:
            ans = await query_grok(clean_text, SMART_PROMPT)
            await message.reply_text(ans)
        except Exception:
            await message.reply_text("⚠️ Bir hata oluştu, lütfen tekrar deneyin.")
        return

    # Çok kısa kelimeler, linkler veya anlamsız metinler çevrilmez
    words = text.split()
    if len(words) < 2 or len(text) < 5 or "http" in text:
        return

    # 2. PYTHON İLE KESİN DİL TESPİTİ
    try:
        lang = detect(text)
    except Exception:
        lang = "tr"

    # Mesajın yazıldığı dille çakışmayan özel prompt atanır
    if lang == "tr":
        target_prompt = """
        Sana verilen metin TÜRKÇE yazılmıştır.
        Bu cümleyi konuşma diline uygun, doğal ve insansı bir üslupla SADECE Rusça ve Almanca'ya çevir.
        ASLA Türkçe yazma ve "Dil 1", "Dil 2" gibi başlıklar atma!

        Rusça: [Çeviri]
        Almanca: [Çeviri]
        """
    elif lang == "ru":
        target_prompt = """
        Sana verilen metin RUSÇA yazılmıştır.
        Bu cümleyi konuşma diline uygun, doğal ve insansı bir üslupla SADECE Türkçe ve Almanca'ya çevir.
        ASLA Rusça yazma ve "Dil 1", "Dil 2" gibi başlıklar atma!

        Türkçe: [Çeviri]
        Almanca: [Çeviri]
        """
    elif lang == "de":
        target_prompt = """
        Sana verilen metin ALMANCA yazılmıştır.
        Bu cümleyi konuşma diline uygun, doğal ve insansı bir üslupla SADECE Türkçe ve Rusça'ya çevir.
        ASLA Almanca yazma ve "Dil 1", "Dil 2" gibi başlıklar atma!

        Türkçe: [Çeviri]
        Rusça: [Çeviri]
        """
    else:
        target_prompt = """
        Bu cümleyi ultra doğal şekilde SADECE Türkçe ve Almanca'ya çevir.
        
        Türkçe: [Çeviri]
        Almanca: [Çeviri]
        """

    try:
        translated = await query_grok(text, target_prompt)
        if len(translated) < 4: return
        await message.reply_text(translated)
    except Exception as e:
        logger.error(f"Auto translation error: {e}")

# --- BOT KOMUTLARI ---
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **VİYANA AI — BOT MENÜSÜ**\n"
        "👑 *Yapımcı / Creator: Ehed*\n"
        "───────────────────────────────\n\n"
        "🗣️ **OTOMATİK ÇEVİRİ AÇIK!**\n"
        "• Yazılan mesaj tespit edilir ve yazılan dil hariç diğer 2 dile çevrilir.\n\n"
        "🎮 **KOMUTLAR**\n"
        "• `/burc <burç_adı>` — Günlük burç yorumu\n"
        "• `/fal` — Günlük kahve falı\n"
        "• `/kral` — Grubun 24 saatlik Kralı\n"
        "• `/kurban` — Günün kurbanı\n"
        "• `/dedikodu` — Gruptakiler hakkında uydurma haber\n"
        "• `/sarcasm <metin>` — Alaycı cevap\n"
        "• `/joke` — Şaka / espri\n"
        "• `/kader` — Günlük kader çarkı\n"
        "• `/bilgi` — Genel kültür sorusu\n"
        "• `/siralama` — Puan sıralaması"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_burc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    burc_adi = " ".join(context.args) if context.args else ""
    if not burc_adi:
        await update.message.reply_text("✨ Lütfen bir burç adı yazın! Örn: `/burc koc`", parse_mode="Markdown")
        return
    try:
        prompt = f"'{burc_adi}' burcu için günlük yorum yap. Türkçe, Rusça ve Almanca yaz."
        res = await query_grok(prompt, "Sen Viyana AI astroloğusun.")
        await update.message.reply_text(f"⭐ **BURÇ YORUMU ({burc_adi.upper()}):**\n\n{res}")
    except Exception:
        await update.message.reply_text("⚠️ Bir hata oluştu.")

async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        prompt = "Bana komik bir espri söyler misin? Türkçe, Rusça ve Almanca olarak yaz."
        res = await query_grok(prompt, "Sen Viyana AI komedyenisin.")
        await update.message.reply_text(f"😂 **ŞAKA / ESPRİ:**\n\n{res}")
    except Exception:
        await update.message.reply_text("⚠️ Bir hata oluştu.")

async def cmd_fal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    try:
        prompt = f"{user_name} için komik kahve falı yorumu yap. Türkçe, Rusça ve Almanca dillerinde yaz."
        res = await query_grok(prompt, "Sen Viyana AI falcısısın.")
        await update.message.reply_text(f"🔮 **FAL ({user_name}):**\n\n{res}")
    except Exception:
        await update.message.reply_text("⚠️ Bir hata oluştu.")

async def cmd_sarcasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = " ".join(context.args) if context.args else update.effective_message.text
    if not msg or msg == "/sarcasm":
        await update.message.reply_text("Lütfen bir cümle yazın!")
        return
    try:
        prompt = f"Şu cümleyi aşırı alaycı/ironik şekilde yanıtla: '{msg}'. Türkçe, Rusça ve Almanca yaz."
        res = await query_grok(prompt, "Sen alaycı Viyana AI botusun.")
        await update.message.reply_text(f"😏 {res}")
    except Exception:
        await update.message.reply_text("⚠️ Bir hata oluştu.")

async def cmd_kader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    try:
        prompt = f"{user_name} için bugün başına gelecek komik bir kader uydur. Türkçe, Rusça ve Almanca yaz."
        res = await query_grok(prompt, "Sen kader çarkısın.")
        await update.message.reply_text(f"🎲 **KADER ({user_name}):**\n\n{res}")
    except Exception:
        await update.message.reply_text("⚠️ Bir hata oluştu.")

async def cmd_kral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("👑 Kral seçilmek için grupta mesaj yazılmalı!")
        return
    now = datetime.now()
    if chat_id in DAILY_KING and now - DAILY_KING[chat_id]["date"] < timedelta(hours=24):
        await update.message.reply_text(f"👑 **BUGÜNÜN KRALI:** {DAILY_KING[chat_id]['name']}! 🙇‍♂️")
        return
    kral = random.choice(list(scores.values()))
    DAILY_KING[chat_id] = {"name": kral["name"], "date": now}
    await update.message.reply_text(f"👑 **GÜNÜN KRALI:** {kral['name']}! 🙇‍♂️✨")

async def cmd_kurban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("🎯 Kurban seçilemedi!")
        return
    kurban = random.choice(list(scores.values()))
    try:
        prompt = f"Gruptan {kurban['name']} kurban seçildi. Ona komik bir unvan ver. Türkçe, Rusça ve Almanca yaz."
        res = await query_grok(prompt, "Sen komik sunucusun.")
        await update.message.reply_text(f"🎯 **KURBAN:** {kurban['name']}\n\n{res}")
    except Exception:
        await update.message.reply_text("⚠️ Bir hata oluştu.")

async def cmd_dedikodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if len(scores) < 2:
        await update.message.reply_text("🕵️ Dedikodu için en az 2 aktif kişi lazım!")
        return
    users = random.sample(list(scores.values()), 2)
    try:
        prompt = f"{users[0]['name']} ve {users[1]['name']} hakkında komik dedikodu yaz. Türkçe, Rusça ve Almanca dillerinde ver."
        res = await query_grok(prompt, "Sen magazin muhabirisin.")
        await update.message.reply_text(f"🚨 **DEDİKODU:**\n\n{res}")
    except Exception:
        await update.message.reply_text("⚠️ Bir hata oluştu.")

async def cmd_bilgi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        prompt = "Bana şıklı genel kültür sorusu sor. Türkçe, Rusça ve Almanca dillerinde yaz."
        res = await query_grok(prompt, "Sen yarışma sunucususun.")
        await update.message.reply_text(f"🧠 **KİM BİLİR?**\n\n{res}")
    except Exception:
        await update.message.reply_text("⚠️ Bir hata oluştu.")

async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("🏆 Henüz puan yok!")
        return
    sorted_users = sorted(scores.values(), key=lambda x: x["points"], reverse=True)[:10]
    text = "🏆 **VİYANA AI — PUAN SIRALAMASI** 🏆\n👑 *Creator: Ehed*\n\n"
    for idx, u in enumerate(sorted_users, 1):
        lvl = get_level(u["points"])
        text += f"{idx}. **{u['name']}** — {u['points']} Puan ({lvl})\n"
    await update.message.reply_text(text, parse_mode="Markdown")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handler/Komut Kayıtları
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("burc", cmd_burc))
    application.add_handler(CommandHandler("fal", cmd_fal))
    application.add_handler(CommandHandler("joke", cmd_joke))
    application.add_handler(CommandHandler("sarcasm", cmd_sarcasm))
    application.add_handler(CommandHandler("kader", cmd_kader))
    application.add_handler(CommandHandler("kral", cmd_kral))
    application.add_handler(CommandHandler("kurban", cmd_kurban))
    application.add_handler(CommandHandler("dedikodu", cmd_dedikodu))
    application.add_handler(CommandHandler("bilgi", cmd_bilgi))
    application.add_handler(CommandHandler("puan", cmd_siralama))
    application.add_handler(CommandHandler("siralama", cmd_siralama))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    main()

