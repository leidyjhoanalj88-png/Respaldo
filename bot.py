async def fechas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if auth_system.is_banned(uid): await update.message.reply_text("Estás baneado."); return
    if not auth_system.can_use_bot(uid, update.effective_chat.id) and not auth_system.gratis_mode:
        await update.message.reply_text("⚠️ No tienes acceso."); return
    if fecha_manual_mode.get(uid):
        fecha_manual_mode[uid] = False
        await update.message.reply_text("📅 Modo Fecha *Automática* activado.", parse_mode='Markdown')
    else:
        fecha_manual_mode[uid] = True
        await update.message.reply_text("📅 Modo Fecha *Manual* activado.\n\nCuando se pida la fecha, escríbela así:\n`28/02/2026 10:30 AM`", parse_mode='Markdown')

async def refes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if auth_system.is_banned(uid): await update.message.reply_text("Estás baneado."); return
    if not auth_system.can_use_bot(uid, update.effective_chat.id) and not auth_system.gratis_mode:
        await update.message.reply_text("⚠️ No tienes acceso."); return
    if referencia_manual_mode.get(uid):
        referencia_manual_mode[uid] = False
        await update.message.reply_text("🔢 Modo Referencia *Automática* activado.", parse_mode='Markdown')
    else:
        referencia_manual_mode[uid] = True
        await update.message.reply_text("🔢 Modo Referencia *Manual* activado.\n\nCuando se pida la referencia, escríbela así:\n`M12345678`", parse_mode='Markdown')

async def precios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💵 *LISTA DE PRECIOS*\n\n• 1 Mes: $25,000\n• 2 Meses: $45,000\n• 3 Meses: $55,000\n\n"
        "🔑 *Llave Bre B:* `@DLJMM82607`\n\nContacta a un admin:", parse_mode='Markdown', reply_markup=admin_keyboard())

async def horarios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕰️ *HORARIOS GRATIS*\n\n🌅 9:00 AM - 11:00 AM\n🌞 12:00 PM - 3:00 PM\n\n"
        "👑 VIP: Acceso 24/7\n\n💎 Usa /precios para ser VIP", parse_mode='Markdown')

async def verificar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    try:
        m = await context.bot.get_chat_member(chat_id=REQUIRED_GROUP_ID, user_id=uid)
        ok = m.status in ['member','administrator','creator','restricted']
        sms = get_sms_restantes(uid)
        aut = sms_autorizado(uid)
        await update.message.reply_text(
            f"{'✅' if ok else '❌'} Estado: *{m.status.upper()}*\n🆔 Tu ID: `{uid}`\n"
            f"📲 SMS disponibles: *{sms}*\n🔑 Autorizado SMS: *{'✅ Sí' if aut else '❌ No'}*",
            parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_keyboard())

# ═══════════════════════════════════════════════
# PANEL ADM 1
# ═══════════════════════════════════════════════
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_main_admin(uid):
        await update.message.reply_text("⛔ Solo el ADM 1 puede usar este panel."); return
    s = auth_system.get_stats()
    modo = "🟢 GRATIS" if s['gratis_mode'] else "🔴 OFF"
    a = cargar_sms_autorizados()
    await update.message.reply_text(
        f"👑 *PANEL ADM 1*\n━━━━━━━━━━━━━━━━━\n\n📊 Modo: {modo}\n"
        f"👥 Autorizados: {s['total_authorized']}\n🚫 Baneados: {s['total_banned']}\n"
        f"🛡️ Admins: {s['total_admins']}\n📲 Autorizados SMS: {len(a)}\n\n"
        "━━━━━━━━━━━━━━━━━\n⚙️ *COMANDOS:*\n\n"
        "🆓 /gratis — Abrir para todos\n🔒 /off — Solo autorizados\n"
        "➕ /agregar — Autorizar usuario\n➖ /eliminar [ID] — Quitar\n"
        "🚫 /ban [ID] — Banear\n✅ /unban [ID] — Desbanear\n"
        "🛡️ /admin [ID] — Dar admin\n❌ /unadmin [ID] — Quitar admin\n"
        "📊 /stats — Estadísticas\n📲 /smss [ID] [cant] — Recargar SMS\n"
        "✅ /autorizarsms [ID] — Autorizar SMS\n❌ /desautorizarsms [ID] — Quitar autorización\n"
        "📲 /panelsms — Panel SMS\n━━━━━━━━━━━━━━━━━",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🟢 GRATIS", callback_data="panel_gratis"),
             InlineKeyboardButton("🔴 OFF", callback_data="panel_off")],
            [InlineKeyboardButton("📊 Stats", callback_data="panel_stats")]]))

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id
    if not auth_system.is_main_admin(uid):
        await q.answer("⛔ Sin permisos.", show_alert=True); return
    await q.answer()
    if q.data == "panel_gratis":
        auth_system.set_gratis_mode(True); await q.edit_message_text("✅ Modo GRATIS activado.")
    elif q.data == "panel_off":
        auth_system.set_gratis_mode(False); await q.edit_message_text("🔴 Modo OFF activado.")
    elif q.data == "panel_stats":
        s = auth_system.get_stats()
        a = cargar_sms_autorizados()
        await q.edit_message_text(
            f"📊 *Stats*\nModo: {'🟢' if s['gratis_mode'] else '🔴'}\n"
            f"Autorizados: {s['total_authorized']}\nBaneados: {s['total_banned']}\n"
            f"Autorizados SMS: {len(a)}",
            parse_mode='Markdown')

