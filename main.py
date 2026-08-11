import logging
import random
import re
import json
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TELEGRAM_TOKEN = "8363449973:AAElwMlaNrlKJ7sh8PApYPxWb13YqrHJakU"
CEREBRAS_API_KEY = "csk-2nr3xkmt8x9eyfkc9hhc2nyrwf5nrx8kdt4pn8hwdjvewfxv"

CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
# MODEL ADI CEREBRAS API DOKÜMANLARINA GÖRE DÜZELTİLDİ:
CEREBRAS_MODEL = "llama-3.3-70b"

USER_SCORES = {}
LANG_STATUS = {"tr": True, "ru": True, "de": True}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SYSTEM_TRANSLATE_PROMPT = """
You are a professional native-level translator for a multilingual Telegram community chat (Turkish, Russian, German speakers).

Translate the given short chat message the way a real native speaker would translate it in a casual conversation:
- Natural, idiomatic, and contextually correct.
- NOT a robotic word-for-word translation.
- NEVER invent, add, or drop meaning that isn't in the original message.
- Preserve tone (greeting, joke, slang, question, etc.) exactly as a native speaker would.

You MUST respond with STRICT JSON ONLY. No explanations, no markdown, no code fences, no extra text before or after the JSON.

Depending on the detected source language of the input, return exactly these keys:

If input is Turkish or Azerbaijani:
{"ru": "<Russian translation>", "de": "<German translation>"}

If input is Russian:
{"tr": "<Turkish translation>", "de": "<German translation>"}

If input is German:
{"tr": "<Turkish translation>", "ru": "<Russian translation>"}

MANDATORY RULES:
1. ALWAYS include BOTH required keys.
2. NEVER leave a value empty and NEVER omit a key.
3. Output ONLY the raw JSON object.
"""

COMMAND_3LANG_PROMPT = """
Sana verilen metni veya görevi 3 dilde (Türkçe, Rusça, Almanca) yanıtla.
Çıktı formatı KESİNLİKLE şöyle olmalı:
🇹🇷 [Türkçe İfade]
🇷🇺 [Rusça İfade - Kiril]
🇩🇪 [Almanca İfade]
"""

class TranslationServiceError(Exception):
    pass

