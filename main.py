import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)
from openai import OpenAI

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = "8363449973:AAF6GLHfm_rhtafV_ni_yJB4cZbynkAKCMM"

# OpenRouter API açarı
OPENROUTER_API_KEYS = [
    "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"
]

# Groq API açarı
GROQ_API_KEY = "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"

SYSTEM_PROMPT = """Sen C2 (Master) seviyesinde profesyonel bir çeviri ve lokalizasyon uzmanısın. Kullanıcının yazdığı metni; deyimleri, mecazları, kültürel bağlamı, tonu ve en ince anlam nuanslarını tamamen koruyarak çevir. 

KURAL:
- Eğer gelen metin **İngilizce** yazılmışsa, İngilizceye çevirme; sadece şu 3 dile çevir ve çıktıyı tam olarak bu formatta ver (başka hiçbir şey ekleme):
🇩🇪 Almanca: [...]
🇷🇺 Rusça: [...]
🇹🇷 Türkçe: [...]

- Eğer gelen metin **başka bir dilde** yazılmışsa, şu 4 dile çevir ve çıktıyı tam olarak bu formatta ver (başka hiçbir şey ekleme):
🇬🇧 İngilizce: [...]
🇩🇪 Almanca: [...]
🇷🇺 Rusça: [...]
🇹🇷 Türkçe: [...]

Kelimesi kelimesine değil, hedef dilde anadili olan birinin kuracağı en doğal, akıcı ve profesyonel cümle yapısını kullan.
"""

def translate_with_fallback(text: str) -> str:
    last_error = ""
    
    # 1. Addim: OpenRouter ilə yoxla
    for index, api_key in enumerate(OPENROUTER_API_KEYS, start=1):
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
            completion = client.chat.completions.create(
                model="deepseek/deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=600,
                temperature=0.1
            )
            content = completion.choices[0].message.content
            if content:
                logger.info(f"Uğurla işlədi: OpenRouter")
                return content.strip()
        except Exception as e:
            last_error = str(e)
            logger.error(f"❌ OpenRouter xəta verdi: {last_error}")

    # 2. Addim: Groq ilə yoxla
    try:
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=GROQ_API_KEY
        )
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            max_tokens=600,
            temperature=0.1
        )
        content = completion.choices[0].message.content
        if content:
            logger.info("Uğurla işlədi: Groq")
            return content.strip()
    except Exception as e:
        last_error = str(e)
        logger.error(f"❌ Groq Xətası: {last_error}")

    return f"⚠️ Xəta: Bütün sistemlər yoxlanıldı. Son xəta: {last_error}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text or message.text.startswith("/"):
        return

    translated = translate_with_fallback(message.text.strip())
    await message.reply_text(translated)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Telegram xətası: {context.error}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    logger.info("🤖 BOT HAZIRDIR VƏ İŞLƏYİR!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
