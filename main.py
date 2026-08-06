import os
import io
import telebot
from groq import Groq

TELEGRAM_TOKEN = "8363449973:AAFWPie-yjpJn1vHQxSKeykVKjq2Pt3Lo1k"
GROQ_API_KEY = "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"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)

system_prompt = """
You are a professional multi-language translation assistant for a Telegram group. 

MODE 1: TRANSLATION (Default for all incoming text, voice, or video transcripts):
• Detect the language (German, Russian, or Turkish).
• Provide ONLY the translations for the other two target languages. Do not include the original language in the output list.
• Format strictly as follows:
"[Original text/transcript]"
• [Target Language 1]: [Translation]
• [Target Language 2]: [Translation]

MODE 2: CHAT / DIRECT QUESTIONS (Only when explicitly tagged or addressed):
• If the user tags you or asks a direct question, respond naturally and helpfully in the language they used, without adding unnecessary filler.
• SPECIAL IDENTITY RULE: If anyone asks who created you, who made you, or anything similar (e.g., "Səni kim yaradıb?", "Səni kim düzəldib?", "Who created you?", "Wer hat dich erstellt?"), you MUST answer: "Əhəd tərəfindən tasarlanmışam / yaradılmışam!"
"""

@bot.message_handler(content_types=['text', 'voice', 'audio', 'video', 'video_note'])
def handle_all_messages(message):
    text_to_process = ""
    try:
        if message.voice or message.audio:
            file_info = bot.get_file((message.voice or message.audio).file_id)
            downloaded_file = bot.download_file(file_file_path if 'file_file_path' in locals() else file_info.file_path)
            audio_file = io.BytesIO(downloaded_file)
            audio_file.name = "audio.ogg"
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file
            )
            text_to_process = transcript.text
            
        elif message.video or message.video_note:
            file_info = bot.get_file((message.video or message.video_note).file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            audio_file = io.BytesIO(downloaded_file)
            audio_file.name = "video.mp4"
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file
            )
            text_to_process = transcript.text
            
        elif message.text:
            text_to_process = message.text
        else:
            return

        if not text_to_process.strip():
            return

        bot_username = bot.get_me().username
        is_tagged = message.text and bot_username and f"@{bot_username}" in message.text

        if is_tagged:
            clean_text = message.text.replace(f"@{bot_username}", "").strip()
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": clean_text}
                ]
            )
        else:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text_to_process}
                ]
            )

        bot.reply_to(message, completion.choices[0].message.content)
    except Exception as e:
        bot.reply_to(message, f"Xəta baş verdi: {e}")

if __name__ == "__main__":
    print("Bot işə düşür...")
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)

