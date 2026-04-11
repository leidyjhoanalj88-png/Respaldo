import zipfile
import os

# Auto-unzip de assets al arrancar
for zip_name, extract_to in [("img.zip", "."), ("fuentes.zip", ".")]:
    if os.path.exists(zip_name):
        print(f"[STARTUP] Descomprimiendo {zip_name}...")
        with zipfile.ZipFile(zip_name, 'r') as z:
            z.extractall(extract_to)
        print(f"[STARTUP] {zip_name} descomprimido OK")
    else:
        print(f"[STARTUP] {zip_name} no encontrado, omitiendo")

from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from config import (
    COMPROBANTE1_CONFIG,
    COMPROBANTE4_CONFIG,
    COMPROBANTE_MOVIMIENTO_CONFIG,
    COMPROBANTE_MOVIMIENTO2_CONFIG,
    COMPROBANTE_QR_CONFIG,
    COMPROBANTE_NUEVO_CONFIG,
    COMPROBANTE_ANULADO_CONFIG,
    COMPROBANTE_MOVIMIENTO3_CONFIG,
    MVKEY_CONFIG,
    COMPROBANTE_AHORROS_CONFIG,
    COMPROBANTE_AHORROS2_CONFIG,
    COMPROBANTE_DAVIPLATA_CONFIG,
    COMPROBANTE_BC_NQ_T_CONFIG,
    COMPROBANTE_BC_QR_CONFIG,
    COMPROBANTE_NEQUI_BC_CONFIG,
    COMPROBANTE_NEQUI_AHORROS_CONFIG,
    MOVIMIENTO_BC_AHORROS_CONFIG,
    MOVIMIENTO_BC_CORRIENTE_CONFIG,
    MOVIMIENTO_BC_NEQUI_CONFIG,
    MOVIMIENTO_BC_QR_CONFIG
)
from utils import generar_comprobante, generar_comprobante_nuevo, generar_comprobante_anulado, enmascarar_nombre, generar_comprobante_ahorros, generar_comprobante_daviplata, generar_comprobante_bc_nq_t, generar_comprobante_bc_qr, generar_comprobante_nequi_bc, generar_comprobante_nequi_ahorros, generar_movimiento_bancolombia
from auth_system import AuthSystem
import logging
from datetime import datetime
import pytz
import json

logging.basicConfig(level=logging.DEBUG)

ADMIN_ID = 8114050673
ALLOWED_GROUP = -1003832824723
ADMINS_USERNAMES = ["@Libertadyplata777"]
auth_system = AuthSystem(ADMIN_ID, ALLOWED_GROUP)
user_data_store = {}
fecha_manual_mode = {}
referencia_manual_mode = {}
REFERENCIAS_FILE = "referencias.json"
REQUIRED_GROUP_ID = -1003832824723

