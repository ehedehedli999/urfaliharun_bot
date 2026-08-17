import os
import json
import logging
import urllib.request
import urllib.error

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# ============================================================
# 5'Lİ ZİNCİRVARİ EHTİYAT (FALLBACK) GROQ API AÇARLARI
# ============================================================

GROQ_API_KEYS = [
    os.getenv("GROQ_API_KEY_1", "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"),
    os.getenv("GROQ_API_KEY_2", "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"),
    os.getenv("GROQ_API_KEY_3", "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"),
    os.getenv("GROQ_API_KEY_4", "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"),
    os.getenv("GROQ_API_KEY_5", "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"),
]
GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8363449973:AAF6GLHfm_rhtafV_ni_yJB4cZbynkAKCMM")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

MODEL_NAME = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """Sen profesyonel bir çeviri motorusun. Kullanıcının yazdığı metni algıla ve tam olarak şu JSON formatında İngilizce (en), Almanca (de), Rusça (ru) ve Türkçe (tr) karşılıklarını ver. Başka hiçbir açıklama yazma:

{
  "detected_lang": "az",
  "tr": "türkçe çeviri",
  "de": "almanca çeviri",
  "ru": "rusça çeviri",
  "en": "ingilizce çeviri"
}
"""

def translate_text(text: str) -> str:
    content = ""
    url = "https://api.groq.com/openai/v1/chat/completions"

    for index, api_key in enumerate(GROQ_API_KEYS, start=1):
        if not api_key:
            continue
            
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 400,
            "temperature": 0.0
        }

        # Cloudflare blokunu keçmək üçün User-Agent əlavə olundu
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                content = res_data['choices'][0]['message']['content']
                if content:
                    break
        except Exception as e:
            logger.warning(f"⚠️ Açar #{index} xəta verdi: {e}. Növbətiyə keçilir...")

    if not content:
        return "⚠️ Xəta: Heç bir açar cavab vermədi."

    try:
        data = json.loads(content)
        tr = data.get("tr", "")
        de = data.get("de", "")
        ru = data.get("ru", "")
        en = data.get("en", "")

        result = []
        if en: result.append(f"🇬🇧 {en}")
        if de: result.append(f"🇩🇪 {de}")
        if ru: result.append(f"🇷🇺 {ru}")
        if tr: result.append(f"🇹🇷 {tr}")

        return "\n".join(result)
    except Exception as e:
        return f"Çeviri xətası: {content}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return

    text = message.text.strip()
    if not text or text.startswith("/"):
        return

    translated = translate_text(text)
    if translated:
        await message.reply_text(translated)

def main():
    try:
        clear_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True"
        urllib.request.urlopen(clear_url, timeout=5)
    except:
        pass

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 BOT İŞƏ DÜŞDÜ!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
