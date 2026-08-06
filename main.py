import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq

# Logging quraşdırması
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# API açarları (Render Environment Variables-dən oxunacaq)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  message = update.effective_message
  chat = update.effective_chat
  bot_username = context.bot.username
  is_group = chat.type in ["group", "supergroup"]

  if not message:
    return

  # --- 1. SƏSLİ MESAJLARIN İŞLƏNMƏSİ ---
  if message.voice:
    # A) Əgər botun öz mesajına reply (cavab) olaraq səs atılıbsa -> Səsli cavab ver
    if (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == context.bot.id
    ):
      try:
        # Səs faylını yüklə
        file = await context.bot.get_file(message.voice.file_id)
        voice_path = "temp_voice.ogg"
        await file.download_to_drive(voice_path)

        # Groq Whisper ilə səsi mətə çevir (Speech-to-Text)
        with open(voice_path, "rb") as audio_file:
          transcription = groq_client.audio.transcriptions.create(
              file=(voice_path, audio_file.read()),
              model="whisper-large-v3",
              language="az",
          )
        user_text = transcription.text

        # Müvəqqəti faylı sil
        if os.path.exists(voice_path):
          os.remove(voice_path)

        if not user_text.strip():
          await message.reply_text(
              "Səsinizi aydın eşidə bilmədim, zəhmət olmasa bir də"
              " təkrarlayın."
          )
          return

        # Groq LLM-dən cavab al
        chat_completion = groq_client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": user_text,
            }],
            model="llama-3.3-70b-versatile",
        )
        ai_reply = chat_completion.choices[0].message.content

        # Hələlik səsli cavab funksiyası üçün mətni səsə çevirmə (TTS) əlavə olunmayıbsa,
        # cavabı mətn/səs şəklində göndərə bilərik. İndilik mətn cavabı qaytarırıq (və ya TTS inteqrasiya edə bilərsən):
        await message.reply_text(ai_reply)

      except Exception as e:
        logger.error(f"Səs işlənərkən xəta baş verdi: {e}")
        await message.reply_text("Səsinizi emal edərkən xəta baş verdi.")
      return

    # B) Əgər başqasının səsli mesajına reply edilibsə -> Tərcümə/Cavab məntiqi
    if message.reply_to_message and message.reply_to_message.voice:
      # İstəsəniz buraya başqasının səsini tərcümə etmə funksiyasını əlavə edə bilərsiniz.
      pass

    # Əgər qrupda sadəcə ortaya səs atılıbsa və bot reply olunmayıbsa - QARIŞMA
    if is_group and not message.reply_to_message:
      return

  # --- 2. MƏTN MESAJLARI ÜÇÜN (YALNIZ ETİKETLƏNDİKDƏ) ---
  if is_group:
    is_mentioned = False

    # Mətnin içində @bot_username yoxlanışı
    if message.text and f"@{bot_username}" in message.text:
      is_mentioned = True
    elif message.caption and f"@{bot_username}" in message.caption:
      is_mentioned = True
    elif message.entities:
      for entity in message.entities:
        if entity.type == "mention":
          mention_text = message.text[entity.offset : entity.offset + entity.length]
          if mention_text.lower() == f"@{bot_username}".lower():
            is_mentioned = True

    # Əgər qrupdadır və bot etiketlənməyibsə, mesajı burax
    if not is_mentioned:
      return

  # --- 3. MƏTNLƏRƏ AI CAVABI ---
  text_to_process = message.text or message.caption
  if text_to_process:
    # Botun adını mətndən təmizləyək ki, AI təmiz sualı görsün
    clean_text = text_to_process.replace(f"@{bot_username}", "").strip()

    try:
      chat_completion = groq_client.chat.completions.create(
          messages=[{"role": "user", "content": clean_text}],
          model="llama-3.3-70b-versatile",
      )
      ai_response = chat_completion.choices[0].message.content
      await message.reply_text(ai_response)
    except Exception as e:
      logger.error(f"AI cavab verərkən xəta: {e}")
      await message.reply_text(
          "Sorğunuzu yerinə yetirərkən xəta baş verdi."
      )


def main():
  # Telegram Bot Application quraşdırması
  application = Application.builder().token(TELEGRAM_TOKEN).build()

  # Bütün mesajları (həm səs, həm mətn) tək bir handler vasitəsilə idarə edirik
  application.add_handler(
      MessageHandler(
          filters.TEXT | filters.VOICE | filters.PHOTO, handle_message
      )
  )

  # Botu işə sal
  logger.info("Bot işə düşdü...")
  application.run_polling()


if __name__ == "__main__":
  main()