async def query_grok(prompt: str, system_prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {CEREBRAS_API_KEY.strip()}",
        "Content-Type": "application/json",
    }
    data = {
        "model": CEREBRAS_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(CEREBRAS_URL, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            
            error_msg = f"HTTP {response.status_code}: {response.text}"
            raise TranslationServiceError(error_msg)
    except Exception as e:
        raise TranslationServiceError(str(e))

def detect_language(text: str) -> str:
    if re.search(r'[\u0400-\u04FF]', text): return "ru"
    elif re.search(r'[äöüßÖÜß]', text) or any(w in text.lower().split() for w in ["ich", "ist", "und", "nicht", "das", "die", "der", "wie", "hallo"]): return "de"
    else: return "tr"

LANG_FLAGS = {"tr": "🇹🇷", "ru": "🇷🇺", "de": "🇩🇪"}
REQUIRED_TARGETS = {"tr": ["ru", "de"], "ru": ["tr", "de"], "de": ["tr", "ru"]}
SINGLE_LANG_NAMES = {"tr": "Turkish", "ru": "Russian", "de": "German"}

async def get_single_translation(clean_text: str, target: str) -> str:
    system_prompt = f"You are a native translator. Translate this short message into {SINGLE_LANG_NAMES[target]}. Respond with ONLY the translation text."
    raw = await query_grok(f'Translate this message: "{clean_text}"', system_prompt)
    return raw.strip().strip('"') if raw else ""

async def get_translation(clean_text: str, src_lang: str) -> dict:
    targets = REQUIRED_TARGETS.get(src_lang, [])
    if not targets: return {}

    for _ in range(2):
        raw = await query_grok(f'Translate this chat message: "{clean_text}"', SYSTEM_TRANSLATE_PROMPT)
        if not raw: continue

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match: continue

        try:
            data = json.loads(match.group(0))
            if all(str(data.get(t, "")).strip() for t in targets):
                return {t: str(data[t]).strip() for t in targets}
        except:
            continue

    result = {}
    for t in targets:
        translated = await get_single_translation(clean_text, t)
        if translated: result[t] = translated
    return result

def add_point(chat_id: int, user):
    if user.is_bot: return
    if chat_id not in USER_SCORES: USER_SCORES[chat_id] = {}
    uid = user.id
    if uid not in USER_SCORES[chat_id]:
        USER_SCORES[chat_id][uid] = {"name": user.first_name, "points": 0, "messages": 0}
    USER_SCORES[chat_id][uid]["points"] += random.randint(5, 15)
    USER_SCORES[chat_id][uid]["messages"] += 1
    USER_SCORES[chat_id][uid]["name"] = user.first_name

async def cmd_toggle_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    cmd = update.message.text.split()[0].replace("/", "").split("@")[0].lower()
    
    if cmd == "turkce":
        LANG_STATUS["tr"] = not LANG_STATUS["tr"]
        msg = f"🇹🇷 Türkçe Çeviri: {'AÇILDI ✅' if LANG_STATUS['tr'] else 'KAPATILDI ❌'}"
    elif cmd == "rusca":
        LANG_STATUS["ru"] = not LANG_STATUS["ru"]
        msg = f"🇷🇺 Rusça Çeviri: {'AÇILDI ✅' if LANG_STATUS['ru'] else 'KAPATILDI ❌'}"
    elif cmd == "almanca":
        LANG_STATUS["de"] = not LANG_STATUS["de"]
        msg = f"🇩🇪 Almanca Çeviri: {'AÇILDI ✅' if LANG_STATUS['de'] else 'KAPATILDI ❌'}"
    else: return
    await update.message.reply_text(msg)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = await query_grok("Hakkımda metni yaz: Ben Viyana Ai Yapay zeka botuyum. Ehed tarafından tasarlandım.", COMMAND_3LANG_PROMPT)
    if ans: await update.message.reply_text(ans)

async def cmd_burc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = " ".join(context.args) if context.args else "genel"
    ans = await query_grok(f"Kullanıcı için ({args}) burcu/fal hakkında eğlenceli yorum yap.", COMMAND_3LANG_PROMPT)
    if ans: await update.message.reply_text(ans)

async def cmd_kral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = await query_grok(f"Günün Kralı: {update.effective_user.first_name}. Kısa övgü yaz.", COMMAND_3LANG_PROMPT)
    if ans: await update.message.reply_text(ans)

async def cmd_siralama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scores = USER_SCORES.get(update.effective_chat.id, {})
    if not scores:
        await update.message.reply_text("🇹🇷 Henüz puan yok!\n🇷🇺 Пока нет очков!\n🇩🇪 Noch keine Punkte!")
        return
    text = "🏆 **PUAN SIRALAMASI / РЕЙТИНГ / RANGLISTE** 🏆\n\n"
    for idx, u in enumerate(sorted(scores.values(), key=lambda x: x["points"], reverse=True)[:5], 1):
        text += f"{idx}. **{u['name']}** — {u['points']} Pts\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.effective_message
        if not message or not message.text: return
        text = message.text.strip()
        
        if update.effective_user.is_bot or text.startswith("/"): return

        add_point(message.chat_id, update.effective_user)
        clean_text = re.sub(r'@\w+', '', text).strip()
        if len(clean_text.split()) < 1 or "http" in text: return

        src_lang = detect_language(clean_text)
        translations = await get_translation(clean_text, src_lang)

        if not translations: return

        valid_lines = [f"{LANG_FLAGS[t]} {translations[t]}" for t in REQUIRED_TARGETS.get(src_lang, []) if LANG_STATUS.get(t, True) and translations.get(t)]
        if valid_lines:
            await message.reply_text("\n".join(valid_lines))

    except TranslationServiceError as e:
        await update.effective_message.reply_text(f"🛑 API HATASI DETAYI:\n{str(e)}")

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

