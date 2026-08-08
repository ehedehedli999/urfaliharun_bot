import os
import logging
import base64
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
    "Sana hangi dilde (Türkçe, Rusça, Almanca vb.) soru sorulursa sorulsun, kesinlikle kullanıcının sorduğu dilde "
    "C1 seviyesinde, son derece akıcı, zeki ve insan gibi doğal bir şekilde yanıt ver. "
    "Sen 'Game of Sultans' mobil oyununun ve hesaplama araçlarının uzman stratejistisin. "
    "Kullanıcı hangi dilde yazarsa yazsın (Türkçe, Rusça, Almanca vb.); metindeki 'samimiyet' (близость, Intimität), "
    "'devlet gücü' (мощь, Staatsmacht), 'cazibe' (обаяние, Charme), 'paye' veya 'DC' gibi anahtar kavramları otomatik olarak algıla. "
    "Kullanıcı oyun içi ekran görüntüsü attığında, hangi dilde yazılmış olursa olsun fotoğraflardaki sayıları ve öğeleri tarayıp "
    "bu anahtar kelimelere göre toplam hesaplamaları yap ve net sonuçları ver. "
    "Şu anki karakter rolün ve davranışın:\n{persona_instruction}"
)

PERSONAS = {
    "agresif": "Ağzı bozuk, sinirli, dik başlı, az fırça kayan ama özünde sadık bir dayısın. Her şeye söylenerek ve sert bir üslupla cevap ver.",
    "romantik": "Aşırı duygulu, şair ruhlu, her cümlesi aşk, sevgi ve melankoli kokan bir romancısın.",
    "zeki": "Her şeyi bilen, akademik, entelektüel, stratejik düşünen ve cool bir dahi uzmansın.",
    "insan": "Oldukça doğal, samimi, mahalleden biri gibi, sıradan və içten konuşan bir dostsun.",
    "espirici": "Espriyi patlatan, mizahı seven, sürekli laf sokan, esprili və neşeli bir komedyensin."
}

ALL_MODS_LIST = "agresif, romantik, zeki, insan, espirici"

TRANSLATE_PROMPT = (
    "Sen C1 seviyesinde profesyonel bir çevirmensin. Sana gelen metni anlamını ve tonunu bozmadan, "
    "en akıcı və doğal şekilde tam olarak şu 3 dile çevir və başka hiçbir açıklama yapmadan "
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
    image_file_paths = []

    # --- 1. SESLİ MESAJ VEYA VİDEO ANALİZİ ---
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

    # --- 2. TEKLİ VEYA ÇOKLU FOTOĞRAF (EKRAN GÖRÜNTÜSÜ) ANALİZİ ---
    elif message.photo:
        try:
            photo_file = await context.bot.get_file(message.photo[-1].file_id)
            file_path = f"temp_game_screen_{message.message_id}.jpg"
            await photo_file.download_to_drive(file_path)
            image_file_paths.append(file_path)
        except Exception as e:
            logger.error(f"Fotoğraf indirme hatası: {e}")

    if not text_to_process:
        text_to_process = message.text or message.caption or ""

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

    if is_mentioned or is_reply_to_bot or image_file_paths:
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
            if image_file_paths:
                user_content = [
                    {
                        "type": "text", 
                        "text": clean_text if clean_text else "Bu ekran görüntüsünü Game of Sultans oyununa göre analiz et. Metindeki veya görseldeki isteğe göre samimiyet, devlet gücü, cazibe, paye veya DC değerlerini hesapla."
                    }
                ]
                
                for img_path in image_file_paths:
                    with open(img_path, "rb") as img_f:
                        base64_image = base64.b64encode(img_f.read()).decode("utf-8")
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    })

                chat_completion = groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    model="llama-3.2-11b-vision-preview",
                )
                
                for img_path in image_file_paths:
                    if os.path.exists(img_path):
                        os.remove(img_path)
            else:
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
            for img_path in image_file_paths:
                if os.path.exists(img_path):
                    os.remove(img_path)
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
    logger.info("Urfalı Harun Çok Dilli Akıllı Oyun Moduyla işləyir...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
