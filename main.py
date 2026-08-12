import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from openai import OpenAI

# --- API VE TOKEN AYARLARI ---
API_KEY = "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"
TELEGRAM_BOT_TOKEN = "8363449973:AAElwMlaNrlKJ7sh8PApYPxWb13YqrHJakU"

# OpenRouter / OpenAI SDK Bağlantısı
client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

MODEL_NAME = "openai/gpt-5.5"

# --- C2 SEVİYE SİSTEM TALİMATI ---
SYSTEM_INSTRUCTION = """
Sen profesyonel bir C2 seviye dilbilimci, yerelleştirme uzmanı ve "Viyana AI" adlı akıllı bir grup asistanısın.

KESİNLİKLE UYMAN GEREKEN KURALLAR:
1. Kelimesi kelimesine (literal) veya makineleşmiş, saçma çeviriler yapmak KESİNLİKLE YASAKTIR.
2. "Trip atmak", "kendine gelmek", "pamuk kalpli olmak" gibi deyimleri, argoları ve günlük konuşma kalıplarını asla kelime kelime çevirme. Hedef dilde o kültürün sokağında, sosyal medyasında kullanılan birebir en doğal C2 seviyesindeki deyimsel karşılığını kullan.
3. ÇALIŞMA MODLARIN:
   - SOHBET MODU (Etiketlendiğinde / Yanıt verildiğinde): Çeviri yapma. Kullanıcıya zeki, akıllı, samimi ve doğal bir insan gibi o dilde doğrudan yanıt ver.
   - ÇEVİRİ MODU (Etiketlenmediğinde): Gelen mesajın dilini tespit et ve kurallı hedef dillere kusursuz bir şekilde çevir.
"""

# --- KOMUT FONKSİYONLARI ---
async def cmd_help(update: Update, context: ContextTypes.DynamicContext):
    await update.message.reply_text("🛠 Yardım Menüsü:\nBot gruptaki mesajları otomatik çevirir.\nBota bir şey sormak için @etiketleyin veya mesajını yanıtlayın.")

async def cmd_kral(update: Update, context: ContextTypes.DynamicContext):
    await update.message.reply_text("👑 Boss burada! Gruba hoş geldin.")

async def cmd_sirallama(update: Update, context: ContextTypes.DynamicContext):
    await update.message.reply_text("🏆 Puan Sıralaması: Sistem şu an güncelleniyor.")

async def cmd_dil(update: Update, context: ContextTypes.DynamicContext):
    await update.message.reply_text("✅ Dil tercihi algılandı. Otomatik çeviri C2 seviyesinde aktif.")


async def handle_message(update: Update, context: ContextTypes.DynamicContext):
    message = update.message
    if not message or not message.text:
        return

    user_text = message.text
    bot_username = context.bot.username
    
    # Etiket veya Yanıt kontrolü
    is_tagged = False
    if bot_username and f"@{bot_username.lower()}" in user_text.lower():
        is_tagged = True
    if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.username:
        if bot_username and message.reply_to_message.from_user.username.lower() == bot_username.lower():
            is_tagged = True

    # --- MOD 1: SOHBET MODU (Etiketlendiğinde) ---
    if is_tagged:
        clean_text = user_text
        if bot_username:
            clean_text = clean_text.replace(f"@{bot_username}", "").replace(f"@{bot_username.lower()}", "").strip()
        
        chat_prompt = f"Kullanıcı sana doğrudan seslendi: '{clean_text}'. Çeviri yapmadan, C2 yerlisi gibi akıllı, doğal ve samimi bir insan yanıtı ver."
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": chat_prompt}
            ]
        )
        await message.reply_text(response.choices[0].message.content)
        return

    # --- MOD 2: OTOMATİK ÇEVİRİ MODU (Etiket yoksa) ---
    translation_prompt = (
        f"Aşağıdaki mesajı analiz et ve kaynak dilini tespit et: \"{user_text}\"\n\n"
        "Şu çeviri matrisi kurallarına harfiyen uy:\n"
        "- İngilizce -> Türkçe, Almanca, Rusça\n"
        "- Almanca -> Türkçe, Rusça\n"
        "- Rusça -> Türkçe, Almanca\n"
        "- Azerice veya Türkçe -> Almanca, Rusça\n\n"
        "Çeviriler kelimesi kelimesine olmasın, C2 seviyesinde yerel deyimlerle yapılsın.\n"
        "Çıktıyı sadece şu formatta ver:\n"
        "🇹🇷 [Türkçe çevirisi varsa yaz, yoksa atla]\n"
        "🇩🇪 [Almanca çevirisi varsa yaz, yoksa atla]\n"
        "🇷🇺 [Rusça çevirisi varsa yaz, yoksa atla]"
    )
    
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": translation_prompt}
        ]
    )
    
    output_text = response.choices[0].message.content
    if output_text and len(output_text.strip()) > 0:
        await message.reply_text(output_text.strip())

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Komut İşleyicileri
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("kral", cmd_kral))
    app.add_handler(CommandHandler("sirallama", cmd_sirallama))
    app.add_handler(CommandHandler(["turkce", "rusca", "almanca"], cmd_dil))
    
    # Mesaj İşleyici
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Viyana AI Bot aktif: Komutlar ve GPT-5.5 C2 Çeviri/Sohbet entegrasyonu tamamlandı.")
    app.run_polling()