def cargar_referencias():
    if os.path.exists(REFERENCIAS_FILE):
        try:
            with open(REFERENCIAS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def guardar_referencias(referencias):
    with open(REFERENCIAS_FILE, 'w', encoding='utf-8') as f:
        json.dump(referencias, f, ensure_ascii=False, indent=2)

async def is_member_of_group(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_GROUP_ID, user_id=user_id)
        print(f"[DEBUG] Usuario {user_id} - Estado en grupo: {member.status}")
        is_member = member.status in ['member', 'administrator', 'creator']
        if not is_member:
            print(f"[ACCESO DENEGADO] Usuario {user_id} - Estado: {member.status}")
        else:
            print(f"[ACCESO PERMITIDO] Usuario {user_id} - Estado: {member.status}")
        return is_member
    except Exception as e:
        print(f"[ERROR CRÍTICO] No se pudo verificar membresía para usuario {user_id}: {e}")
        return False

async def send_success_message(update: Update):
    await update.message.reply_text(
        "✅ **Comprobante generado con éxito**\n\nUsa /comprobante para generar otro",
        parse_mode='Markdown'
    )

async def notify_main_admin(context, admin_id, admin_name, action, target_info=""):
    if admin_id == ADMIN_ID:
        return
    try:
        now = datetime.now()
        fecha_hora = now.strftime("%d/%m/%Y %H:%M:%S")
        message = f"🔔 **Notificación Administrativa**\n\n👤 **Admin:** {admin_id}\n📝 **Nombre:** {admin_name or 'Sin nombre'}\n⚡ **Acción:** {action}\n"
        if target_info:
            message += f"🎯 **Detalles:** {target_info}\n"
        message += f"🕐 **Fecha/Hora:** {fecha_hora}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"[ERROR] No se pudo enviar notificación: {e}")

async def start_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Necesitas acceso a la APK?", callback_data="apk_precios")],
        [InlineKeyboardButton("Admin 1", url="https://t.me/Libertadyplata777")],
        [InlineKeyboardButton("Admin 2", url="https://t.me/Broquicalifoxx")],
        [InlineKeyboardButton("Admin 3", url="https://t.me/The_Offici4l")]
    ]
    await update.message.reply_text(
        "Bienvenido al generador de comprobantes\n\nAdministradores autorizados:\nHaz clic en el boton para contactar\n\nComandos disponibles:\n/comprobante - Iniciar el bot\n/fechas - Activar/desactivar fechas manuales\n/refes - Activar/desactivar referencias manuales\n/horarios - Ver horarios gratis\n/precios - Ver planes premium\n\nUsa /comprobante para empezar",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if auth_system.is_banned(user_id):
        await update.message.reply_text("Estás baneado por ratón ")
        return

    if not await is_member_of_group(context.bot, user_id):
        keyboard = [[InlineKeyboardButton("📲 Unirse al Grupo", url="https://t.me/Nequiibotgv")]]
        await update.message.reply_text(
            "⚠️ **Acceso Denegado**\n\nTienes que unirte a nuestro grupo oficial para poder usar el bot\n\n👇 Haz clic en el botón para unirte:",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if not auth_system.can_use_bot(user_id, chat_id):
        if not auth_system.gratis_mode:
            keyboard = [
                [InlineKeyboardButton("💎 ¿Necesitas acceso a la APK?", callback_data="apk_precios")],
                [InlineKeyboardButton("Admin 1", url="https://t.me/Libertadyplata777")],
                [InlineKeyboardButton("Admin 2", url="https://t.me/Broquicalifoxx")],
                [InlineKeyboardButton("Admin 3", url="https://t.me/The_Offici4l")]
            ]
            await update.message.reply_text(
                "🔴 **Bot en Modo OFF**\n\n🕒 El bot está fuera del horario gratuito\n\n💰 **¿Necesitas usarlo ahora?**\nContacta con algún administrador:\n\n✨ Pueden activarte el acceso premium",
                parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

    keyboard = [
        [KeyboardButton("Nequi"), KeyboardButton("Daviplata")],
        [KeyboardButton("Nequi QR"), KeyboardButton("Bre B"), KeyboardButton("Anulado")],
        [KeyboardButton("Ahorros"), KeyboardButton("Corriente")],
        [KeyboardButton("BC a NQ"), KeyboardButton("BC QR")],
        [KeyboardButton("Nequi Corriente"), KeyboardButton("Nequi Ahorros")]
    ]
    await update.message.reply_text(
        "selecciona el boton de el comprobante que quieres generar",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    button_mapping = {
        "Nequi": "comprobante1", "Transfiya": "comprobante4", "Daviplata": "comprobante_daviplata",
        "Nequi QR": "comprobante_qr", "Bre B": "comprobante_nuevo", "Anulado": "comprobante_anulado",
        "Ahorros": "comprobante_ahorros", "Corriente": "comprobante_corriente",
        "BC a NQ": "comprobante_bc_nq_t", "BC QR": "comprobante_bc_qr",
        "Nequi Corriente": "comprobante_nequi_bc", "Nequi Ahorros": "comprobante_nequi_ahorros"
    }

    # Siempre reiniciar cuando presiona botón
    if text in button_mapping:
        user_data_store.pop(user_id, None)

    if text in button_mapping and user_id not in user_data_store:
        if not auth_system.can_use_bot(user_id, chat_id):
            if not auth_system.gratis_mode:
                keyboard = [
                    [InlineKeyboardButton("💎 ¿Necesitas acceso a la APK?", callback_data="apk_precios")],
                    [InlineKeyboardButton("Admin 1", url="https://t.me/Libertadyplata777")],
                    [InlineKeyboardButton("Admin 2", url="https://t.me/Broquicalifoxx")],
                    [InlineKeyboardButton("Admin 3", url="https://t.me/The_Offici4l")]
                ]
                await update.message.reply_text(
                    "🔴 **Bot en Modo OFF**\n\n🕒 El bot está fuera del horario gratuito\n\n💰 **¿Necesitas usarlo ahora?**\nContacta con algún administrador:\n\n✨ Pueden activarte el acceso premium",
                    parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

        if auth_system.is_banned(user_id):
            await update.message.reply_text("estas baneado de nuestros servicios si crees que es un error contracta con algun administrador")
            return

        if not await is_member_of_group(context.bot, user_id):
            keyboard = [[InlineKeyboardButton("📲 Unirse al Grupo", url="https://t.me/Nequiibotgv")]]
            await update.message.reply_text(
                "⚠️ **Acceso Denegado**\n\nTienes que unirte a nuestro grupo oficial para poder usar el bot\n\n👇 Haz clic en el botón para unirte:",
                parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        tipo = button_mapping[text]
        user_data_store[user_id] = {"step": 0, "tipo": tipo}
        prompts = {
            "comprobante1": "¿Nombre de la víctima? ", "comprobante4": "¿Número a transferir? ",
            "comprobante_qr": "¿Nombre del negocio? ", "comprobante_nuevo": "¿Nombre de la víctima? ",
            "comprobante_anulado": "¿Nombre de la víctima? ", "comprobante_corriente": "¿Nombre de la víctima? ",
            "comprobante_daviplata": "¿Nombre de la víctima? ", "comprobante_ahorros": "¿Nombre de la víctima? ",
            "comprobante_bc_nq_t": "¿Número de teléfono? ", "comprobante_bc_qr": "¿Descripción del QR? ",
            "comprobante_nequi_bc": "¿Nombre? ", "comprobante_nequi_ahorros": "¿Nombre? "
        }
        await update.message.reply_text(prompts.get(tipo, " Inicia ingresando los datos:"))
        return

    if user_id not in user_data_store:
        return

    if auth_system.is_banned(user_id):
        await update.message.reply_text("estas baneado de nuestros servicios")
        return

    data = user_data_store[user_id]
    tipo = data["tipo"]
    step = data["step"]

    # --- NEQUI ---
    if tipo == "comprobante1":
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el número de teléfono ")
        elif step == 1:
            if not text.isdigit() or len(text) != 10 or not text.startswith('3'):
                await update.message.reply_text("El número tiene que empezar en 3 y tener exactamente 10 dígitos \nEjemplo: 3012223855 ")
                return
            data["telefono"] = text
            data["step"] = 2
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 2:
            if not text.replace("-", "", 1).isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(text)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            if user_id in referencia_manual_mode and referencia_manual_mode[user_id]:
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia\n\nEjemplo: M12345678")
                return
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha\n\nEjemplo: 06 de diciembre de 2025 a las 02:30 p. m.")
                return
            try:
                output_path = generar_comprobante(data, COMPROBANTE1_CONFIG)
                with open(output_path, "rb") as f:
                    await update.message.reply_document(document=f, caption=" ")
                os.remove(output_path)
                data_mov = data.copy()
                data_mov["nombre"] = data["nombre"].upper()
                data_mov["valor"] = -abs(data["valor"])
                output_path_mov = generar_comprobante(data_mov, COMPROBANTE_MOVIMIENTO_CONFIG)
                with open(output_path_mov, "rb") as f:
                    await update.message.reply_document(document=f, caption=" ")
                os.remove(output_path_mov)
                await send_success_message(update)
                del user_data_store[user_id]
            except Exception as e:
                logging.error(f"[ERROR Nequi step2] {e}", exc_info=True)
                await update.message.reply_text(f"⚠️ Error generando comprobante: {e}")
                del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            try:
                output_path = generar_comprobante(data, COMPROBANTE1_CONFIG)
                with open(output_path, "rb") as f:
                    await update.message.reply_document(document=f, caption=" ")
                os.remove(output_path)
                data_mov = data.copy()
                data_mov["nombre"] = data["nombre"].upper()
                data_mov["valor"] = -abs(data["valor"])
                output_path_mov = generar_comprobante(data_mov, COMPROBANTE_MOVIMIENTO_CONFIG)
                with open(output_path_mov, "rb") as f:
                    await update.message.reply_document(document=f, caption=" ")
                os.remove(output_path_mov)
                await send_success_message(update)
                del user_data_store[user_id]
            except Exception as e:
                logging.error(f"[ERROR Nequi step3] {e}", exc_info=True)
                await update.message.reply_text(f"⚠️ Error generando comprobante: {e}")
                del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha\n\nEjemplo: 06 de diciembre de 2025 a las 02:30 p. m.")
                return
            try:
                output_path = generar_comprobante(data, COMPROBANTE1_CONFIG)
                with open(output_path, "rb") as f:
                    await update.message.reply_document(document=f, caption=" ")
                os.remove(output_path)
                data_mov = data.copy()
                data_mov["nombre"] = data["nombre"].upper()
                data_mov["valor"] = -abs(data["valor"])
                output_path_mov = generar_comprobante(data_mov, COMPROBANTE_MOVIMIENTO_CONFIG)
                with open(output_path_mov, "rb") as f:
                    await update.message.reply_document(document=f, caption=" ")
                os.remove(output_path_mov)
                await send_success_message(update)
                del user_data_store[user_id]
            except Exception as e:
                logging.error(f"[ERROR Nequi step10] {e}", exc_info=True)
                await update.message.reply_text(f"⚠️ Error generando comprobante: {e}")
                del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            try:
                output_path = generar_comprobante(data, COMPROBANTE1_CONFIG)
                with open(output_path, "rb") as f:
                    await update.message.reply_document(document=f, caption=" ")
                os.remove(output_path)
                data_mov = data.copy()
                data_mov["nombre"] = data["nombre"].upper()
                data_mov["valor"] = -abs(data["valor"])
                output_path_mov = generar_comprobante(data_mov, COMPROBANTE_MOVIMIENTO_CONFIG)
                with open(output_path_mov, "rb") as f:
                    await update.message.reply_document(document=f, caption=" ")
                os.remove(output_path_mov)
                await send_success_message(update)
                del user_data_store[user_id]
            except Exception as e:
                logging.error(f"[ERROR Nequi step11] {e}", exc_info=True)
                await update.message.reply_text(f"⚠️ Error generando comprobante: {e}")
                del user_data_store[user_id]

    # --- TRANSFIYA ---
    elif tipo == "comprobante4":
        if step == 0:
            if not text.isdigit() or len(text) != 10 or not text.startswith('3'):
                await update.message.reply_text("El número tiene que empezar en 3 y tener exactamente 10 dígitos \nEjemplo: 3012223855 ")
                return
            data["telefono"] = text
            data["step"] = 1
            await update.message.reply_text(" Digite el valor ")
        elif step == 1:
            if not text.replace("-", "", 1).isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(text)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            if user_id in referencia_manual_mode and referencia_manual_mode[user_id]:
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia\n\nEjemplo: M12345678")
                return
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 2
                await update.message.reply_text("📅 Ingresa la fecha\n\nEjemplo: 06 de diciembre de 2025 a las 02:30 p. m.")
                return
            output_path = generar_comprobante(data, COMPROBANTE4_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov2 = {"telefono": data["telefono"], "valor": -abs(data["valor"]), "nombre": data["telefono"]}
            output_path_mov2 = generar_comprobante(data_mov2, COMPROBANTE_MOVIMIENTO2_CONFIG)
            with open(output_path_mov2, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_mov2)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 2:
            data["fecha_manual"] = text
            output_path = generar_comprobante(data, COMPROBANTE4_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov2 = {"telefono": data["telefono"], "valor": -abs(data["valor"]), "nombre": data["telefono"]}
            output_path_mov2 = generar_comprobante(data_mov2, COMPROBANTE_MOVIMIENTO2_CONFIG)
            with open(output_path_mov2, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_mov2)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante(data, COMPROBANTE4_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov2 = {"telefono": data["telefono"], "valor": -abs(data["valor"]), "nombre": data["telefono"]}
            output_path_mov2 = generar_comprobante(data_mov2, COMPROBANTE_MOVIMIENTO2_CONFIG)
            with open(output_path_mov2, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_mov2)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            output_path = generar_comprobante(data, COMPROBANTE4_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov2 = {"telefono": data["telefono"], "valor": -abs(data["valor"]), "nombre": data["telefono"]}
            output_path_mov2 = generar_comprobante(data_mov2, COMPROBANTE_MOVIMIENTO2_CONFIG)
            with open(output_path_mov2, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_mov2)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- MOVIMIENTOS ---
    elif tipo in ["movimiento", "movimiento2"]:
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 1:
            if not text.isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(text)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            cfg = COMPROBANTE_MOVIMIENTO_CONFIG if tipo == "movimiento" else COMPROBANTE_MOVIMIENTO2_CONFIG
            output_path = generar_comprobante(data, cfg)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE QR ---
    elif tipo == "comprobante_qr":
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 1:
            if not text.replace("-", "", 1).isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(text)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            if user_id in referencia_manual_mode and referencia_manual_mode[user_id]:
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia\n\nEjemplo: M12345678")
                return
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 2
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante(data, COMPROBANTE_QR_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov_qr = {"nombre": data["nombre"].upper(), "valor": -abs(data["valor"])}
            output_path_movqr = generar_comprobante(data_mov_qr, COMPROBANTE_MOVIMIENTO3_CONFIG)
            with open(output_path_movqr, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_movqr)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 2:
            data["fecha_manual"] = text
            output_path = generar_comprobante(data, COMPROBANTE_QR_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov_qr = {"nombre": data["nombre"].upper(), "valor": -abs(data["valor"])}
            output_path_movqr = generar_comprobante(data_mov_qr, COMPROBANTE_MOVIMIENTO3_CONFIG)
            with open(output_path_movqr, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_movqr)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante(data, COMPROBANTE_QR_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov_qr = {"nombre": data["nombre"].upper(), "valor": -abs(data["valor"])}
            output_path_movqr = generar_comprobante(data_mov_qr, COMPROBANTE_MOVIMIENTO3_CONFIG)
            with open(output_path_movqr, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_movqr)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            output_path = generar_comprobante(data, COMPROBANTE_QR_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov_qr = {"nombre": data["nombre"].upper(), "valor": -abs(data["valor"])}
            output_path_movqr = generar_comprobante(data_mov_qr, COMPROBANTE_MOVIMIENTO3_CONFIG)
            with open(output_path_movqr, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_movqr)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE NUEVO (LLAVES) ---
    elif tipo == "comprobante_nuevo":
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 1:
            val_txt = text.replace(".", "").replace(",", ".")
            try:
                valor = float(val_txt)
                if valor < 1000:
                    await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                    return
                data["valor"] = valor
            except ValueError:
                await update.message.reply_text(" El valor debe ser numérico. Intenta de nuevo ")
                return
            data["step"] = 2
            await update.message.reply_text(" Ingresa la llave ")
        elif step == 2:
            data["llave"] = text
            data["step"] = 3
            await update.message.reply_text(" Ingresa el banco ")
        elif step == 3:
            data["banco"] = text
            data["step"] = 4
            await update.message.reply_text(" Ingresa el número de quien envía ")
        elif step == 4:
            if not text.isdigit() or len(text) != 10 or not text.startswith('3'):
                await update.message.reply_text("El número tiene que empezar en 3 y tener exactamente 10 dígitos \nEjemplo: 3012223855 ")
                return
            data["numero_envia"] = text
            if user_id in referencia_manual_mode and referencia_manual_mode[user_id]:
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia\n\nEjemplo: M12345678")
                return
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 5
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante_nuevo(data, COMPROBANTE_NUEVO_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov_llaves = {"nombre": enmascarar_nombre(data["nombre"]), "valor": -abs(float(data["valor"]))}
            output_path_movllaves = generar_comprobante(data_mov_llaves, MVKEY_CONFIG)
            with open(output_path_movllaves, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_movllaves)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 5:
            data["fecha_manual"] = text
            output_path = generar_comprobante_nuevo(data, COMPROBANTE_NUEVO_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov_llaves = {"nombre": enmascarar_nombre(data["nombre"]), "valor": -abs(float(data["valor"]))}
            output_path_movllaves = generar_comprobante(data_mov_llaves, MVKEY_CONFIG)
            with open(output_path_movllaves, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_movllaves)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante_nuevo(data, COMPROBANTE_NUEVO_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov_llaves = {"nombre": enmascarar_nombre(data["nombre"]), "valor": -abs(float(data["valor"]))}
            output_path_movllaves = generar_comprobante(data_mov_llaves, MVKEY_CONFIG)
            with open(output_path_movllaves, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_movllaves)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            output_path = generar_comprobante_nuevo(data, COMPROBANTE_NUEVO_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path)
            data_mov_llaves = {"nombre": enmascarar_nombre(data["nombre"]), "valor": -abs(float(data["valor"]))}
            output_path_movllaves = generar_comprobante(data_mov_llaves, MVKEY_CONFIG)
            with open(output_path_movllaves, "rb") as f:
                await update.message.reply_document(document=f, caption=" ")
            os.remove(output_path_movllaves)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE ANULADO ---
    elif tipo == "comprobante_anulado":
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 1:
            if not text.replace("-", "", 1).isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(text)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 2
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante_anulado(data, COMPROBANTE_ANULADO_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ANULADO")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 2:
            data["fecha_manual"] = text
            output_path = generar_comprobante_anulado(data, COMPROBANTE_ANULADO_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" ANULADO")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE AHORROS ---
    elif tipo == "comprobante_ahorros":
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el número de cuenta ")
        elif step == 1:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text(" El número de cuenta debe tener exactamente 11 dígitos \nEjemplo: 12345678912 ")
                return
            data["numero_cuenta"] = text
            data["step"] = 2
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 2:
            valor_limpio = text.replace(".", "").replace(",", "").replace(" ", "")
            if not valor_limpio.isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(valor_limpio)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha\n\nEjemplo: 06 Sept 2025 - 01:23 p. m.")
                return
            output_path = generar_comprobante_ahorros(data, COMPROBANTE_AHORROS_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Ahorros")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            output_path = generar_comprobante_ahorros(data, COMPROBANTE_AHORROS_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Ahorros")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE CORRIENTE ---
    elif tipo == "comprobante_corriente":
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el número de cuenta ")
        elif step == 1:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text(" El número de cuenta debe tener exactamente 11 dígitos \nEjemplo: 12345678912 ")
                return
            data["numero_cuenta"] = text
            data["step"] = 2
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 2:
            valor_limpio = text.replace(".", "").replace(",", "").replace(" ", "")
            if not valor_limpio.isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(valor_limpio)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha\n\nEjemplo: 06 Sept 2025 - 01:23 p. m.")
                return
            output_path = generar_comprobante_ahorros(data, COMPROBANTE_AHORROS2_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante de Corriente")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            output_path = generar_comprobante_ahorros(data, COMPROBANTE_AHORROS2_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante de Corriente")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE DAVIPLATA ---
    elif tipo == "comprobante_daviplata":
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 1:
            valor_limpio = text.replace(".", "").replace(",", "").replace(" ", "")
            if not valor_limpio.isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(valor_limpio)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            data["step"] = 2
            await update.message.reply_text(" Ingresa los 4 dígitos de la cuenta que envia ")
        elif step == 2:
            if not text.isdigit() or len(text) != 4:
                await update.message.reply_text(" Deben ser exactamente 4 dígitos numéricos ")
                return
            data["recibe"] = text
            data["step"] = 3
            await update.message.reply_text(" Ingresa los 4 dígitos de la cuenta que recibe ")
        elif step == 3:
            if not text.isdigit() or len(text) != 4:
                await update.message.reply_text(" Deben ser exactamente 4 dígitos numéricos ")
                return
            data["envia"] = text
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 4
                await update.message.reply_text("📅 Ingresa la fecha\n\nEjemplo: 06/12/2025 - 02:30 PM")
                return
            output_path = generar_comprobante_daviplata(data, COMPROBANTE_DAVIPLATA_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Daviplata")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 4:
            data["fecha_manual"] = text
            output_path = generar_comprobante_daviplata(data, COMPROBANTE_DAVIPLATA_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Daviplata")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE BC A NQ Y T ---
    elif tipo == "comprobante_bc_nq_t":
        if step == 0:
            if not text.isdigit() or len(text) != 10 or not text.startswith('3'):
                await update.message.reply_text("El número tiene que empezar en 3 y tener exactamente 10 dígitos \nEjemplo: 3012223855 ")
                return
            data["telefono"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 1:
            valor_limpio = text.replace(".", "").replace(",", "").replace(" ", "")
            if not valor_limpio.isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(valor_limpio)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 2
                await update.message.reply_text("📅 Ingresa la fecha\n\nEjemplo: 06 Sept 2025 - 01:23 p. m.")
                return
            output_path = generar_comprobante_bc_nq_t(data, COMPROBANTE_BC_NQ_T_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante BC a NQ")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 2:
            data["fecha_manual"] = text
            output_path = generar_comprobante_bc_nq_t(data, COMPROBANTE_BC_NQ_T_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante BC a NQ")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE BC QR ---
    elif tipo == "comprobante_bc_qr":
        if step == 0:
            data["descripcion_qr"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 1:
            data["valor"] = text
            data["step"] = 2
            await update.message.reply_text(" Ingresa el nombre ")
        elif step == 2:
            data["nombre"] = text
            data["step"] = 3
            await update.message.reply_text(" Ingresa el número de cuenta ")
        elif step == 3:
            data["numero_cuenta"] = text
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 4
                await update.message.reply_text("📅 Ingresa la fecha\n\nEjemplo: 07 oct. 2025 - 02:34 a. m.")
                return
            output_path = generar_comprobante_bc_qr(data, COMPROBANTE_BC_QR_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante BC QR")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 4:
            data["fecha_manual"] = text
            output_path = generar_comprobante_bc_qr(data, COMPROBANTE_BC_QR_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante BC QR")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE NEQUI A BC ---
    elif tipo == "comprobante_nequi_bc":
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 1:
            valor_limpio = text.replace(".", "").replace(",", "").replace(" ", "")
            if not valor_limpio.isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(valor_limpio)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            data["step"] = 2
            await update.message.reply_text(" Ingresa el número de cuenta ")
        elif step == 2:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text(" El número de cuenta debe tener exactamente 11 dígitos \nEjemplo: 12345678912 ")
                return
            data["numero_cuenta"] = text
            if user_id in referencia_manual_mode and referencia_manual_mode[user_id]:
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia\n\nEjemplo: M12345678")
                return
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante_nequi_bc(data, COMPROBANTE_NEQUI_BC_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Nequi Corriente")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            output_path = generar_comprobante_nequi_bc(data, COMPROBANTE_NEQUI_BC_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Nequi Corriente")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante_nequi_bc(data, COMPROBANTE_NEQUI_BC_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Nequi Corriente")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            output_path = generar_comprobante_nequi_bc(data, COMPROBANTE_NEQUI_BC_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Nequi Corriente")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- COMPROBANTE NEQUI AHORROS ---
    elif tipo == "comprobante_nequi_ahorros":
        if step == 0:
            data["nombre"] = text
            data["step"] = 1
            await update.message.reply_text(" Ingresa el valor ")
        elif step == 1:
            valor_limpio = text.replace(".", "").replace(",", "").replace(" ", "")
            if not valor_limpio.isdigit():
                await update.message.reply_text(" El valor debe ser numérico ")
                return
            valor = int(valor_limpio)
            if valor < 1000:
                await update.message.reply_text(" El valor mínimo es $1,000. Intenta de nuevo ")
                return
            data["valor"] = valor
            data["step"] = 2
            await update.message.reply_text(" Ingresa el número de cuenta ")
        elif step == 2:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text(" El número de cuenta debe tener exactamente 11 dígitos \nEjemplo: 12345678912 ")
                return
            data["numero_cuenta"] = text
            if user_id in referencia_manual_mode and referencia_manual_mode[user_id]:
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia\n\nEjemplo: M12345678")
                return
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante_nequi_ahorros(data, COMPROBANTE_NEQUI_AHORROS_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Nequi Ahorros")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            output_path = generar_comprobante_nequi_ahorros(data, COMPROBANTE_NEQUI_AHORROS_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Nequi Ahorros")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha")
                return
            output_path = generar_comprobante_nequi_ahorros(data, COMPROBANTE_NEQUI_AHORROS_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Nequi Ahorros")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            output_path = generar_comprobante_nequi_ahorros(data, COMPROBANTE_NEQUI_AHORROS_CONFIG)
            with open(output_path, "rb") as f:
                await update.message.reply_document(document=f, caption=" Comprobante Nequi Ahorros")
            os.remove(output_path)
            await send_success_message(update)
            del user_data_store[user_id]

    # --- AGREGAR USUARIO (ADMIN) ---
    elif tipo == "agregar_usuario":
        if step == 0:
            if not text.isdigit():
                await update.message.reply_text("❌ El ID debe ser numérico. Intenta de nuevo:")
                return
            data["target_user_id"] = int(text)
            data["step"] = 1
            await update.message.reply_text("📝 Ingresa el nombre del usuario:")
        elif step == 1:
            data["nombre"] = text
            data["step"] = 2
            await update.message.reply_text("📅 Ingresa la fecha de vencimiento:\n(Ejemplo: lunes 12 de octubre de 2025)")
        elif step == 2:
            try:
                data["fecha_vencimiento"] = text
                auth_system.add_user(data["target_user_id"], data["nombre"])
                now = datetime.now(pytz.timezone("America/Bogota"))
                fecha_agregado = now.strftime("%d/%m/%Y %H:%M:%S")
                nombre_escaped = data['nombre'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                fecha_venc_escaped = data['fecha_vencimiento'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                admin_name_escaped = data['admin_name'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                mensaje_confirmacion = (
                    "✅ **Usuario Agregado Exitosamente**\n\n"
                    f"👤 **ID:** `{data['target_user_id']}`\n"
                    f"📝 **Nombre:** {nombre_escaped}\n"
                    f"📅 **Fecha de vencimiento:** {fecha_venc_escaped}\n"
                    f"🕐 **Agregado el:** {fecha_agregado}\n"
                    f"👨‍💼 **Agregado por:** {admin_name_escaped}"
                )
                await update.message.reply_text(mensaje_confirmacion, parse_mode='Markdown')
                if user_id != ADMIN_ID:
                    mensaje_admin = (
                        "🔔 **Nuevo Usuario Agregado**\n\n"
                        f"👤 **ID:** `{data['target_user_id']}`\n"
                        f"📝 **Nombre:** {nombre_escaped}\n"
                        f"📅 **Vence:** {fecha_venc_escaped}\n"
                        f"🕐 **Agregado:** {fecha_agregado}\n"
                        f"👨‍💼 **Por:** {admin_name_escaped} (`{user_id}`)"
                    )
                    await context.bot.send_message(chat_id=ADMIN_ID, text=mensaje_admin, parse_mode='Markdown')
                del user_data_store[user_id]
            except Exception as e:
                await update.message.reply_text(f"❌ Error al agregar usuario: {str(e)}")
                del user_data_store[user_id]

# ================= ADMIN COMMANDS =================
async def gratis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("comando solo para administradores.")
        return
    auth_system.set_gratis_mode(True)
    await update.message.reply_text("✅ **Modo Gratis ACTIVADO**\n\n🎉 Todos los usuarios pueden usar el bot ahora", parse_mode='Markdown')
    await notify_main_admin(context, user_id, update.effective_user.first_name, "Activó modo gratis")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("comando disponible solo para administradores.")
        return
    auth_system.set_gratis_mode(False)
    await update.message.reply_text("🔴 **Modo Gratis DESACTIVADO**\n\n🔒 Solo usuarios autorizados pueden usar el bot", parse_mode='Markdown')
    await notify_main_admin(context, user_id, update.effective_user.first_name, "Desactivó modo gratis")

async def agregar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("❌ Comando disponible solo para administradores.")
        return
    user_data_store[user_id] = {"step": 0, "tipo": "agregar_usuario", "admin_name": update.effective_user.first_name or "Admin"}
    await update.message.reply_text("👤 Ingresa el ID del usuario:")

async def eliminar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("comando disponible solo para adminsitradores.")
        return
    if not context.args:
        await update.message.reply_text(" Uso: /eliminar <id_usuario>")
        return
    try:
        target_user_id = int(context.args[0])
        if auth_system.remove_user(target_user_id):
            await update.message.reply_text(f" Usuario {target_user_id} desautorizado.")
        else:
            await update.message.reply_text(f" Usuario {target_user_id} no estaba autorizado.")
        await notify_main_admin(context, user_id, update.effective_user.first_name, "Eliminó usuario", str(target_user_id))
    except ValueError:
        await update.message.reply_text(" ID de usuario inválido.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("comando disponible solo para adminsitradores.")
        return
    stats = auth_system.get_stats()
    authorized_users = auth_system.get_authorized_users()
    banned_users = auth_system.get_banned_users()
    admin_users = auth_system.get_admin_users()
    message = f" **Estadísticas del Bot**\n\n Usuarios autorizados: {stats['total_authorized']}\n Usuarios baneados: {stats['total_banned']}\n Administradores: {stats['total_admins']}\n Modo gratis: {'Activado' if stats['gratis_mode'] else 'Desactivado'}\n\n **Administradores:**\n  {auth_system.admin_id} - Administrador Principal\n"
    if admin_users:
        for uid in admin_users:
            user_name = authorized_users.get(uid, f"Usuario_{uid}")
            message += f"  {uid} - {user_name}\n"
    if authorized_users:
        message += "\n **Usuarios autorizados:**\n"
        for uid, nombre in authorized_users.items():
            if uid != auth_system.admin_id and uid not in admin_users:
                message += f"  • {uid} - {nombre}\n"
    if banned_users:
        message += "\n **Usuarios baneados:**\n"
        for uid in banned_users:
            message += f"  • {uid}\n"
    await update.message.reply_text(message)

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("comando disponible solo par administradores.")
        return
    if not context.args:
        await update.message.reply_text(" Uso: /ban <id_usuario>")
        return
    try:
        target_user_id = int(context.args[0])
        auth_system.ban_user(target_user_id)
        await update.message.reply_text(f" Usuario {target_user_id} baneado.")
        await notify_main_admin(context, user_id, update.effective_user.first_name, "Baneó usuario", str(target_user_id))
    except ValueError:
        await update.message.reply_text(" ID de usuario inválido.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("comando disponible solo para adminsitradores.")
        return
    if not context.args:
        await update.message.reply_text(" Uso: /unban <id_usuario>")
        return
    try:
        target_user_id = int(context.args[0])
        if auth_system.unban_user(target_user_id):
            await update.message.reply_text(f" Usuario {target_user_id} desbaneado.")
        else:
            await update.message.reply_text(f" Usuario {target_user_id} no estaba baneado.")
        await notify_main_admin(context, user_id, update.effective_user.first_name, "Desbaneó usuario", str(target_user_id))
    except ValueError:
        await update.message.reply_text(" ID de usuario inválido.")

async def verificar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=REQUIRED_GROUP_ID, user_id=user_id)
        status = member.status
        status_emoji = {'creator': '👑', 'administrator': '🔧', 'member': '✅', 'restricted': '⚠️', 'left': '❌', 'kicked': '🚫'}
        emoji = status_emoji.get(status, '❓')
        message = f"{emoji} **Estado de Verificación**\n\n🆔 Tu ID: `{user_id}`\n📊 Estado: **{status.upper()}**\n\n"
        if status in ['member', 'administrator', 'creator', 'restricted']:
            message += "✅ **Tienes acceso al bot**"
        else:
            message += "❌ **No tienes acceso al bot**"
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error de verificación: {e}")

async def precios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💎 ¿Necesitas acceso a la APK?", callback_data="apk_precios")],
        [InlineKeyboardButton("Admin 1", url="https://t.me/Libertadyplata777")],
        [InlineKeyboardButton("Admin 2", url="https://t.me/Broquicalifoxx")],
        [InlineKeyboardButton("Admin 3", url="https://t.me/The_Offici4l")]
    ]
    await update.message.reply_text(
        "💵 **LISTA DE PRECIOS**\n\n📅 **Planes Mensuales:**\n• 1 Mes: $25,000\n• 2 Meses: $45,000\n• 3 Meses: $55,000\n\n🌟 **Plan Permanente:**\n• Contacta con algún admin para más info\n\n📞 **Para contratar contacta a:**",
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def horarios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕰️ **HORARIOS DE SERVICIO**\n\n🆓 **Horarios GRATIS:**\n\n🌅 **Mañana:**\n9:00 AM - 11:00 AM\n\n🌞 **Tarde:**\n12:00 PM - 3:00 PM\n\n——————————\n\n👑 **Usuarios VIP:**\n✅ Acceso 24/7 sin restricciones\n\n💎 Usa /precios para ver cómo ser VIP",
        parse_mode='Markdown'
    )

async def cancelar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
        await update.message.reply_text("se cancelo la operacion ")
    else:
        await update.message.reply_text("no tienes accioes activas usa /comprobante para iniciar una")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text(" Solo el administrador puede usar este comando.")
        return
    if len(context.args) < 1:
        await update.message.reply_text(" Uso: /admin <id_usuario>")
        return
    try:
        target_user_id = int(context.args[0])
        auth_system.add_admin(target_user_id)
        await update.message.reply_text(f" Usuario {target_user_id} agregado como administrador.")
        await notify_main_admin(context, user_id, update.effective_user.first_name, "Agregó administrador", str(target_user_id))
    except ValueError:
        await update.message.reply_text(" ID de usuario inválido.")

async def unadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text(" Solo el administrador puede usar este comando.")
        return
    if not context.args:
        await update.message.reply_text(" Uso: /unadmin <id_usuario>")
        return
    try:
        target_user_id = int(context.args[0])
        if auth_system.remove_admin(target_user_id):
            await update.message.reply_text(f" Usuario {target_user_id} removido como administrador.")
        else:
            await update.message.reply_text(f" Usuario {target_user_id} no era administrador.")
        await notify_main_admin(context, user_id, update.effective_user.first_name, "Removió administrador", str(target_user_id))
    except ValueError:
        await update.message.reply_text(" ID de usuario inválido.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def refe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("❌ Este comando solo está disponible para administradores.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Debes responder a una foto con /refe para guardarla como referencia.")
        return
    replied_message = update.message.reply_to_message
    if not replied_message.photo:
        await update.message.reply_text("❌ El mensaje debe contener una foto.")
        return
    try:
        photo = replied_message.photo[-1]
        file_id = photo.file_id
        admin_name = update.effective_user.first_name or "Admin"
        now = datetime.now(pytz.timezone("America/Bogota"))
        fecha = now.strftime("%d/%m/%Y %H:%M:%S")
        referencias = cargar_referencias()
        nueva_referencia = {"file_id": file_id, "guardado_por": admin_name, "user_id": user_id, "fecha": fecha, "numero": len(referencias) + 1}
        referencias.append(nueva_referencia)
        guardar_referencias(referencias)
        await update.message.reply_text(f"✅ **Referencia guardada**\n\n📸 **Número:** #{nueva_referencia['numero']}\n👤 **Guardado por:** {admin_name}\n📅 **Fecha:** {fecha}", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error al guardar referencia: {str(e)}")

async def referencias_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("❌ Este comando solo está disponible para administradores.")
        return
    try:
        referencias = cargar_referencias()
        if not referencias:
            await update.message.reply_text("📭 No hay referencias guardadas aún.")
            return
        await enviar_referencias_paginadas(update, context, referencias, 0)
    except Exception as e:
        await update.message.reply_text(f"❌ Error al mostrar referencias: {str(e)}")

async def enviar_referencias_paginadas(update_or_query, context, referencias, offset):
    if hasattr(update_or_query, 'callback_query') and update_or_query.callback_query is not None:
        chat_id = update_or_query.callback_query.message.chat_id
    else:
        chat_id = update_or_query.effective_chat.id
    total = len(referencias)
    fin = min(offset + 5, total)
    referencias_a_enviar = referencias[offset:fin]
    message_ids = []
    for ref in referencias_a_enviar:
        caption = f"📸 **Referencia #{ref['numero']}**\n👤 Guardado por: {ref['guardado_por']}\n📅 Fecha: {ref['fecha']}"
        try:
            file = await context.bot.get_file(ref['file_id'])
            file_path = await file.download_to_drive()
            with open(file_path, 'rb') as photo_file:
                msg = await context.bot.send_document(chat_id=chat_id, document=photo_file, caption=caption, parse_mode='Markdown', filename=f"referencia_{ref['numero']}.jpg")
            message_ids.append(msg.message_id)
            try:
                os.remove(file_path)
            except:
                pass
        except Exception as e:
            msg = await context.bot.send_message(chat_id=chat_id, text=f"❌ Error al enviar referencia #{ref['numero']}: {str(e)}")
            message_ids.append(msg.message_id)
    if fin < total:
        keyboard = [[InlineKeyboardButton(f"📥 Enviar las siguientes 5 ({fin + 1}-{min(fin + 5, total)} de {total})", callback_data=f"ref_next_{fin}_{','.join(map(str, message_ids))}")]]
        await context.bot.send_message(chat_id=chat_id, text="👇 Presiona el botón para ver más referencias:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id=chat_id, text="✅ Todas las referencias han sido enviadas.")

async def referencias_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_parts = query.data.split('_')
    offset = int(data_parts[2])
    message_ids = [int(mid) for mid in data_parts[3].split(',')]
    for msg_id in message_ids:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=msg_id)
        except Exception as e:
            logging.error(f"Error al borrar mensaje {msg_id}: {e}")
    try:
        await query.message.delete()
    except:
        pass
    referencias = cargar_referencias()
    await enviar_referencias_paginadas(update, context, referencias, offset)

async def apk_precios_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Admin 1", url="https://t.me/Libertadyplata777")],
        [InlineKeyboardButton("Admin 2", url="https://t.me/Broquicalifoxx")],
        [InlineKeyboardButton("Admin 3", url="https://t.me/The_Offici4l")]
    ]
    await query.message.reply_text(
        "📱 **PRECIOS OFICIALES DE APKs**\n\n💳 **Saldo para cualquier app:**\n\n• 20.000 COP → 5.000.000 de saldo\n• 35.000 COP → 8.000.000 de saldo\n• 45.000 COP → 10.000.000 de saldo\n• 55.000 COP → 15.000.000 de saldo\n• 70.000 COP → 25.000.000 de saldo\n• 85.000 COP → 35.000.000 de saldo\n• 100.000 COP → 50.000.000 de saldo\n\n📞 **Contacta para adquirir:**",
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def fechas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if auth_system.is_banned(user_id):
        await update.message.reply_text("Estás baneado de nuestros servicios")
        return
    if not auth_system.can_use_bot(user_id, chat_id):
        await update.message.reply_text("⚠️ No tienes acceso al bot")
        return
    if user_id in fecha_manual_mode and fecha_manual_mode[user_id]:
        fecha_manual_mode[user_id] = False
        await update.message.reply_text("📅 **Modo Fecha Automática ACTIVADO**\n\n✅ Los comprobantes usarán la fecha actual automáticamente", parse_mode='Markdown')
    else:
        fecha_manual_mode[user_id] = True
        await update.message.reply_text("📅 **Modo Fecha Manual ACTIVADO**\n\n✅ Ahora el bot te pedirá la fecha\n\n💡 Usa /fechas nuevamente para volver al modo automático", parse_mode='Markdown')

async def refes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if auth_system.is_banned(user_id):
        await update.message.reply_text("Estás baneado de nuestros servicios")
        return
    if not auth_system.can_use_bot(user_id, chat_id):
        await update.message.reply_text("⚠️ No tienes acceso al bot")
        return
    if user_id in referencia_manual_mode and referencia_manual_mode[user_id]:
        referencia_manual_mode[user_id] = False
        await update.message.reply_text("🔢 **Modo Referencia Automática ACTIVADO**\n\n✅ Los comprobantes generarán la referencia automáticamente", parse_mode='Markdown')
    else:
        referencia_manual_mode[user_id] = True
        await update.message.reply_text("🔢 **Modo Referencia Manual ACTIVADO**\n\n✅ Ahora el bot te pedirá la referencia\n📝 Formato: M + 8 dígitos (Ejemplo: M12345678)\n\n💡 Usa /refes nuevamente para volver al modo automático", parse_mode='Markdown')

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_main_admin(user_id):
        await update.message.reply_text("⛔ Acceso denegado. Solo el administrador principal puede usar este comando.")
        return
    stats = auth_system.get_stats()
    modo = "🟢 GRATIS (abierto)" if stats['gratis_mode'] else "🔴 OFF (solo autorizados)"
    texto = (
        "👑 *PANEL DE ADMINISTRADOR PRINCIPAL*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Estado actual:* {modo}\n"
        f"👥 *Usuarios autorizados:* {stats['total_authorized']}\n"
        f"🚫 *Usuarios baneados:* {stats['total_banned']}\n"
        f"🛡️ *Admins extra:* {stats['total_admins'] - 1}\n"
        f"🏠 *Grupo activo:* `{stats['allowed_group']}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ *COMANDOS DISPONIBLES:*\n\n"
        "🔓 /gratis — Abrir el bot para todos\n"
        "🔒 /off — Cerrar el bot (solo autorizados)\n"
        "➕ /agregar [ID] — Autorizar usuario\n"
        "➖ /eliminar [ID] — Quitar usuario\n"
        "🚫 /ban [ID] — Banear usuario\n"
        "✅ /unban [ID] — Desbanear usuario\n"
        "🛡️ /admin [ID] — Dar permisos de admin\n"
        "❌ /unadmin [ID] — Quitar admin\n"
        "📊 /stats — Ver estadísticas\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )
    keyboard = [
        [InlineKeyboardButton("🟢 Activar GRATIS", callback_data="panel_gratis"), InlineKeyboardButton("🔴 Activar OFF", callback_data="panel_off")],
        [InlineKeyboardButton("📊 Ver Stats", callback_data="panel_stats")]
    ]
    await update.message.reply_text(texto, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not auth_system.is_main_admin(user_id):
        await query.answer("⛔ Sin permisos.", show_alert=True)
        return
    await query.answer()
    if query.data == "panel_gratis":
        auth_system.set_gratis_mode(True)
        await query.edit_message_text("✅ Modo GRATIS activado. Todos los usuarios del grupo pueden usar el bot.")
    elif query.data == "panel_off":
        auth_system.set_gratis_mode(False)
        await query.edit_message_text("🔒 Modo OFF activado. Solo usuarios autorizados pueden usar el bot.")
    elif query.data == "panel_stats":
        stats = auth_system.get_stats()
        modo = "🟢 GRATIS" if stats['gratis_mode'] else "🔴 OFF"
        texto = f"📊 *Estadísticas*\n\nModo: {modo}\nUsuarios autorizados: {stats['total_authorized']}\nBaneados: {stats['total_banned']}\nAdmins: {stats['total_admins']}"
        await query.edit_message_text(texto, parse_mode='Markdown')

def main():
    app = Application.builder().token("8779045930:AAFf4CluVZS8OmEjsbYAsCCGaGqnKfoKXWw").build()
    app.add_handler(CommandHandler("comprobante", start))
    app.add_handler(CommandHandler("start", start_redirect))
    app.add_handler(CommandHandler("fechas", fechas_command))
    app.add_handler(CommandHandler("refes", refes_command))
    app.add_handler(CommandHandler("precios", precios_command))
    app.add_handler(CommandHandler("horarios", horarios_command))
    app.add_handler(CommandHandler("gratis", gratis_command))
    app.add_handler(CommandHandler("off", off_command))
    app.add_handler(CommandHandler("agregar", agregar_command))
    app.add_handler(CommandHandler("eliminar", eliminar_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("cancelar", cancelar_command))
    app.add_handler(CommandHandler("verificar", verificar_command))
    app.add_handler(CommandHandler("refe", refe_command))
    app.add_handler(CommandHandler("referencias", referencias_command))
    app.add_handler(CallbackQueryHandler(apk_precios_callback, pattern="^apk_precios$"))
    app.add_handler(CallbackQueryHandler(referencias_callback, pattern="^ref_next_"))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("unadmin", unadmin_command))
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CallbackQueryHandler(panel_callback, pattern="^panel_"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
