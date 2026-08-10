# --- AKILLI VE TEK TİP ÇEVİRİ FİLTRESİ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text: return
    text = message.text.strip()
    chat_id = message.chat_id
    user = update.effective_user

    if user.is_bot or text.startswith("/"):
        return

    add_point(chat_id, user)
    bot_username = context.bot.username or ""

    if bot_username and f"@{bot_username}".lower() in text.lower():
        clean_text = text.replace(f"@{bot_username}", "").strip()
        if not clean_text: return
        await message.chat.send_action(action="typing")
        try:
            ans = await query_grok(clean_text, SMART_PROMPT)
            await message.reply_text(ans)
        except Exception:
            await message.reply_text("⚠️ Bir hata oluştu.")
        return

    words = text.split()
    if len(words) < 2 or len(text) < 5 or "http" in text:
        return

    # KOD SEVİYESİNDE DİL TESPİTİ
    try:
        lang = detect(text)
    except Exception:
        lang = "tr"

    # KATILAŞTIRILMIŞ FORMAT PROMPTLARI (Parantezsiz ve Gerçek Alfabeyle)
    if lang == "tr":
        target_prompt = """
        Metin TÜRKÇE yazılmıştır.
        Bu cümleyi SADECE Rusça ve Almanca'ya çevir.
        
        KURALLAR:
        - Rusça çeviriyi KESİNLİKLE gerçek Kiril alfabesiyle yaz (Latin harfi veya okunuş yazma!).
        - Asla [...] veya (...) gibi parantezler kullanma!
        - Türkçe çeviri yapma!
        
        Format tam olarak böyle olmalıdır:
        Rusça: Çeviri
        Almanca: Çeviri
        """
    elif lang == "ru":
        target_prompt = """
        Metin RUSÇA yazılmıştır.
        Bu cümleyi SADECE Türkçe ve Almanca'ya çevir.
        
        KURALLAR:
        - Asla [...] veya (...) gibi parantezler kullanma!
        - Rusça çeviri yapma!
        
        Format tam olarak böyle olmalıdır:
        Türkçe: Çeviri
        Almanca: Çeviri
        """
    elif lang == "de":
        target_prompt = """
        Metin ALMANCA yazılmıştır.
        Bu cümleyi SADECE Türkçe ve Rusça'ya çevir.
        
        KURALLAR:
        - Rusça çeviriyi KESİNLİKLE gerçek Kiril alfabesiyle yaz!
        - Asla [...] veya (...) gibi parantezler kullanma!
        - Almanca çeviri yapma!
        
        Format tam olarak böyle olmalıdır:
        Türkçe: Çeviri
        Rusça: Çeviri
        """
    else:
        target_prompt = """
        Bu cümleyi SADECE Türkçe ve Almanca'ya çevir. Parantez kullanma.
        
        Türkçe: Çeviri
        Almanca: Çeviri
        """

    try:
        translated = await query_grok(text, target_prompt)
        if len(translated) < 4: return
        await message.reply_text(translated)
    except Exception as e:
        logger.error(f"Auto translation error: {e}")
