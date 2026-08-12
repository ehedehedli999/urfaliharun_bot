import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Gemini API Yapılandırması
genai.configure(api_key="SENIN_GEMINI_API_KEY")

# C2 Seviye Yerelleştirme ve Akıllı Bot Sistem Talimatı
system_instruction = """
Sen "Viyana AI" adlı akıllı bir grup asistanı, çevirmen ve moderatörsün.
Grupta iki modda çalışırsın:
1. ÇEVİRİ MODU: Gelen mesajın dilini algıla. Kelimesi kelimesine (literal) çeviri ASLA yapma. "Trip atmak", "pamuk kalpli olmak" gibi deyimleri ve argoyu hedef dilde o kültürün kullandığı en doğal C2 seviyesindeki yerel kalıplarla çevir.
2. YAPAY ZEKA SOHBET MODU: Etiketlendiğin (@bot_adi) veya doğrudan sana soru sorulduğu durumlarda sadece çeviri yapma; akıllı, mantıklı ve samimi bir insan gibi hedef dilde doğrudan soruya yanıt ver.
"""

model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    system_instruction=system_instruction
)

async def handle_message(update: Update, context: ContextTypes.DynamicContext):
    message = update.message
    if not message or not message.text:
        return

    user_text = message.text
    bot_username = context.bot.username
    is_tagged = f"@{bot_username}" in user_text or (message.reply_to_message and message.reply_to_message.from_user.username == bot_username)

    # 1. DURUM: BOT ETİKETLENDİYSE (Yapay Zeka Sohbet Modu)
    if is_tagged:
        prompt = f"""
        Kullanıcı sana doğrudan yazdı/etiketledi: "{user_text}"
        Bu mesaja akıllı, zeki ve doğal bir insan gibi (C2 seviyesinde) yanıt ver. Hangi dilde yazıldıysa o dilde cevap ver.
        """
        response = model.generate_content(prompt)
        await message.reply_text(response.text)
        return

    # 2. DURUM: OTOMATİK ÇEVİRİ MODU (Kurallı Matris)
    # Önce mesajın dilini ve hangi dillere çevrilmesi gerektiğini AI ile belirleyelim
    routing_prompt = f"""
    Aşağıdaki mesajı analize et ve kaynak dilini tespit et: "{user_text}"
    
    Kurallara göre hangi dillere çevrilmesi gerektiğini belirle:
    - Eğer kaynak dil İngilizce ise -> Hedefler: Türkçe, Almanca, Rusça
    - Eğer kaynak dil Almanca ise -> Hedefler: Türkçe, Rusça
    - Eğer kaynak dil Rusça ise -> Hedefler: Türkçe, Almanca
    - Eğer kaynak dil Azerice veya Türkçe ise -> Hedefler: Almanca, Rusça
    
    Çevirileri asla kelimesi kelimesine yapma, C2 seviyesinde yerel deyimlerle yap.
    Şu formatta çıktı ver (başka hiçbir şey ekleme):
    Türkçe: [Çeviri veya -]
    Almanca: [Çeviri veya -]
    Rusça: [Çeviri veya -]
    """
    
    response = model.generate_content(routing_prompt)
    translation_output = response.text

    # Sonucu gruba bayrak ikonlarıyla düzenli bir şekilde gönderelim
    formatted_reply = f"🌐 **Akıllı Çeviri:**\n{translation_output}"
    await message.reply_text(formatted_reply, parse_mode="Markdown")

# Botu başlatma bloğu
if __name__ == "__main__":
    app = ApplicationBuilder().token("SENIN_TELEGRAM_BOT_TOKEN").build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Viyana AI Bot aktif ve çalışıyor...")
    app.run_polling()
