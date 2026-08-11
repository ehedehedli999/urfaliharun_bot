import logging
import re
import httpx
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
)

TELEGRAM_TOKEN = "8363449973:AAEel1P8fp1b3eRhnbpDNM4Z6vdEbFQR8h0"
XAI_API_KEY = "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"

XAI_URL = "https://api.groq.com/openai/v1/chat/completions"
GROK_MODEL = "llama-3.3-70b-versatile"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# EXPERT TRANSLATOR PROMPT (AZERBAYCAN TÜRKÇESİ DAHİL)
SYSTEM_PROMPT = """
You are a world-class professional translator.
Your job is to translate short chat messages into highly natural, fluent, and correct target languages.

CRITICAL INSTRUCTIONS:
1. Understand informal Turkish, Azerbaijani Turkish (e.g., "salam necesen", "necesiniz", "cox"), and slang correctly before translating.
2. NEVER truncate sentences or leave incomplete phrases (e.g., never output "ich brauche" for greetings).
3. Do NOT include any explanations, source text, or extra conversation.
4. ONLY output lines starting with the corresponding flag emojis.

FORMAT REQUIRED:
If input is Turkish / Azerbaijani:
🇷🇺 [Natural Russian translation]
🇩🇪 [Natural German translation]

If input is Russian:
🇹🇷 [Natural Turkish translation]
🇩🇪 [Natural German translation]

If input is German:
🇹🇷 [Natural Turkish translation]
🇷🇺 [Natural Russian translation]
"""

def detect_language(text: str) -> str:
    # Kiril alfabesi -> Rusça
    if re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    # Almanca karakteristik kelimeler / karakterler
    elif re.search(r'[äöüßÖÜß]', text) or any(w in text.lower().split() for w in ["ich", "ist", "und", "nicht", "das", "die", "der", "wie", "hallo"]):
        return "de"
    else:
        return "tr"

async def get_translation(text: str, source_lang: str) -> str:
    user_prompt = f"Translate this message accurately:\n\"{text}\""

    try:
        headers = {
            "Authorization": f"Bearer {XAI_API_KEY.strip()}",
            "Content-Type": "application/json",
        }
        data = {
            "model": GROK_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 150
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.effective_message
        if not message or not message.text:
            return

        text = message.text.strip()

        # Bot mesajlarını ve komutları atla
        if update.effective_user.is_bot or text.startswith("/"):
            return

        # Çok kısa veya link içeren girdileri atla
        words = text.split()
        if len(words) < 2 or "http" in text:
            return

        src_lang = detect_language(text)
        raw_translation = await get_translation(text, src_lang)

        if not raw_translation:
            return

        # ÇIKTIYI KOD SEVİYESİNDE SÜZGEÇTEN GEÇİR
        lines = raw_translation.split("\n")
        valid_lines = []

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            # Kaynak dille aynı olan bayraklı satırı yazma
            if src_lang == "tr" and line_clean.startswith("🇹🇷"):
                continue
            if src_lang == "ru" and line_clean.startswith("🇷🇺"):
                continue
            if src_lang == "de" and line_clean.startswith("🇩🇪"):
                continue

            if any(line_clean.startswith(flag) for flag in ["🇹🇷", "🇷🇺", "🇩🇪"]):
                valid_lines.append(line_clean)

        if valid_lines:
            final_output = "\n".join(valid_lines)
            await message.reply_text(final_output)

    except Exception as e:
        logger.error(f"Handle error: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Viyana AI Güncellenmiş Çeviri Sistemi İle Yayında...")
    app.run_polling(drop_pending_updates=True)
