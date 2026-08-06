import os
import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq
from gtts import gTTS

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = (
    "Senin adın Urfalı Harundur. Seni Ehed tasarladı. "
    "Doğal, samimi ve akıllı bir yapay zeka asistanı olarak yanıt ver. "
    "Sadece doğrudan sorulduğunda adını veya seni kimin tasarladığını söyle."
)

TRANSLATE_PROMPT = (
    "Gelen bu metni otomatik olarak şu 3 dile çevir ve sadece şu formatta ver: "
    "Türkçe: [çeviri] "
    "Almanca: [çeviri] "
    "Rusça: [çeviri]"
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    bot_username = context.bot.username
    is_group = chat.type in ["group", "supergroup"]

    if not message:
        return

    # --- 1. SƏSLİ MESAJLAR ---
    if message.voice:
        # A) Botun mesajına səsli reply edilibsə -> Səsli cavab ver
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
                    await message.reply_text("Səsinizi eşidə bilmədim.")
                    return

                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_text}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                ai_reply = chat_completion.choices[0].message.content

                # Cavabı səsli mesaja çevirib göndəririk
                tts = gTTS(text=ai_reply, lang='tr')
                output_audio = "reply_voice.ogg"
                tts.save(output_audio)

                with open(output_audio, "rb") as voice_file:
                    await message.reply_voice(voice=voice_file)

                if os.path.exists(output_audio):
                    os.remove(output_audio)

            except Exception as e:
                logger.error(f"Səs xətası: {e}")
            return

        # B) Başqasının səsinə reply edilibsə -> 3 dilə tərcümə et
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
                        {"role": "system", "content": TRANSLATE_PROMPT},
                        {"role": "user", "content": other_text}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                await message.reply_text(chat_completion.choices[0].message.content)
            except Exception as e:
                logger.error(f"Səs tərcümə xətası: {e}")
            return

        if is_group and not message.reply_to_message:
            return

    # --- 2. MƏTN, FOTO VƏ VİDEO AÇIQLAMALARI (CAPTION) ---
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

    if is_mentioned:
        clean_text = text_to_process.replace(f"@{bot_username}", "").strip()
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": clean_text}
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
    application.add_handler(MessageHandler(filters.TEXT | filters.VOICE | filters.PHOTO | filters.VIDEO | filters.ANIMATION, handle_message))
    logger.info("Urfalı Harun 7/24 işləyir...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
