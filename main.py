import logging
import os
import random
from datetime import datetime, timedelta
import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Tokenlar
TELEGRAM_TOKEN = "8363449973:AAFWPie-yjpJn1vHQxSKeykVKjq2Pt3Lo1k"
# Groq API Key
XAI_API_KEY = "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"

# Groq API Endpoint & Model (Güncel ve Stabil Model Yapıldı)
XAI_URL = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL = "llama3-70b-8192"

# Veri Depoları
CHAT_MODES = {}
TRANSLATION_SETTINGS = {}  # Varsayılan kapalı
DISABLED_LANGUAGES = {}    
USER_SCORES = {}           
DAILY_KING = {}            

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SMART_PROMPT = """
Sen Viyana AI Bot'un Zeki modusun. Yapımcın Ehed'dir.
Çok zeki, bilgili, analitik, kültürlü ve mantıklı konuş.
Kullanıcının sorusuna doğrudan, doğal ve doğru cevap ver.
Sadece Türkçe, Rusça ve Almanca dillerini destekle.
"""

AGGRESSIVE_PROMPT = """
Sen Viyana AI Bot'un Agresif modusun. Yapımcın Ehed'dir.
Sert, özgüvenli, direkt, keskin, hafif alaycı konuş.
Sadece Türkçe, Rusça ve Almanca dillerini destekle.
"""

