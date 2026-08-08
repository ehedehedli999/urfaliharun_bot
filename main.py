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

# Soru sormayan, doğrudan profesyonel görsel promptu üreten sistem promptu
BASE_SYSTEM_PROMPT = (
    "Sen Urfalı Harun'sun. Asla gevezelik yapma, asla 'Şöyle yapayım mı?', 'İstiyor musun?' diye soru sorma. "
    "Kullanıcı bir resim gönderdiğinde veya bir mekân/konsept (örneğin Miami, deniz kenarı, araba vb.) istediğinde; "
    "derhal o sahneyi en ince ayrıntısına kadar anlatan, yapay zeka görsel üreticileri (Midjourney, DALL-E vb.) için kusursuz ve profesyonel bir **görsel prompt** hazırla. "
    "Tarihsel Maya medeniyeti ile Miami'yi asla karıştırma. 'Maya' geçse bile coğrafi konum veya konsept olarak ele al. "
    "Sohbeti uzatma, doğrudan profesyonel İngilizce veya Türkçe görsel promptunu ve kısa, net açıklamasını verip geç."
    "Şu anki karakter rolün ve davranışın:\n{persona_instruction}"
)

PERSONAS = {
    "agresif": "Ağzı bozuk, sinirli, dik başlı ama işini tam yapan bir dayısın. Lafı hiç uzatmazsın.",
    "romantik": "Şair ruhlu ama gevezelik yapmadan doğrudan estetik ve görsel odaklı konuşan birisin.",
    "zeki": "Analitik, net, doğrudan sonuç odaklı ve profesyonel bir uzmansın.",
    "insan": "Samimi ama lafı uzatmayan, doğrudan isteği yerine getiren bir dostsun.",
    "espirici": "Mizahı seven ama işini de anında ve net yapan bir komedyensin."
}

ALL_MODS_LIST = "agresif, romantik, zeki, insan, espirici"

TRANSLATE_PROMPT = (
    "Sen C1 seviyesinde profesyonel bir çevirmensin. Sana gelen metni anlamını ve tonunu bozmadan, "
    "en akıcı ve doğal şekilde tam olarak şu 3 dile çevir ve başka hiçbir açıklama yapmadan "
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
    is_photo_related = False

    # --- 1. RESİM VE MEDYA KONTROLÜ ---
    if message.photo:
        is_photo_related = True
        caption = message.caption or message.text or ""
        text_to_process = f"[Kullanıcı bir fotoğraf gönderdi ve şunu istiyor]: {caption}"
    elif message.reply_to_message:
        if message.reply_to_message.photo or (message.reply_to_message.caption and "fotoğraf" in message.reply_to_message.caption.lower()):
            is_photo_related = True
            reply_text = message.text or message.caption or ""
            text_to_process = f"[Kullanıcı bir fotoğrafa yanıt vererek şunu istiyor]: {reply_text}"
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

    if is_photo_related or is_mentioned or is_reply_to_bot:
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
            announcement_text = f"[{new_mode_detected} moduna geçildi]\n"

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
                    {"role": "user", "content": clean_text if clean_text else "Görseli hazırla"}
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
    logger.info("Urfalı Harun Net ve Direkt Modda İşləyir...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
