import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

BASE_SYSTEM_PROMPT = (
    "Sen Urfalı Harun adında zeki, akıcı ve doğrudan yanıt veren bir yapay zeka asistanısın. "
    "Sana sorulan sorulara C1 seviyesinde, net, insan gibi doğal bir dille cevap ver. "
    "DİKKAT: Kullanıcıya asla 'Nasıl yardımcı olabilirim?', 'Başka bir sorunuz var mı?' "
    "veya 'Hangi detayları ekleyeyim?' gibi takip veya onay soruları SORMA! "
    "Doğrudan istenen cevabı ver ve bitir."
)

TRANSLATE_PROMPT = (
    "Sen C1 ve üstü seviyede profesyonel bir çevirmensin. "
    "Sana gelen metni anlamını, tonunu ve doğallığını bozmadan mükemmel bir şekilde şu 3 dile çevir "
    "ve başka hiçbir açıklama eklemeden yalnızca şu formatta yanıt ver:\n\n"
    "Türkçe: [çeviri]\n"
    "Rusça: [çeviri]\n"
    "Almanca: [çeviri]"
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return

    text = message.text.strip()
    bot_username = context.bot.username

    is_mentioned = False
    if f"@{bot_username}" in text:
        is_mentioned = True
    elif message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention_text = text[entity.offset : entity.offset + entity.length]
                if mention_text.lower() == f"@{bot_username}".lower():
                    is_mentioned = True

    is_reply_to_bot = (
        message.reply_to_message 
        and message.reply_to_message.from_user 
        and message.reply_to_message.from_user.id == context.bot.id
    )

    clean_text = text.replace(f"@{bot_username}", "").strip()

    # 1. BOTA ETİKET VEYA YANIT ATILDIYSA: YAPAY ZEKA DESTEĞİ
    if is_mentioned or is_reply_to_bot:
        if gemini_client:
            try:
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=clean_text if clean_text else "Merhaba",
                    config=types.GenerateContentConfig(
                        system_instruction=BASE_SYSTEM_PROMPT
                    )
                )
                await message.reply_text(response.text)
            except Exception as e:
                logger.error(f"Gemini AI hatası: {e}")
                await message.reply_text("Bir hata oluştu, lütfen GEMINI_API_KEY değerini kontrol edin.")

    # 2. NORMAL YAZILAN MESAJLAR: OTOMATİK C1 ÇEVİRİ
    else:
        if gemini_client:
            try:
                response = gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=text,
                    config=types.GenerateContentConfig(
                        system_instruction=TRANSLATE_PROMPT
                    )
                )
                await message.reply_text(response.text)
            except Exception as e:
                logger.error(f"Gemini Çeviri hatası: {e}")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot sadece Gemini C1 Çeviri ve Yapay Zeka modunda çalışıyor...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
