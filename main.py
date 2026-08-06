
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

# API açarları
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

# Urfalı Harun şəxsiyyəti və tərcümə/cavablandırma təlimatı
SYSTEM_PROMPT = (
    "Senin adın Urfalı Harundur. Seni Ehed tasarladı (yarattı). "
    "Eğer biri sana adını sorarsa, mutlaka 'Benim ismim Urfalı Harun' de. "
    "Eğer biri seni kimin yarattığını sorarsa, 'Beni Ehed tasarladı' de. "
    "Sen aynı zamanda profesyonel bir çevirmen ve akıllı bir asistansın: "
    "- Türkçe yazılanları Almanca ve Rusçaya, "
    "- Almanca yazılanları Türkçe ve Rusçaya, "
    "- Rusça yazılanları Almanca ve Türkçeye çevirebilirsin. "
    "Metinde özel bir dil çevirisi isteniyorsa çeviriyi yap. Genel sorularda ise bir yapay zeka asistanı olarak yardımcı ol."
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    bot_username = context.bot.username
    is_group = chat.type in ["group", "supergroup"]

    if not message:
        return

    # --- 1. SESLİ MESAJLARIN İŞLENMESİ ---
    if message.voice:
        # A) Botun kendi mesajına reply (yanıt) olarak ses atıldıysa
        if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == context.bot.id:
            try:
                file = await context.bot.get_file(message.voice.file_id)
                voice_path = "temp_voice.ogg"
                await file.download_to_drive(voice_path)

                with open(voice_path, "rb") as audio_file:
                    transcription = groq_client.audio.transcriptions.create(
                        file=(voice_path, audio_file.read()),
                        model="whisper-large-v3",
                        language="az",
                    )
                user_text = transcription.text

                if os.path.exists(voice_path):
                    os.remove(voice_path)

                if not user_text.strip():
                    await message.reply_text("Sesinizi duyamadım, lütfen tekrar edin.")
                    return

                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_text}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                ai_reply = chat_completion.choices[0].message.content
                await message.reply_text(ai_reply)

            except Exception as e:
                logger.error(f"Ses hatası: {e}")
                await message.reply_text("Sesiniz işlenirken bir hata oluştu.")
            return

        # B) Grupta başkasının sesli mesajı reply edildiyse (Çeviri için)
        if message.reply_to_message and message.reply_to_message.voice:
            try:
                file = await context.bot.get_file(message.reply_to_message.voice.file_id)
                voice_path = "other_voice.ogg"
                await file.download_to_drive(voice_path)

                with open(voice_path, "rb") as audio_file:
                    transcription = groq_client.audio.transcriptions.create(
                        file=(voice_path, audio_file.read()),
                        model="whisper-large-v3"
                    )
                other_text = transcription.text

                if os.path.exists(voice_path):
                    os.remove(voice_path)

                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Bu sesli mesajı Türkçe, Almanca ve Rusça dillere çevir: {other_text}"}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                await message.reply_text(chat_completion.choices[0].message.content)
            except Exception as e:
                logger.error(f"Ses çeviri hatası: {e}")
            return

        # Grupta ortaya atılan rastgele seslere karışmasın
        if is_group and not message.reply_to_message:
            return

    # --- 2. METİN MESAJLARI İÇİN (YALNIZCA ETİKETLENDİĞİNDE) ---
    if is_group:
        is_mentioned = False
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

        if not is_mentioned:
            return

    # --- 3. METİNLERE VE ÇEVİRİLERE AI CEVABI ---
    text_to_process = message.text or message.caption
    if text_to_process:
        clean_text = text_to_process.replace(f"@{bot_username}", "").strip()

        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": clean_text}
                ],
                model="llama-3.3-70b-versatile",
            )
            ai_response = chat_completion.choices[0].message.content
            await message.reply_text(ai_response)
        except Exception as e:
            logger.error(f"AI hatası: {e}")
            await message.reply_text("İsteğiniz işlenirken bir hata oluştu.")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE | filters.PHOTO, handle_message))
    logger.info("Urfalı Harun çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()