TRANSLATION_PROMPT = """
Sen hedef dillerin kültürüne hakim profesyonel bir çevirmensin.
SADECE Türkçe, Rusça ve Almanca dilleri arasında çeviri yap. (İngilizce yok!)

KURALLAR:
1. Gelen metni tespit et ve SADECE DİĞER İKİ DİLE çevir.
- Türkçe geldiyse → Rusça ve Almanca
- Rusça geldiyse → Türkçe ve Almanca
- Almanca geldiyse → Türkçe ve Rusça

2. Çıktı formatı:
Türkçe: ...
Rusça: ...
Almanca: ...

3. Ekstra hiçbir açıklama yazma.
4. Desteklenmeyen bir dilse SADECE: DESTEKLENMEYEN_DIL yaz.
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
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(XAI_URL, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        elif response.status_code == 401:
            raise Exception("UNAUTHORIZED")
        elif response.status_code == 429:
            raise Exception("LIMIT_EXCEEDED")
        raise Exception(f"API Hatası: {response.status_code}")

def filter_disabled_languages(chat_id: int, text: str) -> str:
    disabled = DISABLED_LANGUAGES.get(chat_id, set())
    if not disabled:
        return text

    blocks = text.split("\n\n")
    filtered_blocks = []

    for block in blocks:
        lower_block = block.lower().strip()
        
        if ("türkçe" in lower_block or "turkce" in lower_block or "tr:" in lower_block) and "tr" in disabled:
            continue
        if ("rusça" in lower_block or "rusca" in lower_block or "русский" in lower_block or "ru:" in lower_block) and "ru" in disabled:
            continue
        if ("almanca" in lower_block or "deutsch" in lower_block or "de:" in lower_block) and "de" in disabled:
            continue
            
        filtered_blocks.append(block)

    return "\n\n".join(filtered_blocks).strip()

def get_active_prompt_languages(chat_id: int) -> str:
    disabled = DISABLED_LANGUAGES.get(chat_id, set())
    langs = []
    if "tr" not in disabled: langs.append("Türkçe")
    if "ru" not in disabled: langs.append("Rusça")
    if "de" not in disabled: langs.append("Almanca")
    return ", ".join(langs) if langs else "Türkçe, Rusça, Almanca"

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

# --- HELP MENÜSÜ ---
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **VİYANA AI — KOMUT MENÜSÜ / МЕНЮ КОМАНД / BEFEHLSMENÜ**\n"
        "👑 *Yapımcı / Создатель / Creator: Ehed*\n"
        "───────────────────────────────\n\n"
        "🌐 **ÇEVİRİ AYARLARI / НАСТРОЙКИ ПЕРЕВОДА / ÜBERSETZUNG**\n"
        "• `/ceviri` — Otomatik çeviriyi açar/kapatır.\n"
        "• `/turkce` — Türkçe çeviriyi açar/kapatır.\n"
        "• `/rusca` — Rusça çeviriyi açar/kapatır.\n"
        "• `/almanca` — Almanca çeviriyi açar/kapatır.\n\n"
        "───────────────────────────────\n"
        "🎮 **EĞLENCE & OYUNLAR / ИГРЫ / SPIELE**\n\n"
        "• `/burc <burç_adı>` — Günlük burç yorumu\n"
        "• `/fal` — Günlük kahve falı\n"
        "• `/kral` — Grubun 24 saatlik Kralını seçer\n"
        "• `/kurban` — Günün kurbanını seçer\n"
        "• `/dedikodu` — Gruptakiler hakkında uydurma haber\n"
        "• `/sarcasm <metin>` — Alaycı/ironik cevap\n"
        "• `/joke` — Komik espri / şaka\n"
        "• `/kader` — Günlük kader çarkı\n"
        "• `/bilgi` — Genel kültür sorusu\n"
        "• `/siralama` — Puan sıralaması\n"
        "───────────────────────────────\n"
        "💡 *Not: Bot etiketlendiğinde (@ViyanaAi) AI doğrudan cevap verir!*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_burc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    burc_adi = " ".join(context.args) if context.args else ""
    if not burc_adi:
        await update.message.reply_text("✨ Lütfen bir burç adı yazın! Örn: `/burc koc`", parse_mode="Markdown")
        return
    try:
        active_langs = get_active_prompt_languages(chat_id)
        prompt = f"'{burc_adi}' burcu için bugün özel günlük burç yorumu yap. Cevabı SADECE şu dillerde ver: {active_langs}."
        res = await query_grok(prompt, "Sen Viyana AI astroloğusun.")
        filtered_res = filter_disabled_languages(chat_id, res)
        await update.message.reply_text(f"⭐ **BURÇ YORUMU ({burc_adi.upper()}):**\n\n{filtered_res}")
    except Exception as e:
        if str(e) == "UNAUTHORIZED":
            await update.message.reply_text("🔑 API Key geçersiz!")
        elif str(e) == "LIMIT_EXCEEDED":
            await update.message.reply_text("⚠️ API Limiti doldu, lütfen 1 dakika sonra tekrar deneyin!")
        else:
            await update.message.reply_text("⚠️ Bir hata oluştu, lütfen tekrar deneyin.")

async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        active_langs = get_active_prompt_languages(chat_id)
        prompt = f"Bana komik bir espri söyler misin? Cevabı SADECE şu dillerde ver: {active_langs}."
        res = await query_grok(prompt, "Sen Viyana AI komedyenisin.")
        filtered_res = filter_disabled_languages(chat_id, res)
        await update.message.reply_text(f"😂 {filtered_res}")
    except Exception as e:
        if str(e) == "UNAUTHORIZED":
            await update.message.reply_text("🔑 API Key geçersiz!")
        elif str(e) == "LIMIT_EXCEEDED":
            await update.message.reply_text("⚠️ API Limiti doldu, lütfen 1 dakika sonra tekrar deneyin!")
        else:
            await update.message.reply_text("⚠️ Bir hata oluştu, lütfen tekrar deneyin.")

async def cmd_fal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    try:
        active_langs = get_active_prompt_languages(chat_id)
        prompt = f"{user_name} için bugün özel komik kahve falı yorumu yap. Cevabı SADECE şu dillerde ver: {active_langs}."
        res = await query_grok(prompt, "Sen Viyana AI falcısısın.")
        filtered_res = filter_disabled_languages(chat_id, res)
        await update.message.reply_text(f"🔮 **{user_name} Fal:**\n\n{filtered_res}")
    except Exception as e:
        if str(e) == "UNAUTHORIZED":
            await update.message.reply_text("🔑 API Key geçersiz!")
        elif str(e) == "LIMIT_EXCEEDED":
            await update.message.reply_text("⚠️ API Limiti doldu, lütfen 1 dakika sonra tekrar deneyin!")
        else:
            await update.message.reply_text("⚠️ Bir hata oluştu, lütfen tekrar deneyin.")

async def cmd_sarcasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = " ".join(context.args) if context.args else update.effective_message.text
    if not msg or msg == "/sarcasm":
        await update.message.reply_text("Lütfen bir cümle yazın!")
        return
    try:
        active_langs = get_active_prompt_languages(chat_id)
        prompt = f"Şu cümleyi aşırı alaycı/ironik şekilde yanıtla: '{msg}'. Cevabı SADECE şu dillerde ver: {active_langs}."
        res = await query_grok(prompt, "Sen alaycı Viyana AI botusun.")
        filtered_res = filter_disabled_languages(chat_id, res)
        await update.message.reply_text(f"😏 {filtered_res}")
    except Exception as e:
        if str(e) == "UNAUTHORIZED":
            await update.message.reply_text("🔑 API Key geçersiz!")
        elif str(e) == "LIMIT_EXCEEDED":
            await update.message.reply_text("⚠️ API Limiti doldu, lütfen 1 dakika sonra tekrar deneyin!")
        else:
            await update.message.reply_text("⚠️ Bir hata oluştu, lütfen tekrar deneyin.")

async def cmd_kader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    try:
        active_langs = get_active_prompt_languages(chat_id)
        prompt = f"{user_name} için bugün başına gelecek komik bir kader durumu uydur. Cevabı SADECE şu dillerde ver: {active_langs}."
        res = await query_grok(prompt, "Sen kader çarkısın.")
        filtered_res = filter_disabled_languages(chat_id, res)
        await update.message.reply_text(f"🎲 **Kader:**\n\n{filtered_res}")
    except Exception as e:
        if str(e) == "UNAUTHORIZED":
            await update.message.reply_text("🔑 API Key geçersiz!")
        elif str(e) == "LIMIT_EXCEEDED":
            await update.message.reply_text("⚠️ API Limiti doldu, lütfen 1 dakika sonra tekrar deneyin!")
        else:
            await update.message.reply_text("⚠️ Bir hata oluştu, lütfen tekrar deneyin.")

async def cmd_kral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("👑 Kral seçilmek için grupta mesaj yazılmalı!")
        return
    now = datetime.now()
    if chat_id in DAILY_KING and now - DAILY_KING[chat_id]["date"] < timedelta(hours=24):
        await update.message.reply_text(f"👑 **BUGÜNÜN KRALI:** {DAILY_KING[chat_id]['name']}! (24 Saat) 🙇‍♂️")
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
        active_langs = get_active_prompt_languages(chat_id)
        prompt = f"Gruptan {kurban['name']} kurban seçildi. Ona komik bir unvan ver. Cevabı SADECE şu dillerde ver: {active_langs}."
        res = await query_grok(prompt, "Sen komik sunucusun.")
        filtered_res = filter_disabled_languages(chat_id, res)
        await update.message.reply_text(f"🎯 **KURBAN:** {kurban['name']}\n\n{filtered_res}")
    except Exception as e:
        if str(e) == "UNAUTHORIZED":
            await update.message.reply_text("🔑 API Key geçersiz!")
        elif str(e) == "LIMIT_EXCEEDED":
            await update.message.reply_text("⚠️ API Limiti doldu, lütfen 1 dakika sonra tekrar deneyin!")
        else:
            await update.message.reply_text("⚠️ Bir hata oluştu, lütfen tekrar deneyin.")

async def cmd_dedikodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if len(scores) < 2:
        await update.message.reply_text("🕵️ Dedikodu için en az 2 aktif kişi lazım!")
        return
    users = random.sample(list(scores.values()), 2)
    try:
        active_langs = get_active_prompt_languages(chat_id)
        prompt = f"{users[0]['name']} ve {users[1]['name']} hakkında komik dedikodu yaz. Cevabı SADECE şu dillerde ver: {active_langs}."
        res = await query_grok(prompt, "Sen magazin muhabirisin.")
        filtered_res = filter_disabled_languages(chat_id, res)
        await update.message.reply_text(f"🚨 **DEDİKODU:**\n\n{filtered_res}")
    except Exception as e:
        if str(e) == "UNAUTHORIZED":
            await update.message.reply_text("🔑 API Key geçersiz!")
        elif str(e) == "LIMIT_EXCEEDED":
            await update.message.reply_text("⚠️ API Limiti doldu, lütfen 1 dakika sonra tekrar deneyin!")
        else:
            await update.message.reply_text("⚠️ Bir hata oluştu, lütfen tekrar deneyin.")

async def cmd_bilgi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        active_langs = get_active_prompt_languages(chat_id)
        prompt = f"Bana şıklı genel kültür sorusu sor. Soruyu SADECE şu dillerde ver: {active_langs}."
        res = await query_grok(prompt, "Sen yarışma sunucususun.")
        filtered_res = filter_disabled_languages(chat_id, res)
        await update.message.reply_text(f"🧠 **KİM BİLİR?**\n\n{filtered_res}")
    except Exception as e:
        if str(e) == "UNAUTHORIZED":
            await update.message.reply_text("🔑 API Key geçersiz!")
        elif str(e) == "LIMIT_EXCEEDED":
            await update.message.reply_text("⚠️ API Limiti doldu, lütfen 1 dakika sonra tekrar deneyin!")
        else:
            await update.message.reply_text("⚠️ Bir hata oluştu, lütfen tekrar deneyin.")

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

async def toggle_language(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code: str, lang_name: str):
    chat_id = update.effective_chat.id
    if chat_id not in DISABLED_LANGUAGES: DISABLED_LANGUAGES[chat_id] = set()
    if lang_code in DISABLED_LANGUAGES[chat_id]:
        DISABLED_LANGUAGES[chat_id].remove(lang_code)
        await update.effective_message.reply_text(f"✅ {lang_name} çevirisi **AÇILDI**.")
    else:
        DISABLED_LANGUAGES[chat_id].add(lang_code)
        await update.effective_message.reply_text(f"❌ {lang_name} çevirisi **KAPATILDI**.")

async def toggle_almanca(update: Update, context: ContextTypes.DEFAULT_TYPE): await toggle_language(update, context, "de", "Almanca")
async def toggle_rusca(update: Update, context: ContextTypes.DEFAULT_TYPE): await toggle_language(update, context, "ru", "Rusça")
async def toggle_turkce(update: Update, context: ContextTypes.DEFAULT_TYPE): await toggle_language(update, context, "tr", "Türkçe")

async def toggle_translation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_status = TRANSLATION_SETTINGS.get(chat_id, False)
    TRANSLATION_SETTINGS[chat_id] = not current_status
    status_str = "AÇILDI" if not current_status else "KAPATILDI"
    await update.effective_message.reply_text(f"🌐 Otomatik çeviri **{status_str}**.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text: return
    text = message.text.strip()
    chat_id = message.chat_id
    user = update.effective_user

    add_point(chat_id, user)

    bot_username = context.bot.username or ""
    if bot_username and f"@{bot_username}".lower() in text.lower():
        clean_text = text.replace(f"@{bot_username}", "").strip()
        if not clean_text: return
        await message.chat.send_action(action="typing")
        try:
            mode = CHAT_MODES.get(chat_id, "smart")
            prompt = AGGRESSIVE_PROMPT if mode == "aggressive" else SMART_PROMPT
            ans = await query_grok(clean_text, prompt)
            await message.reply_text(ans)
        except Exception:
            await message.reply_text("⚠️ İstek yapılamadı, API Key hatası veya limit doldu.")
        return

    if TRANSLATION_SETTINGS.get(chat_id, False):
        try:
            res = await query_grok(text, TRANSLATION_PROMPT)
            if "DESTEKLENMEYEN_DIL" not in res:
                filtered = filter_disabled_languages(chat_id, res)
                if filtered: await message.reply_text(filtered)
        except Exception:
            pass

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
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
    application.add_handler(CommandHandler("ceviri", toggle_translation))
    application.add_handler(CommandHandler("almanca", toggle_almanca))
    application.add_handler(CommandHandler("rusca", toggle_rusca))
    application.add_handler(CommandHandler("turkce", toggle_turkce))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
