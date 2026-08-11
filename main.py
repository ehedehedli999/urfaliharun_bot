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
# MODELİ 70B PARAMETRELİ MÜKEMMEL MODELLE DEĞİŞTİRDİK
GROK_MODEL = "llama-3.3-70b-versatile"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a professional, highly precise translation engine.
Translate the input text into the requested target languages accurately.

RULES:
1. Do NOT write conversational filler like 'Sure', 'Here is the translation'.
2. Do NOT write in the source language.
3. Output MUST ONLY contain lines starting with flag emojis.
4. Keep the translation natural and grammatically correct.
"""

def detect_language(text: str) -> str:
    # Kiril alfabesi -> Rusça
    if re.search(r'[\u0400-\u04FF]', text):
        return "ru"
    # Almanca karakteristik kelimeler / karakterler
    elif re.search(r'[äöüßÖÜß]', text) or any(w in text.lower().split() for w in ["ich", "ist", "und", "nicht", "das", "die", "der", "wie", "allen", "dank"]):
        return "de"
    else:
        return "tr"

async def get_translation(text: str, source_lang: str) -> str:
    if source_lang == "tr":
        target_instructions = "Translate this Turkish text into Russian and German ONLY.\nFormat:\n🇷🇺 [Russian Translation]\n🇩🇪 [German Translation]"
    elif source_lang == "ru":
        target_instructions = "Translate this Russian text into Turkish and German ONLY.\nFormat:\n🇹🇷 [Turkish Translation]\n🇩🇪 [German Translation]"
    else:
        target_instructions = "Translate this German text into Turkish and Russian ONLY.\nFormat:\n🇹🇷 [Turkish Translation]\n🇷🇺 [Russian Translation]"

    user_prompt = f"Text: \"{text}\"\n\n{target_instructions}"

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
            "temperature": 0.0,
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

        # Komutları ve bot mesajlarını atla
        if update.effective_user.is_bot or text.startswith("/"):
            return

        # Etiketleri veya linkleri temizle / filtrele
        words = text.split()
        if len(words) < 2 or "http" in text:
            return

        # Dil tespiti yap
        src_lang = detect_language(text)

        # Çeviri iste
        raw_translation = await get_translation(text, src_lang)

        if not raw_translation:
            return

        # ÇIKTIYI PYTHON SEVİYESİNDE TEMİZLE (AI HATA YAPSA BİLE DÜZELTİR)
        lines = raw_translation.split("\n")
        valid_lines = []

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            # Kaynak dille aynı bayrağı içeren satırı KESİNLİKLE sil
            if src_lang == "tr" and line_clean.startswith("🇹🇷"):
                continue
            if src_lang == "ru" and line_clean.startswith("🇷🇺"):
                continue
            if src_lang == "de" and line_clean.startswith("🇩🇪"):
                continue

            # Sadece geçerli bayraklarla başlayanları al
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
    
    print("Viyana AI Llama-3.3-70B Modeli İle Yayında...")
    app.run_polling(drop_pending_updates=True)