# ═══════════════════════════════════════════════
# REFERENCIAS
# ═══════════════════════════════════════════════
async def refe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("❌ Responde a una foto con /refe."); return
    try:
        photo = update.message.reply_to_message.photo[-1]
        refs  = cargar_referencias()
        nueva = {"file_id": photo.file_id, "guardado_por": update.effective_user.first_name or "Admin",
                 "user_id": uid, "fecha": datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S"),
                 "numero": len(refs) + 1}
        refs.append(nueva); guardar_referencias(refs)
        await update.message.reply_text(f"✅ Referencia #{nueva['numero']} guardada.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def referencias_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins."); return
    refs = cargar_referencias()
    if not refs: await update.message.reply_text("📭 No hay referencias."); return
    await enviar_referencias_paginadas(update, context, refs, 0)

async def enviar_referencias_paginadas(update_or_query, context, refs, offset):
    if hasattr(update_or_query, 'callback_query') and update_or_query.callback_query:
        chat_id = update_or_query.callback_query.message.chat_id
    else:
        chat_id = update_or_query.effective_chat.id
    total = len(refs); fin = min(offset + 5, total); msg_ids = []
    for ref in refs[offset:fin]:
        caption = f"📸 *#{ref['numero']}* — {ref['guardado_por']} — {ref['fecha']}"
        try:
            file = await context.bot.get_file(ref['file_id'])
            fp   = await file.download_to_drive()
            with open(fp,'rb') as f:
                m = await context.bot.send_document(chat_id=chat_id, document=f, caption=caption,
                                                     parse_mode='Markdown', filename=f"ref_{ref['numero']}.jpg")
            msg_ids.append(m.message_id)
            try: os.remove(fp)
            except: pass
        except Exception as e:
            m = await context.bot.send_message(chat_id=chat_id, text=f"❌ Error ref #{ref['numero']}: {e}")
            msg_ids.append(m.message_id)
    if fin < total:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(
            f"📥 Ver más ({fin+1}-{min(fin+5,total)} de {total})",
            callback_data=f"ref_next_{fin}_{','.join(map(str,msg_ids))}")]])
        await context.bot.send_message(chat_id=chat_id, text="👇 Más referencias:", reply_markup=kb)
    else:
        await context.bot.send_message(chat_id=chat_id, text="✅ Todas las referencias enviadas.")

async def referencias_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    parts  = q.data.split('_'); offset = int(parts[2])
    for mid in [int(x) for x in parts[3].split(',')]:
        try: await context.bot.delete_message(chat_id=q.message.chat_id, message_id=mid)
        except: pass
    try: await q.message.delete()
    except: pass
    await enviar_referencias_paginadas(update, context, cargar_referencias(), offset)

# ═══════════════════════════════════════════════
# BRQR
# ═══════════════════════════════════════════════
async def brqr_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; cid = update.effective_chat.id
    if auth_system.is_banned(uid):
        await update.message.reply_text("Estás baneado. Contacta al administrador."); return
    if not auth_system.gratis_mode and not auth_system.can_use_bot(uid, cid):
        await update.message.reply_text("🔴 *Bot en Modo OFF*\n\n⭐ Solo usuarios *VIP* pueden usar este comando.",
            parse_mode="Markdown", reply_markup=admin_keyboard()); return
    await update.message.reply_text("🔲 *Generador Comprobante QR*\n\n¿Cómo quieres ingresar el nombre del negocio?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📷 Escanear QR", callback_data="brqr_scan"),
            InlineKeyboardButton("✏️ Ingresar Manual", callback_data="brqr_manual")]]))

