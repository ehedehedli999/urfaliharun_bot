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

# --- SOHBETLERE ÖZEL AKTİF MOD HAFIZASI ---
chat_modes = {}

BASE_SYSTEM_PROMPT = (
    "Senin adın Urfalı Harundur. Seni Ehed tasarladı. "
    "Şu anki tarih ve saat: {datetime}. "
    "Sana hangi dilde soru sorulursa sorulsun, kesinlikle kullanıcının sorduğu dilde "
    "C1 seviyesinde, son derece akıcı, zeki ve insan gibi doğal bir şekilde yanıt ver. "
    "Eğer kullanıcı sana bir resim gönderip 'bu resmi dağda yap', 'arabada yap' veya benzeri bir konsept değişikliği isterse; "
    "resim düzenleme/yaratma yönetmeni gibi davranarak o karakteri ve ortamı harmanlayan profesyonel bir görsel promptu ve Urfalı Harun tarzı eğlenceli bir açıklama sun. "
    "Şu anki karakter rolün və davranışın:\n{persona_instruction}"
)

PERSONAS = {
    "agresif": "Ağzı bozuk, sinirli, dik başlı, az fırça kayan ama özünde sadık bir dayısın. Her şeye söylenerek ve sert bir üslupla cevap ver.",
    "romantik": "Aşırı duygulu, şair ruhlu, her cümlesi aşk, sevgi ve melankoli kokan bir romancısın.",
    "zeki": "Her şeyi bilen, akademik, entelektüel, stratejik düşünen ve cool bir dahi uzmansın.",
    "insan": "Oldukça doğal, samimi, mahalleden biri gibi, sıradan və içten konuşan bir dostsun.",
    "espirici": "Espriyi patlatan, mizahı seven, sürekli laf sokan, esprili ve neşeli bir komedyensin."
}

ALL_MODS_LIST = "agresif, romantik, zeki, insan, espirici"

TRANSLATE_PROMPT = (
    "Sen C1 seviyesinde profesyonel bir çevirmensin. Sana gelen metni anlamını ve tonunu bozmadan, "
    "en akıcı və doğal şekilde tam olarak şu 3 dile çevir ve başka hiçbir açıklama yapmadan "
    "yalnızca şu formatta ver:\n"
    "Türkçe: [çeviri]\n"
    "Rusça: [çeviri]\n"
    "Almanca: [çeviri]"
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    chat = update.effective_chat
    bot_username = context.bot.username
    chat_id = chat.id

    if not message:
        return

    text_to_process = ""

    # --- 1. RESİM VE MEDYA / SƏS İŞLEMLƏRİ ---
    if message.photo:
        caption = message.caption or ""
        text_to_process = f"[Kullanıcı bir fotoğraf gönderdi ve şunu istiyor]: {caption}"
    elif message.voice or message.video or message.video_note:
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

    if message.photo or is_mentioned or is_reply_to_bot:
        clean_text = text_to_process.replace(f"@{bot_username}", "").strip()
        
        if chat_id not in chat_modes:
            chat_modes[chat_id] = "insan"

        new_mode_detected = None
        clean_lower = clean_text.lower()
        for mode_key in PERSONAS.keys():
            if mode_key in clean_lower:
                new_mode_detected = mode_key
                clean_text = clean_text.replace(mode_key, "").strip()
                break

        announcement_text = ""
        if new_mode_detected and new_mode_detected != chat_modes[chat_id]:
            chat_modes[chat_id] = new_mode_detected
            announcement_text = (
                f"Şu an {new_mode_detected} moddayım ve {new_mode_detected} karakterine geçiş yaptım! "
                f"Modu değiştirmek isterseniz diğer karakterlerim şunlar: {ALL_MODS_LIST}.\n\n"
            )

        active_mode = chat_modes[chat_id]
        persona_rule = PERSONAS[active_mode]

        current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        system_prompt = BASE_SYSTEM_PROMPT.format(
            datetime=current_time_str,
            persona_instruction=persona_rule
        )

        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": clean_text if clean_text else "Merhaba"}
                ],
                model="llama-3.3-70b-versatile",
            )
            
            bot_reply = chat_completion.choices[0].message.content
            final_response = announcement_text + bot_reply
            
            await message.reply_text(final_response)
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
    logger.info("Urfalı Harun Temiz Modda işləyir...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
