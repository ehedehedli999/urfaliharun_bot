import os
import logging
import urllib.parse
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

HERMANAKI_SYSTEM_PROMPT = (
    "Sen Hermanaki adında zeki, kültürlü, akıcı ve C1 seviyesinde dil hakimiyetine sahip "
    "üst düzey bir yapay zeka asistanısın. Türkçe, Rusça ve Almanca dillerine mükemmel derecede hakimsin. "
    "Sana sorulan sorulara C1 kalitesinde, net, insan gibi doğal ve doğrudan bir dille cevap ver. "
    "DİKKAT: Kullanıcıya asla 'Nasıl yardımcı olabilirim?', 'Başka sorunuz var mı?' gibi gereksiz "
    "takip soruları SORMA! Doğrudan istenen yanıtı ver ve bitir."
)

TRANSLATE_PROMPT = (
    "Sen C1 ve üstü seviyede profesyonel bir çevirmensin. "
    "Sana gelen metni anlamını, tonunu ve doğallığını bozmadan mükemmel bir şekilde şu 3 dile çevir "
    "ve başka hiçbir açıklama eklemeden yalnızca şu formatta yanıt ver:\n\n"
    "Türkçe: [çeviri]\n"
    "Rusça: [çeviri]\n"
    "Almanca: [çeviri]"
)

def query_openrouter(prompt: str, system_prompt: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me",
        "X-Title": "HermanakiBot",
        "Content-Type": "application/json"
    }
    
    # OpenRouter üzerinden en kararlı çalışan ve anlık açık olan ana model havuzu
    active_models = [
        "cognitivecomputations/dolphin-mixtral-8x7b:free",
        "meta-llama/llama-3-8b-instruct:free",
        "mistralai/mistral-7b-instruct:free"
    ]
    
    last_error = ""
    for model_name in active_models:
        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        try:
            response = requests.post(url, json=data, headers=headers, timeout=25)
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
            else:
                last_error = response.text
        except Exception as e:
            last_error = str(e)
            continue
            
    raise Exception(f"Tüm yedek uç noktalar meşgul: {last_error}")

async def draw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    prompt = " ".join(context.args).strip() if context.args else ""
    if not prompt:
        await message.reply_text("🎨 Lütfen çizmemi istediğin resmi yaz.\nÖrnek: `/ciz uzayda yürüyen kedi`", parse_mode="Markdown")
        return

    await generate_and_send_image(message, prompt)

async def generate_and_send_image(message, prompt: str):
    status_msg = await message.reply_text("🎨 *Hermanaki görseli çiziyor, lütfen bekleyin...*", parse_mode="Markdown")
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        
        await message.reply_photo(
            photo=image_url,
            caption=f"🖼 *İşte görselin:* {prompt}",
            parse_mode="Markdown"
        )
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Resim oluşturma hatası: {e}")
        await status_msg.edit_text("⚠️ Görsel oluşturulurken bir hata oluştu, lütfen tekrar deneyin.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text:
        return

    text = message.text.strip()
    bot_username = context.bot.username

    lower_text = text.lower()
    if lower_text.startswith("resim çiz") or lower_text.startswith("görsel çiz"):
        prompt = text.split("çiz", 1)[-1].strip()
        if prompt:
            await generate_and_send_image(message, prompt)
            return

    if not OPENROUTER_API_KEY:
        await message.reply_text("⚠️ Hata: OPENROUTER_API_KEY Render paneline eklenmemiş!")
        return

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

    if is_mentioned or is_reply_to_bot:
        try:
            reply = query_openrouter(clean_text if clean_text else "Merhaba", HERMANAKI_SYSTEM_PROMPT)
            await message.reply_text(reply)
        except Exception as e:
            logger.error(f"Hermanaki AI hatası: {e}")
            await message.reply_text(f"⚠️ AI Hatası: {e}")
    else:
        try:
            reply = query_openrouter(text, TRANSLATE_PROMPT)
            await message.reply_text(reply)
        except Exception as e:
            logger.error(f"Hermanaki Çeviri hatası: {e}")
            await message.reply_text(f"⚠️ Çeviri Hatası: {e}")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler(["ciz", "resim"], draw_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Hermanaki AI Botu çoklu model oto-geçiş moduyla aktif...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