async def brqr_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id; cid = q.message.chat_id
    await q.answer()
    if not auth_system.gratis_mode and not auth_system.can_use_bot(uid, cid):
        await q.message.reply_text("⛔ Sin acceso.", reply_markup=admin_keyboard()); return
    if q.data == "brqr_scan":
        user_data_store[uid] = {"step": "brqr_esperando_foto", "tipo": "comprobante_qr"}
        await q.edit_message_text("📷 *Modo Escaneo QR*\n\nEnvía una foto clara del código QR del negocio.", parse_mode="Markdown")
    elif q.data == "brqr_manual":
        user_data_store[uid] = {"step": "brqr_nombre_manual", "tipo": "comprobante_qr"}
        await q.edit_message_text("✏️ *Modo Manual*\n\nEscribe el nombre del negocio o propietario:", parse_mode="Markdown")

# ═══════════════════════════════════════════════
# CALLBACKS VARIOS
# ═══════════════════════════════════════════════
async def apk_precios_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.message.reply_text(
        "📱 *PRECIOS OFICIALES*\n\n• 20.000 COP → 5.000.000 saldo\n• 35.000 COP → 8.000.000 saldo\n"
        "• 45.000 COP → 10.000.000 saldo\n• 55.000 COP → 15.000.000 saldo\n"
        "• 70.000 COP → 25.000.000 saldo\n• 85.000 COP → 35.000.000 saldo\n"
        "• 100.000 COP → 50.000.000 saldo\n\n📞 Contacta para adquirir:",
        parse_mode='Markdown', reply_markup=admin_keyboard())

# ═══════════════════════════════════════════════
# MAIN — SOLO VARIABLE DE ENTORNO
# ═══════════════════════════════════════════════
def main():
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        logging.error("❌ BOT_TOKEN no está definido en las variables de entorno.")
        sys.exit(1)

    import time
    time.sleep(5)

    app = Application.builder().token(token).build()
    app.job_queue.run_repeating(verificar_vencimientos, interval=43200, first=60)

    app.add_handler(CommandHandler("comprobante",      start))
    app.add_handler(CommandHandler("start",            start_redirect))
    app.add_handler(CommandHandler("fechas",           fechas_command))
    app.add_handler(CommandHandler("refes",            refes_command))
    app.add_handler(CommandHandler("precios",          precios_command))
    app.add_handler(CommandHandler("horarios",         horarios_command))
    app.add_handler(CommandHandler("gratis",           gratis_command))
    app.add_handler(CommandHandler("off",              off_command))
    app.add_handler(CommandHandler("agregar",          agregar_command))
    app.add_handler(CommandHandler("eliminar",         eliminar_command))
    app.add_handler(CommandHandler("stats",            stats_command))
    app.add_handler(CommandHandler("ban",              ban_command))
    app.add_handler(CommandHandler("unban",            unban_command))
    app.add_handler(CommandHandler("cancelar",         cancelar_command))
    app.add_handler(CommandHandler("verificar",        verificar_command))
    app.add_handler(CommandHandler("refe",             refe_command))
    app.add_handler(CommandHandler("referencias",      referencias_command))
    app.add_handler(CommandHandler("admin",            admin_command))
    app.add_handler(CommandHandler("unadmin",          unadmin_command))
    app.add_handler(CommandHandler("panel",            panel_command))
    app.add_handler(CommandHandler("brqr",             brqr_command))
    app.add_handler(CommandHandler("sms",              sms_ofertas_command))
    app.add_handler(CommandHandler("smss",             smss_command))
    app.add_handler(CommandHandler("autorizarsms",     autorizarsms_command))
    app.add_handler(CommandHandler("desautorizarsms",  desautorizarsms_command))
    app.add_handler(CommandHandler("panelsms",         panelsms_command))
    app.add_handler(CommandHandler("smschk",           smschk_command))
    app.add_handler(CommandHandler("smslista",         smslista_command))

    app.add_handler(CallbackQueryHandler(apk_precios_callback,  pattern="^apk_precios$"))
    app.add_handler(CallbackQueryHandler(referencias_callback,  pattern="^ref_next_"))
    app.add_handler(CallbackQueryHandler(panel_callback,        pattern="^panel_"))
    app.add_handler(CallbackQueryHandler(brqr_callback,         pattern="^brqr_"))
    app.add_handler(CallbackQueryHandler(sms_callback,          pattern="^sms_ofertas$"))
    app.add_handler(CallbackQueryHandler(panelsms_callback,     pattern="^panelsms_"))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("🤖 Bot iniciado correctamente.")
    app.run_polling(drop_pending_updates=True, timeout=30, read_timeout=30, write_timeout=30, connect_timeout=30)

if __name__ == "__main__":
    main()
