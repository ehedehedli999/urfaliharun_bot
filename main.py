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
XAI_API_KEY = "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"

# Groq API Endpoint & Model
XAI_URL = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL = "llama-3.3-70b-versatile"

# Veri Depoları (Hafıza)
CHAT_MODES = {}
TRANSLATION_SETTINGS = {}  # Genel çeviri açık/kapalı
DISABLED_LANGUAGES = {}    # Grup bazlı kapatılan diller {chat_id: set("de", "ru", "tr")}
USER_SCORES = {}           # Puan sistemi {chat_id: {user_id: {"name": ..., "points": ..., "messages": ...}}}
DAILY_KING = {}            # 24 Saatlik Kral {chat_id: {"name": ..., "date": datetime_obj}}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


SMART_PROMPT = """
Sen Viyana AI Bot'un Zeki modusun. Yapımcın Ehed'dir.
Çok zeki, bilgili, analitik, kültürlü ve mantıklı konuş.
Kullanıcının sorusuna doğrudan, doğal ve doğru cevap ver.
Kullanıcı hangi dilde yazıyorsa SADECE o dilde cevap ver.
Sadece Türkçe, Rusça ve Almanca dillerini destekle.
"""

AGGRESSIVE_PROMPT = """
Sen Viyana AI Bot'un Agresif modusun. Yapımcın Ehed'dir.
Sert, özgüvenli, direkt, keskin, hafif alaycı konuş.
Kullanıcı hangi dilde yazıyorsa SADECE o dilde cevap ver.
Sadece Türkçe, Rusça ve Almanca dillerini destekle.
"""

TRANSLATION_PROMPT = """
Sen hedef dillerin kültürüne ve günlük konuşma kalıplarına %100 hakim profesyonel bir çevirmensin.
SADECE Türkçe, Rusça ve Almanca dilleri arasında çeviri yap. (İngilizce yok!)

KURALLAR:
1. Gelen metni tespit et ve SADECE DİĞER İKİ DİLE çevir.
- Türkçe geldiyse → Rusça ve Almanca
- Rusça geldiyse → Türkçe ve Almanca
- Almanca geldiyse → Türkçe ve Rusça

2. Çıktı formatı Standart Olmalıdır:
Türkçe: ...
Rusça: ...
Almanca: ...

3. Ekstra hiçbir açıklama, giriş yazısı yazma.
4. Desteklenmeyen bir dilse SADECE: DESTEKLENMEYEN_DIL yaz.
"""

