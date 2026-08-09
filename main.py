import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# TOKENLER
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# GROQ CLIENT
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# SADE YAPAY ZEKA SİSTEM PROMPTU
BASE_SYSTEM_PROMPT = (
    "Sen Urfalı Harun adında zeki, net ve doğrudan cevap veren bir yapay zeka asistanısın. "
    "Sana sorulan sorulara akıcı, net ve insan gibi doğal bir şekilde yanıt ver. "
    "DİKKAT: Kullanıcıya asla 'Nasıl yardımcı olabilirim?', 'Başka bir sorunuz var mı?' "
    "veya 'Hangi detayları istersiniz?' gibi onay veya devam soruları SORMA! "
    "Doğrudan cevabı ver ve konuyu kapat."
)

# ULTRA C1 ÇEVİRİ PROMPTU
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

    # Etiket veya Yanıtlama Kontrolü
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
        if groq_client:
            try:
                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": BASE_SYSTEM_PROMPT},
                        {"role": "user", "content": clean_text if clean_text else "Merhaba"}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                await message.reply_text(chat_completion.choices[0].message.content)
            except Exception as e:
                logger.error(f"AI hatası: {e}")

    # 2. NORMAL YAZILAN MESAJLAR: OTOMATİK C1 ÇEVİRİ
    else:
        if groq_client:
            try:
                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": TRANSLATE_PROMPT},
                        {"role": "user", "content": text}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                await message.reply_text(chat_completion.choices[0].message.content)
            except Exception as e:
                logger.error(f"Çeviri hatası: {e}")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot sadece C1 Çeviri ve Yapay Zeka modunda çalışıyor...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
