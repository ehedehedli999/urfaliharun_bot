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

# --- YAPILANDIRMA ---
TELEGRAM_TOKEN = "8363449973:AAElwMlaNrlKJ7sh8PApYPxWb13YqrHJakU"
OPENROUTER_API_KEY = "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"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "meta-llama/llama-3.1-8b-instruct"

USER_SCORES = {}
TRANSLATION_CACHE = {}

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

async def query_ai(prompt: str, system_prompt: str, max_tokens: int = 100) -> str:
    cache_key = f"{system_prompt[:15]}:{prompt}"
    if cache_key in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[cache_key]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/telegram-bot", 
        "X-Title": "Viyana AI Bot",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens
    }

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                if len(TRANSLATION_CACHE) > 500:
                    TRANSLATION_CACHE.pop(next(iter(TRANSLATION_CACHE)))
                TRANSLATION_CACHE[cache_key] = content
                return content
            else:
                logger.error(f"OpenRouter API Error Status {response.status_code}: {response.text}")
                return ""
    except Exception as e:
        logger.error(f"OpenRouter Request Error: {e}")
        return ""

def detect_language(text: str) -> str:
    if re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    elif re.search(r'[äöüßÄÖÜ]', text) or any(w in text.lower().split() for w in ["ich", "ist", "und", "nicht", "das", "die", "der", "wie", "hallo", "hauptsache", "schokolade", "gott", "zeit", "fleisch"]):
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

# --- KOMUTLAR ---
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

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sys_p = "Sana verilen metni Türkçe, Rusça ve Almanca olarak tam ve doğru çevir."
    p = "Hakkımda metni yaz: Ben Viyana Ai Yapay zeka botuyum. Ehed tarafından tasarlandım."
    ans = await query_ai(p, sys_p, max_tokens=200)
    if ans: await update.message.reply_text(ans)

async def cmd_kral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.first_name
    sys_p = "Sana verilen metni Türkçe, Rusça ve Almanca olarak tam ve doğru çevir."
    p = f"Günün Kralı ilan edilen kişi: {user}. Onun için coşkulu ama kısa bir övgü fermanı yaz."
    ans = await query_ai(p, sys_p, max_tokens=200)
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
        if len(clean_text) < 1 or "http" in text: return

        # 1. Kaynak dili kesin olarak tespit et
        src_lang = detect_language(clean_text)

        # 2. Dile göre kesin ve net çeviri talimatları oluştur
        if src_lang == "tr":
            if not LANG_STATUS["ru"] and not LANG_STATUS["de"]: return
            system_prompt = (
                "You are an expert native chat translator. Translate the given Turkish message into natural, fluent Russian and German. "
                "Do NOT do literal word-for-word translation; use native conversational idioms. "
                "Output ONLY the two translated lines in this exact format, with no extra text or explanations:\n"
                "🇷🇺 [Russian Translation]\n"
                "🇩🇪 [German Translation]"
            )
        elif src_lang == "ru":
            if not LANG_STATUS["tr"] and not LANG_STATUS["de"]: return
            system_prompt = (
                "You are an expert native chat translator. Translate the given Russian message into natural, fluent Turkish and German. "
                "Do NOT do literal word-for-word translation; use native conversational idioms. "
                "Output ONLY the two translated lines in this exact format, with no extra text or explanations:\n"
                "🇹🇷 [Turkish Translation]\n"
                "🇩🇪 [German Translation]"
            )
        else: # de
            if not LANG_STATUS["tr"] and not LANG_STATUS["ru"]: return
            system_prompt = (
                "You are an expert native chat translator. Translate the given German message into natural, fluent Turkish and Russian. "
                "Do NOT do literal word-for-word translation; use native conversational idioms. "
                "Output ONLY the two translated lines in this exact format, with no extra text or explanations:\n"
                "🇹🇷 [Turkish Translation]\n"
                "🇷🇺 [Russian Translation]"
            )

        raw_translation = await query_ai(clean_text, system_prompt, max_tokens=150)
        if not raw_translation: return

        # İstek dışı kapalı diller varsa temizle
        lines = raw_translation.split("\n")
        valid_lines = []

        for line in lines:
            line_clean = line.strip()
            if not line_clean: continue

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
    app.add_handler(CommandHandler("kral", cmd_kral))
    app.add_handler(CommandHandler(["siralama", "sirallama", "puan"], cmd_siralama))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Viyana AI - Kusursuz Dinamik Çeviri Modu ile Yayında...")
    app.run_polling(drop_pending_updates=True)