async def query_grok(prompt: str, system_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
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
        raise Exception(f"API Hatası: {response.status_code}")

# --- DİL FİLTRELEME MANTIĞI ---
def filter_disabled_languages(chat_id: int, translation_text: str) -> str:
    disabled = DISABLED_LANGUAGES.get(chat_id, set())
    if not disabled:
        return translation_text

    lines = translation_text.split("\n")
    filtered_lines = []

    for line in lines:
        lower_line = line.lower().strip()
        
        if ("türkçe:" in lower_line or "turkce:" in lower_line or "tr:" in lower_line) and "tr" in disabled:
            continue
        if ("rusça:" in lower_line or "rusca:" in lower_line or "ru:" in lower_line) and "ru" in disabled:
            continue
        if ("almanca:" in lower_line or "de:" in lower_line) and "de" in disabled:
            continue
            
        filtered_lines.append(line)

    return "\n".join(filtered_lines).strip()

def get_active_prompt_languages(chat_id: int) -> str:
    disabled = DISABLED_LANGUAGES.get(chat_id, set())
    langs = []
    if "tr" not in disabled: langs.append("Türkçe")
    if "ru" not in disabled: langs.append("Rusça")
    if "de" not in disabled: langs.append("Almanca")
    return ", ".join(langs) if langs else "Türkçe, Rusça, Almanca"

# --- PUAN & SEVİYE SİSTEMİ ---
def add_point(chat_id: int, user):
    if user.is_bot:
        return
    
    if chat_id not in USER_SCORES:
        USER_SCORES[chat_id] = {}
    
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
        "• `/ceviri` \n"
        "  🇹🇷 Otomatik çeviriyi açar/kapatır.\n"
        "  🇷🇺 Включает/выключает автоперевод.\n"
        "  🇩🇪 Schaltet die automatische Übersetzung ein/aus.\n\n"

        "• `/turkce` \n"
        "  🇹🇷 Türkçe çeviriyi grupta açar veya kapatır.\n"
        "  🇷🇺 Включает/выключает турецкий перевод.\n"
        "  🇩🇪 Schaltet die türkische Übersetzung ein/aus.\n\n"

        "• `/rusca` \n"
        "  🇹🇷 Rusça çeviriyi grupta açar veya kapatır.\n"
        "  🇷🇺 Включает/выключает русский перевод.\n"
        "  🇩🇪 Schaltet die russische Übersetzung ein/aus.\n\n"

        "• `/almanca` \n"
        "  🇹🇷 Almanca çeviriyi grupta açar veya kapatır.\n"
        "  🇷🇺 Включает/выключает немецкий перевод.\n"
        "  🇩🇪 Schaltet die deutsche Übersetzung ein/aus.\n\n"

        "───────────────────────────────\n"
        "🎮 **EĞLENCE & OYUNLAR / ИГРЫ / SPIELE**\n\n"

        "• `/burc <burç_adı>`\n"
        "  🇹🇷 Yazdığınız burç için günlük yorum yapar.\n"
        "  🇷🇺 Ежедневный гороскоп для указанного знака.\n"
        "  🇩🇪 Tägliches Horoskop für das Sternzeichen.\n\n"

        "• `/fal` \n"
        "  🇹🇷 Kişiye özel komik günlük kahve falı bakar.\n"
        "  🇷🇺 Веселое ежедневное гадание на кофе.\n"
        "  🇩🇪 Lustiges tägliches Kaffeesatzlesen.\n\n"

        "• `/kral` \n"
        "  🇹🇷 Grubun 24 saatlik Kralını seçer.\n"
        "  🇷🇺 Выбирает Короля группы на 24 часа.\n"
        "  🇩🇪 Wählt den König der Gruppe für 24 Stunden.\n\n"

        "• `/kurban` \n"
        "  🇹🇷 Günün kurbanını seçer ve unvan verir.\n"
        "  🇷🇺 Выбирает жертву дня и дает титул.\n"
        "  🇩🇪 Wählt das Opfer des Tages und gibt einen Titel.\n\n"

        "• `/dedikodu` \n"
        "  🇹🇷 Gruptaki 2 kişi hakkında komik dedikodu uydurur.\n"
        "  🇷🇺 Придумывает смешные слухи о 2 участниках.\n"
        "  🇩🇪 Erfindet klatsch über 2 Personen.\n\n"

        "• `/sarcasm <metin>` \n"
        "  🇹🇷 Yazdığınız metne alaycı/ironik cevap verir.\n"
        "  🇷🇺 Ироничный и саркастический ответ.\n"
        "  🇩🇪 Sarkastische und ironische Antwort.\n\n"

        "• `/joke` \n"
        "  🇹🇷 Rastgele komik bir espri/şaka söyler.\n"
        "  🇷🇺 Рассказывает случайную шутку.\n"
        "  🇩🇪 Erzählt einen zufälligen Witz.\n\n"

        "• `/kader` \n"
        "  🇹🇷 Bugün başınıza gelecek komik kaderi söyler.\n"
        "  🇷🇺 Предсказывает вашу смешную судьбу.\n"
        "  🇩🇪 Sagt dein lustiges Schicksal voraus.\n\n"

        "• `/bilgi` \n"
        "  🇹🇷 Eğlenceli genel kültür sorusu sorar.\n"
        "  🇷🇺 Интересный вопрос викторины.\n"
        "  🇩🇪 Eine unterhaltsame Quizfrage.\n\n"

        "• `/siralama` \n"
        "  🇹🇷 En çok mesaj yazanların puan sıralaması.\n"
        "  🇷🇺 Рейтинг самых активных участников.\n"
        "  🇩🇪 Rangliste der aktivsten Mitglieder.\n"
        "───────────────────────────────\n"
        "💡 *Not: Bot etiketlendiğinde (@ViyanaAi) AI doğrudan cevap verir!*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# --- KOMUTLAR ---

async def cmd_burc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    burc_adi = " ".join(context.args) if context.args else ""
    if not burc_adi:
        await update.message.reply_text(
            "✨ Lütfen bir burç adı yazın! / Напишите знак зодиака! / Bitte geben Sie ein Sternzeichen an!\n"
            "Örn: `/burc koc`",
            parse_mode="Markdown"
        )
        return

    active_langs = get_active_prompt_languages(chat_id)
    prompt = f"'{burc_adi}' burcu için bugün özel günlük burç yorumu yap. Cevabı SADECE şu dillerde başlıklarıyla ver: {active_langs}."
    res = await query_grok(prompt, "Sen Viyana AI astroloğusun.")
    filtered_res = filter_disabled_languages(chat_id, res)
    await update.message.reply_text(f"⭐ **BURÇ YORUMU / ГОРОСКОП / HOROSKOP ({burc_adi.upper()}):**\n\n{filtered_res}")

async def cmd_fal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    active_langs = get_active_prompt_languages(chat_id)
    
    prompt = f"{user_name} için bugün özel komik günlük kahve falı yorumu yap. Cevabı SADECE şu dillerde başlıklarıyla ver: {active_langs}."
    res = await query_grok(prompt, "Sen Viyana AI'nin eğlenceli falcısısın.")
    filtered_res = filter_disabled_languages(chat_id, res)
    await update.message.reply_text(f"🔮 **{user_name} Fal / Гадание / Horoskop:**\n\n{filtered_res}")

async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    active_langs = get_active_prompt_languages(chat_id)
    prompt = f"Bana komik bir espri söyler misin? Cevabı SADECE şu dillerde başlıklarıyla ver: {active_langs}."
    res = await query_grok(prompt, "Sen Viyana AI komedyenisin.")
    filtered_res = filter_disabled_languages(chat_id, res)
    await update.message.reply_text(f"😂 {filtered_res}")

async def cmd_sarcasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = " ".join(context.args) if context.args else update.effective_message.text
    if not msg or msg == "/sarcasm":
        await update.message.reply_text("Lütfen bir cümle yazın! / Напишите предложение! / Bitte schreiben Sie einen Satz!")
        return
    active_langs = get_active_prompt_languages(chat_id)
    prompt = f"Şu cümleyi aşırı alaycı/ironik şekilde yanıtla: '{msg}'. Cevabı SADECE şu dillerde başlıklarıyla ver: {active_langs}."
    res = await query_grok(prompt, "Sen alaycı Viyana AI botusun.")
    filtered_res = filter_disabled_languages(chat_id, res)
    await update.message.reply_text(f"😏 {filtered_res}")

async def cmd_kader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name
    active_langs = get_active_prompt_languages(chat_id)
    prompt = f"{user_name} için bugün başına gelecek komik bir kader durumu uydur. Cevabı SADECE şu dillerde başlıklarıyla ver: {active_langs}."
    res = await query_grok(prompt, "Sen eğlenceli kader çarkısın.")
    filtered_res = filter_disabled_languages(chat_id, res)
    await update.message.reply_text(f"🎲 **Kader / Судьба / Schicksal:**\n\n{filtered_res}")

async def cmd_kral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("👑 Kral için grupta mesaj yazılmalı! / Напишите сообщения untuk выбора короля!")
        return

    now = datetime.now()
    if chat_id in DAILY_KING:
        king_data = DAILY_KING[chat_id]
        if now - king_data["date"] < timedelta(hours=24):
            await update.message.reply_text(
                f"👑 **BUGÜNÜN KRALI / КОРОЛЬ ДНЯ / KÖNIG DES TAGES:** {king_data['name']}!\n"
                f"*(24 Saat / 24 Часа / 24 Stunden)* 🙇‍♂️"
            )
            return

    kral = random.choice(list(scores.values()))
    DAILY_KING[chat_id] = {"name": kral["name"], "date": now}
    
    text = f"👑 **GÜNÜN KRALI / КОРОЛЬ ДНЯ / KÖNIG DES TAGES:** {kral['name']}!\n"
    disabled = DISABLED_LANGUAGES.get(chat_id, set())
    if "tr" not in disabled: text += "Türkçe: Önümüzdeki 24 saat boyunca taht senin!\n"
    if "ru" not in disabled: text += "Rusça: В течение следующих 24 часов трон твой!\n"
    if "de" not in disabled: text += "Almanca: Für die nächsten 24 Stunden gehört der Thron dir!\n"
    
    await update.message.reply_text(text)

async def cmd_kurban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("🎯 Kurban seçilemedi!")
        return
    kurban = random.choice(list(scores.values()))
    active_langs = get_active_prompt_languages(chat_id)
    prompt = f"Gruptan {kurban['name']} bugünün kurbanı seçildi. Ona komik bir unvan ver ve cevabı SADECE şu dillerde başlıklarıyla yaz: {active_langs}."
    res = await query_grok(prompt, "Sen komik bir sunucusun.")
    filtered_res = filter_disabled_languages(chat_id, res)
    await update.message.reply_text(f"🎯 **KURBAN / ЖЕРТВА / OPFER:** {kurban['name']}\n\n{filtered_res}")

async def cmd_dedikodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if len(scores) < 2:
        await update.message.reply_text("🕵️ Dedikodu için en az 2 aktif kişi lazım!")
        return
    users = random.sample(list(scores.values()), 2)
    active_langs = get_active_prompt_languages(chat_id)
    prompt = f"{users[0]['name']} ve {users[1]['name']} hakkında komik uydurma bir dedikodu yaz. Cevabı SADECE şu dillerde başlıklarıyla ver: {active_langs}."
    res = await query_grok(prompt, "Sen magazin muhabirisin.")
    filtered_res = filter_disabled_languages(chat_id, res)
    await update.message.reply_text(f"🚨 **DEDİKODU / СЛУХИ / KLATSCH:**\n\n{filtered_res}")

async def cmd_bilgi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    active_langs = get_active_prompt_languages(chat_id)
    prompt = f"Bana şıklı eğlenceli bir genel kültür sorusu sor. Soruyu SADECE şu dillerde başlıklarıyla ver: {active_langs}."
    res = await query_grok(prompt, "Sen bilgi yarışması sunucususun.")
    filtered_res = filter_disabled_languages(chat_id, res)
    await update.message.reply_text(f"🧠 **KİM BİLİR? / КТО ЗНАЕТ? / WER WEISS?**\n\n{filtered_res}")

async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scores = USER_SCORES.get(chat_id, {})
    if not scores:
        await update.message.reply_text("🏆 Henüz puan yok! / Очков пока нет! / Noch keine Punkte!")
        return

    sorted_users = sorted(scores.values(), key=lambda x: x["points"], reverse=True)[:10]
    text = "🏆 **VİYANA AI — PUAN SIRALAMASI / РЕЙТИНГ / RANGLISTE** 🏆\n👑 *Creator: Ehed*\n\n"
    for idx, u in enumerate(sorted_users, 1):
        lvl = get_level(u["points"])
        text += f"{idx}. **{u['name']}** — {u['points']} Puan ({lvl})\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# --- DİL AÇMA/KAPATMA KOMUTLARI ---
async def toggle_language(update: Update, context: ContextTypes.DEFAULT_TYPE, lang_code: str, lang_name: str):
    chat_id = update.effective_chat.id
    if chat_id not in DISABLED_LANGUAGES:
        DISABLED_LANGUAGES[chat_id] = set()

    if lang_code in DISABLED_LANGUAGES[chat_id]:
        DISABLED_LANGUAGES[chat_id].remove(lang_code)
        await update.effective_message.reply_text(f"✅ {lang_name} çevirisi **AÇILDI / ВКЛЮЧЕНО / AKTIVIERT**.")
    else:
        DISABLED_LANGUAGES[chat_id].add(lang_code)
        await update.effective_message.reply_text(f"❌ {lang_name} çevirisi **KAPATILDI / ВЫКЛЮЧЕНО / DEAKTIVIERT**.")

async def toggle_almanca(update: Update, context: ContextTypes.DEFAULT_TYPE): await toggle_language(update, context, "de", "Almanca / Немецкий / Deutsch")
async def toggle_rusca(update: Update, context: ContextTypes.DEFAULT_TYPE): await toggle_language(update, context, "ru", "Rusça / Русский / Russisch")
async def toggle_turkce(update: Update, context: ContextTypes.DEFAULT_TYPE): await toggle_language(update, context, "tr", "Türkçe / Турецкий / Türkisch")

async def toggle_translation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current_status = TRANSLATION_SETTINGS.get(chat_id, True)
    TRANSLATION_SETTINGS[chat_id] = not current_status
    status_str = "AÇILDI / ВКЛ" if not current_status else "KAPATILDI / ВЫКЛ"
    await update.effective_message.reply_text(f"🌐 Otomatik çeviri **{status_str}**.")

# --- MESAJ İŞLEYİCİ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return

    text = message.text.strip()
    chat_id = message.chat_id
    user = update.effective_user

    # Puan Ekle
    add_point(chat_id, user)

    # Bot Etiketlenme Kontrolü (@ViyanaAi)
    bot_username = context.bot.username or ""
    if bot_username and f"@{bot_username}".lower() in text.lower():
        clean_text = text.replace(f"@{bot_username}", "").strip()
        if not clean_text: return
        
        await message.chat.send_action(action="typing")
        mode = CHAT_MODES.get(chat_id, "smart")
        prompt = AGGRESSIVE_PROMPT if mode == "aggressive" else SMART_PROMPT
        ans = await query_grok(clean_text, prompt)
        await message.reply_text(ans)
        return

    # Otomatik Çeviri
    if TRANSLATION_SETTINGS.get(chat_id, True):
        try:
            res = await query_grok(text, TRANSLATION_PROMPT)
            if "DESTEKLENMEYEN_DIL" in res:
                return

            filtered = filter_disabled_languages(chat_id, res)
            if filtered:
                await message.reply_text(filtered)
        except Exception as e:
            logger.error(f"Çeviri hatası: {e}")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Yardım & Bilgi
    application.add_handler(CommandHandler("help", cmd_help))

    # Oyun & Eğlence Komutları
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

    # Dil Ayar Komutları
    application.add_handler(CommandHandler("ceviri", toggle_translation))
    application.add_handler(CommandHandler("almanca", toggle_almanca))
    application.add_handler(CommandHandler("rusca", toggle_rusca))
    application.add_handler(CommandHandler("turkce", toggle_turkce))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Viyana AI Bot Çalışıyor (3 Dil Modu - TR/RU/DE)... Yapımcı: Ehed")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
