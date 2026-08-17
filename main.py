import os
import json
import logging
import urllib.request

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

from openai import OpenAI

# ============================================================
# 5'Lİ ZİNCİRVARİ EHTİYAT (FALLBACK) GROQ API AÇARLARI
# ============================================================

GROQ_API_KEYS = [
    "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",  # 1. Açar
    "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",  # 2. Açar
    "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",  # 3. Açar
    "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",  # 4. Açar
    "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",  # 5. Açar
]

TELEGRAM_BOT_TOKEN = "8363449973:AAElwMlaNrlKJ7sh8PApYPxWb13YqrHJakU"
GROUP_CHAT_ID = "" 

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN bulunamadı.")

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
    
    for index, api_key in enumerate(GROQ_API_KEYS, start=1):
        if not api_key:
            continue
            
        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                max_tokens=400,
                temperature=0.0,
            )
            
            if response.choices and response.choices[0].message.content:
                content = response.choices[0].message.content
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
        return  # Əmrləri oxumur

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
