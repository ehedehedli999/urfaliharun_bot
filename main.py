import logging
import random
import re
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- TOKENLAR ---
TELEGRAM_TOKEN = "8363449973:AAEel1P8fp1b3eRhnbpDNM4Z6vdEbFQR8h0"
XAI_API_KEY = "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"

XAI_URL = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL = "llama-3.3-70b-versatile"

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

# --- TAM VE KESİNLİKLE EKSİKSİZ ÇEVİRİ PROMPTU ---
SYSTEM_TRANSLATE_PROMPT = """
You are an uncompromising translation engine. 
Your task is to translate short chat messages into target languages.

STRICT MANDATORY RULES:
1. You MUST ALWAYS output EXACTLY TWO lines of translations (unless one language is disabled by system).
2. NEVER skip German or Russian, even if the input text is very short (e.g., "Tmm", "Gelir gülüm").
3. NEVER truncate sentences or leave lines missing.
4. Output ONLY lines starting with flag emojis. No explanations.

OUTPUT FORMAT REQUIREMENTS:
If input language is Turkish / Azerbaijani:
🇷🇺 [Russian Translation]
🇩🇪 [German Translation]

If input language is Russian:
🇹🇷 [Turkish Translation]
🇩🇪 [German Translation]

If input language is German:
🇹🇷 [Turkish Translation]
🇷🇺 [Russian Translation]
"""

COMMAND_3LANG_PROMPT = """
Sana verilen metni veya görevi 3 dilde (Türkçe, Rusça, Almanca) yanıtla.
Çıktı formatı KESİNLİKLE şöyle olmalı:
🇹🇷 [Türkçe İfade]
🇷🇺 [Rusça İfade - Kiril]
🇩🇪 [Almanca İfade]
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
            "temperature": 0.1,
            "max_tokens": 300
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(XAI_URL, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            return ""
    except Exception as e:
        logger.error(f"API Error: {e}")
        return ""

def detect_language(text: str) -> str:
    if re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    elif re.search(r'[äöüßÖÜß]', text) or any(w in text.lower().split() for w in ["ich", "ist", "und", "nicht", "das", "die", "der", "wie", "hallo"]):
        return "de"
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
    if not update.message or not update.message.text: return
    cmd = update.message.text.split()[0].replace("/", "").split("@")[0].lower()
    
    if cmd == "turkce":
        LANG_STATUS["tr"] = not LANG_STATUS["tr"]
        st = "AÇILDI ✅" if LANG_STATUS["tr"] else "KAPATILDI ❌"
        msg = f"🇹🇷 Türkçe Çeviri: {st}"
    elif cmd == "rusca":
        LANG_STATUS["ru"] = not LANG_STATUS["ru"]
        st = "AÇILDI ✅" if LANG_STATUS["ru"] else "KAPATILDI ❌"
        msg = f"🇷🇺 Rusça Çeviri: {st}"
    elif cmd == "almanca":
        LANG_STATUS["de"] = not LANG_STATUS["de"]
        st = "AÇILDI ✅" if LANG_STATUS["de"] else "KAPATILDI ❌"
        msg = f"🇩🇪 Almanca Çeviri: {st}"
    else:
        return
        
    await update.message.reply_text(msg)

# --- EĞLENCE KOMUTLARI ---
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = "Hakkımda metni yaz: Ben Viyana Ai Yapay zeka botuyum. Ehed tarafından tasarlandım."
    ans = await query_grok(p, COMMAND_3LANG_PROMPT)
    if ans: await update.message.reply_text(ans)

async def cmd_burc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args) if context.args else "genel"
    p = f"Kullanıcı için ({args}) burcu/fal hakkında eğlenceli ve kısa bir yorum yap."
    ans = await query_grok(p, COMMAND_3LANG_PROMPT)
    if ans: await update.message.reply_text(ans)

async def cmd_kral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    p = f"Günün Kralı ilan edilen kişi: {user}. Onun için kısa bir övgü fermanı yaz."
    ans = await query_grok(p, COMMAND_3LANG_PROMPT)
    if ans: await update.message.reply_text(ans)

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

# --- MESAJ İŞLEYİCİ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.effective_message
        if not message or not message.text: return
        text = message.text.strip()
        chat_id = message.chat_id
        user = update.effective_user

        if user.is_bot or text.startswith("/"): return

        add_point(chat_id, user)

        clean_text = re.sub(r'@\w+', '', text).strip()
        words = clean_text.split()
        if len(words) < 1 or "http" in text: return

        src_lang = detect_language(clean_text)
        raw_translation = await query_grok(f"Translate: \"{clean_text}\"", SYSTEM_TRANSLATE_PROMPT)

        if not raw_translation: return

        lines = raw_translation.split("\n")
        valid_lines = []

        for line in lines:
            line_clean = line.strip()
            if not line_clean: continue

            # 1. Kaynak dili filtrele
            if src_lang == "tr" and line_clean.startswith("🇹🇷"): continue
            if src_lang == "ru" and line_clean.startswith("🇷🇺"): continue
            if src_lang == "de" and line_clean.startswith("🇩🇪"): continue

            # 2. Kapalı dili filtrele
            if not LANG_STATUS["tr"] and line_clean.startswith("🇹🇷"): continue
            if not LANG_STATUS["ru"] and line_clean.startswith("🇷🇺"): continue
            if not LANG_STATUS["de"] and line_clean.startswith("🇩🇪"): continue

            if any(line_clean.startswith(flag) for flag in ["🇹🇷", "🇷🇺", "🇩🇪"]):
                valid_lines.append(line_clean)

        if valid_lines:
            final_output = "\n".join(valid_lines)
            await message.reply_text(final_output)

    except Exception as e:
        logger.error(f"Handle error: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler(["turkce", "rusca", "almanca"], cmd_toggle_lang))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("burc", cmd_burc))
    app.add_handler(CommandHandler("kral", cmd_kral))
    app.add_handler(CommandHandler(["siralama", "sirallama", "puan"], cmd_siralama))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Viyana AI Güncellenmiş Kod İle Yayında...")
    app.run_polling(drop_pending_updates=True)

