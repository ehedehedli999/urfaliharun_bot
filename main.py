import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = (
    "Senin adın Urfalı Harundur. Seni Ehed tasarladı. "
    "Doğal, samimi ve akıllı bir yapay zeka asistanısın. "
    "Sana hangi dilde (Rusça, İngilizce, Türkçe vb.) soru sorulursa sorulsun, "
    "kesinlikle kullanıcının sorduğu dilde akıcı bir şekilde yanıt ver. "
    "Sadece doğrudan sorulduğunda adını veya seni kimin tasarladığını söyle. "
    f"Şu anki tarih ve saat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
)

TRANSLATE_PROMPT = (
    "Sen profesyonel bir çevirmensin. Sana gelen metni anlamını bozmadan, "
    "akıcı bir şekilde tam olarak şu 3 dile çevir ve başka hiçbir açıklama yapmadan "
    "yalnızca şu formatta ver:\n"
    "Türkçe: [çeviri]\n"
    "İngilizce: [çeviri]\n"
    "Almanca: [çeviri]"
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    bot_username = context.bot.username
    is_group = chat.type in ["group", "supergroup"]

    if not message:
        return

    text_to_process = ""

    # --- 1. SƏSLİ MESAJ VƏ YA VİDEONUN İÇİNDƏKİ SƏS ---
    if message.voice or message.video or message.video_note:
        try:
            media_file = message.voice or message.video or message.video_note
            file = await context.bot.get_file(media_file.file_id)
            file_path = "temp_media.mp4"
            await file.download_to_drive(file_path)

            with open(file_path, "rb") as audio_file:
                transcription = groq_client.audio.transcriptions.create(
                    file=(file_path, audio_file.read()),
                    model="whisper-large-v3"
                )
            text_to_process = transcription.text
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Media səs xətası: {e}")

    if not text_to_process:
        text_to_process = message.text or message.caption

    if not text_to_process:
        return

    is_mentioned = False
    if f"@{bot_username}" in text_to_process:
        is_mentioned = True
    elif message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                mention_text = text_to_process[entity.offset : entity.offset + entity.length]
                if mention_text.lower() == f"@{bot_username}".lower():
                    is_mentioned = True

    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == context.bot.id

    if is_mentioned or is_reply_to_bot:
        clean_text = text_to_process.replace(f"@{bot_username}", "").strip()
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": clean_text if clean_text else "Merhaba"}
                ],
                model="llama-3.3-70b-versatile",
            )
            await message.reply_text(chat_completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"AI xətası: {e}")
    else:
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": TRANSLATE_PROMPT},
                    {"role": "user", "content": text_to_process}
                ],
                model="llama-3.3-70b-versatile",
            )
            await message.reply_text(chat_completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"Tərcümə xətası: {e}")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE | filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.VIDEO_NOTE, handle_message))
    logger.info("Urfalı Harun işləyir...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
