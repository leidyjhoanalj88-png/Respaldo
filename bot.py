import os
import zipfile

# ── Descomprimir fuentes automáticamente ──────────────────────────────────
if not os.path.exists("fuentes") and os.path.exists("fuentes.zip"):
    with zipfile.ZipFile("fuentes.zip", "r") as z:
        z.extractall(".")
    print("✅ Fuentes descomprimidas")

# ── Descomprimir imágenes automáticamente ─────────────────────────────────
if not os.path.exists("bcnd.jpg") and os.path.exists("img.zip"):
    with zipfile.ZipFile("img.zip", "r") as z:
        z.extractall(".")
    print("✅ Imágenes descomprimidas")

# ─────────────────────────────────────────────────────────────────────────

from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler, JobQueue
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
import asyncio
import logging
import traceback
from datetime import datetime, date, timedelta
import pytz
import json
import urllib.request
import urllib.parse

logging.basicConfig(level=logging.DEBUG)

BOT_TOKEN  = "8239033621:AAEjVqVXM6u9hT009gi1unSluwVMO93IWRs"
ADMIN_ID   = 8114050673
ALLOWED_GROUP    = -1003496628417
REQUIRED_GROUP_ID = -1003496628417
GROUP_LINK       = "https://t.me/httpsNequiblogger"

auth_system = AuthSystem(ADMIN_ID, ALLOWED_GROUP)
user_data_store = {}
fecha_manual_mode = {}
referencia_manual_mode = {}
REFERENCIAS_FILE = "referencias.json"
VENCIMIENTOS_FILE = "vencimientos.json"


def limpiar_valor(text):
    import unicodedata
    text = unicodedata.normalize('NFKC', text)
    return text.strip().replace(".", "").replace(",", "").replace(" ", "").replace("$", "").replace("\xa0", "").replace("\u200b", "")


def parsear_qr_emv(contenido):
    try:
        pos = 0
        datos = {}
        while pos + 4 <= len(contenido):
            tag = contenido[pos:pos+2]
            try:
                length = int(contenido[pos+2:pos+4])
            except ValueError:
                break
            value = contenido[pos+4:pos+4+length]
            datos[tag] = value
            pos += 4 + length
        if "59" in datos and datos["59"].strip():
            return datos["59"].strip()
        if "26" in datos:
            sub = datos["26"]
            sub_pos = 0
            while sub_pos + 4 <= len(sub):
                s_tag = sub[sub_pos:sub_pos+2]
                try:
                    s_len = int(sub[sub_pos+2:sub_pos+4])
                except ValueError:
                    break
                s_val = sub[sub_pos+4:sub_pos+4+s_len]
                if s_tag == "02" and s_val.strip():
                    return s_val.strip()
                sub_pos += 4 + s_len
    except Exception:
        pass
    return None


def extraer_nombre_qr(contenido):
    nombre_emv = parsear_qr_emv(contenido)
    if nombre_emv:
        return nombre_emv
    if "name=" in contenido.lower() or "&" in contenido or "=" in contenido:
        try:
            params = dict(urllib.parse.parse_qsl(contenido.split("?")[-1]))
            for key in ["name", "Name", "merchant", "businessName", "alias", "comercio", "negocio"]:
                if key in params and params[key].strip():
                    return params[key].strip()
        except Exception:
            pass
    return contenido[:40].strip()


def cargar_vencimientos():
    if os.path.exists(VENCIMIENTOS_FILE):
        try:
            with open(VENCIMIENTOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def guardar_vencimientos(data):
    with open(VENCIMIENTOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def agregar_vencimiento(user_id, nombre, dias=30):
    vencimientos = cargar_vencimientos()
    fecha_vence = (date.today() + timedelta(days=dias)).isoformat()
    vencimientos[str(user_id)] = {
        "nombre": nombre,
        "fecha_vence": fecha_vence,
        "dias": dias,
        "aviso3_enviado": False,
        "expirado_enviado": False
    }
    guardar_vencimientos(vencimientos)
    return fecha_vence

def eliminar_vencimiento(user_id):
    vencimientos = cargar_vencimientos()
    if str(user_id) in vencimientos:
        del vencimientos[str(user_id)]
        guardar_vencimientos(vencimientos)

async def verificar_vencimientos(context: ContextTypes.DEFAULT_TYPE):
    vencimientos = cargar_vencimientos()
    hoy = date.today()
    actualizar = False
    for uid_str, info in vencimientos.items():
        uid = int(uid_str)
        fecha_vence = date.fromisoformat(info["fecha_vence"])
        dias_restantes = (fecha_vence - hoy).days
        if dias_restantes == 3 and not info.get("aviso3_enviado"):
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"⚠️ *Aviso de Vencimiento*\n\n"
                        f"Hola {info['nombre']}, tu acceso al bot vence en *3 días* "
                        f"({fecha_vence.strftime('%d/%m/%Y')}).\n\n"
                        f"Renueva con un administrador para no perder el acceso.\n\n"
                        f"👑 ADM: @8114050673"
                    ),
                    parse_mode="Markdown"
                )
                info["aviso3_enviado"] = True
                actualizar = True
            except Exception as e:
                logging.error(f"[VENC] aviso3 {uid}: {e}")
        elif dias_restantes <= 0 and not info.get("expirado_enviado"):
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"🔴 *Acceso Expirado*\n\n"
                        f"Hola {info['nombre']}, tu acceso al bot ha expirado.\n\n"
                        f"Contacta a un administrador para renovar:\n\n"
                        f"👑 ADM 1\n"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👑 ADM", url="tg://user?id=8114050673")],
                        [InlineKeyboardButton("📢 Grupo", url=GROUP_LINK)]
                    ])
                )
                auth_system.remove_user(uid)
                info["expirado_enviado"] = True
                actualizar = True
            except Exception as e:
                logging.error(f"[VENC] expirado {uid}: {e}")
    if actualizar:
        guardar_vencimientos(vencimientos)


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


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 ¿Necesitas acceso?", callback_data="apk_precios")],
        [InlineKeyboardButton("👑 ADM", url="tg://user?id=8114050673")],
        [InlineKeyboardButton("📢 Grupo", url=GROUP_LINK)]
    ])


# ── Helper global para generar y enviar — muestra el error exacto ───────────
async def generar_y_enviar(update, fn, data, config, caption=" "):
    try:
        out = fn(data, config)
        with open(out, "rb") as f:
            await update.message.reply_document(document=f, caption=caption)
        os.remove(out)
        return True
    except Exception:
        tb = traceback.format_exc()
        logging.error(f"[ERROR COMPROBANTE] {tb}")
        await update.message.reply_text(
            f"❌ Error generando comprobante:\n<code>{tb[-1000:]}</code>",
            parse_mode="HTML"
        )
        return False
# ────────────────────────────────────────────────────────────────────────────


async def send_success_message(update: Update):
    await update.message.reply_text(
        "✅ **Comprobante generado con éxito**\n\nUsa /comprobante para generar otro",
        parse_mode='Markdown'
    )

async def notify_main_admin(context, admin_id, admin_name, action, target_info=""):
    if admin_id == ADMIN_ID:
        return
    try:
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        msg = f"🔔 *Notificación*\n👤 Admin: {admin_id} ({admin_name})\n⚡ {action}"
        if target_info:
            msg += f"\n🎯 {target_info}"
        msg += f"\n🕐 {now}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='Markdown')
    except Exception as e:
        print(f"[notify_admin error] {e}")


async def start_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenido al generador de comprobantes\n\n"
        "Comandos disponibles:\n"
        "/comprobante - Iniciar el bot\n"
        "/fechas - Fechas manuales\n"
        "/refes - Referencias manuales\n"
        "/horarios - Ver horarios gratis\n"
        "/precios - Ver planes premium\n\n"
        "Usa /comprobante para empezar",
        reply_markup=admin_keyboard()
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if auth_system.is_banned(user_id):
        await update.message.reply_text("Estás baneado. Contacta al administrador.")
        return

    if not auth_system.can_use_bot(user_id, chat_id):
        if not auth_system.gratis_mode:
            await update.message.reply_text(
                "🔴 **Bot en Modo OFF**\n\n💰 Contacta a un administrador para acceso premium.",
                parse_mode='Markdown',
                reply_markup=admin_keyboard()
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
        "Selecciona el comprobante que quieres generar:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if auth_system.is_banned(user_id):
        await update.message.reply_text("Estás baneado.")
        return

    if not auth_system.gratis_mode and not auth_system.can_use_bot(user_id, chat_id):
        await update.message.reply_text("⛔ No tienes acceso.", reply_markup=admin_keyboard())
        return

    if user_id in user_data_store:
        return

    await update.message.reply_text("🔍 Leyendo código QR...")
    try:
        import cv2
        import numpy as np

        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        detector = cv2.QRCodeDetector()
        contenido, _, _ = detector.detectAndDecode(img)

        if not contenido:
            await update.message.reply_text("❌ No se pudo leer el QR. Asegúrate que la imagen sea clara.")
            return

        nombre_negocio = extraer_nombre_qr(contenido)[:30].strip()
        user_data_store[user_id] = {
            "step": "qr_monto",
            "tipo": "comprobante_qr",
            "nombre": nombre_negocio,
        }
        await update.message.reply_text(
            f"✅ *QR leído*\n\n🏪 *Negocio:* {nombre_negocio}\n\n💰 ¿Cuánto es el monto?",
            parse_mode="Markdown"
        )
    except ImportError:
        await update.message.reply_text("❌ Error interno al leer QR.")
    except Exception as e:
        logging.error(f"[ERROR QR] {e}")
        await update.message.reply_text(f"❌ Error al leer el QR: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    logging.warning(f"[DEBUG] user={user_id} text={repr(text)} store={user_data_store.get(user_id)}")

    button_mapping = {
        "Nequi": "comprobante1", "Transfiya": "comprobante4",
        "Daviplata": "comprobante_daviplata", "Nequi QR": "comprobante_qr",
        "Bre B": "comprobante_nuevo", "Anulado": "comprobante_anulado",
        "Ahorros": "comprobante_ahorros", "Corriente": "comprobante_corriente",
        "BC a NQ": "comprobante_bc_nq_t", "BC QR": "comprobante_bc_qr",
        "Nequi Corriente": "comprobante_nequi_bc", "Nequi Ahorros": "comprobante_nequi_ahorros"
    }

    if text in button_mapping and user_id not in user_data_store:
        if not auth_system.can_use_bot(user_id, chat_id) and not auth_system.gratis_mode:
            await update.message.reply_text("🔴 Bot en Modo OFF", reply_markup=admin_keyboard())
            return
        if auth_system.is_banned(user_id):
            await update.message.reply_text("Estás baneado.")
            return
        tipo = button_mapping[text]
        user_data_store[user_id] = {"step": 0, "tipo": tipo}
        prompts = {
            "comprobante1": "¿Nombre? ", "comprobante4": "¿Número a transferir? ",
            "comprobante_qr": "¿Nombre del negocio? ", "comprobante_nuevo": "¿Nombre? ",
            "comprobante_anulado": "¿Nombre? ", "comprobante_corriente": "¿Nombre? ",
            "comprobante_daviplata": "¿Nombre de quien envía? ", "comprobante_ahorros": "¿Nombre? ",
            "comprobante_bc_nq_t": "¿Número de teléfono? ", "comprobante_bc_qr": "¿Descripción del QR? ",
            "comprobante_nequi_bc": "¿Nombre? ", "comprobante_nequi_ahorros": "¿Nombre? ",
        }
        await update.message.reply_text(prompts.get(tipo, "Ingresa los datos:"))
        return

    # Monto QR desde foto
    if user_id in user_data_store and user_data_store[user_id].get("step") == "qr_monto":
        data = user_data_store[user_id]
        limpio = limpiar_valor(text)
        if not limpio.replace("-","",1).isdigit():
            await update.message.reply_text("❌ El valor debe ser numérico."); return
        valor = int(limpio)
        if valor < 1000:
            await update.message.reply_text("❌ Mínimo $1,000."); return
        data["valor"] = valor
        await update.message.reply_text("⏳ Generando comprobante QR...")
        ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE_QR_CONFIG)
        if ok:
            dm = {"nombre": data["nombre"].upper(), "valor": -abs(valor)}
            await generar_y_enviar(update, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO3_CONFIG)
            await send_success_message(update)
        del user_data_store[user_id]
        return

    if user_id not in user_data_store:
        return
    if auth_system.is_banned(user_id):
        await update.message.reply_text("Estás baneado.")
        return

    data = user_data_store[user_id]
    tipo = data["tipo"]
    step = data["step"]

    # ── NEQUI ───────────────────────────────────────────────────────────────
    if tipo == "comprobante1":
        if step == 0:
            data["nombre"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el número de teléfono")
        elif step == 1:
            tel = text.strip().replace(" ", "").replace("-", "")
            if tel.startswith("+57"): tel = tel[3:]
            elif tel.startswith("57") and len(tel) == 12: tel = tel[2:]
            if not tel.isdigit() or len(tel) != 10 or not tel.startswith("3"):
                await update.message.reply_text("\u274c Número inválido. Debe tener 10 dígitos y empezar en 3.\nEjemplo: 3001234567\n\nUsa /cancelar para reiniciar."); return
            data["telefono"] = tel; data["step"] = 2
            await update.message.reply_text("Ingresa el valor")
        elif step == 2:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números, sin letras ni símbolos"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v
            if referencia_manual_mode.get(user_id): data["step"] = 10; await update.message.reply_text("🔢 Ingresa la referencia\nEjemplo: M12345678"); return
            if fecha_manual_mode.get(user_id): data["step"] = 3; await update.message.reply_text("📅 Ingresa la fecha"); return
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE1_CONFIG)
            if ok:
                dm = data.copy(); dm["nombre"] = data["nombre"].upper(); dm["valor"] = -abs(v)
                await generar_y_enviar(update, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE1_CONFIG)
            if ok:
                dm = data.copy(); dm["nombre"] = data["nombre"].upper(); dm["valor"] = -abs(data["valor"])
                await generar_y_enviar(update, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id): data["step"] = 11; await update.message.reply_text("📅 Ingresa la fecha"); return
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE1_CONFIG)
            if ok:
                dm = data.copy(); dm["nombre"] = data["nombre"].upper(); dm["valor"] = -abs(data["valor"])
                await generar_y_enviar(update, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE1_CONFIG)
            if ok:
                dm = data.copy(); dm["nombre"] = data["nombre"].upper(); dm["valor"] = -abs(data["valor"])
                await generar_y_enviar(update, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]

    # ── TRANSFIYA ───────────────────────────────────────────────────────────
    elif tipo == "comprobante4":
        if step == 0:
            if not text.isdigit() or len(text) != 10 or not text.startswith('3'):
                await update.message.reply_text("❌ Número inválido. 10 dígitos, empieza en 3.\nUsa /cancelar para reiniciar."); return
            data["telefono"] = text; data["step"] = 1
            await update.message.reply_text("Digite el valor")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v
            if referencia_manual_mode.get(user_id): data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id): data["step"] = 2; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE4_CONFIG)
            if ok:
                dm2 = {"telefono": data["telefono"], "valor": -abs(v), "nombre": data["telefono"]}
                await generar_y_enviar(update, generar_comprobante, dm2, COMPROBANTE_MOVIMIENTO2_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 2:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE4_CONFIG)
            if ok:
                dm2 = {"telefono": data["telefono"], "valor": -abs(data["valor"]), "nombre": data["telefono"]}
                await generar_y_enviar(update, generar_comprobante, dm2, COMPROBANTE_MOVIMIENTO2_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id): data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE4_CONFIG)
            if ok:
                dm2 = {"telefono": data["telefono"], "valor": -abs(data["valor"]), "nombre": data["telefono"]}
                await generar_y_enviar(update, generar_comprobante, dm2, COMPROBANTE_MOVIMIENTO2_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE4_CONFIG)
            if ok:
                dm2 = {"telefono": data["telefono"], "valor": -abs(data["valor"]), "nombre": data["telefono"]}
                await generar_y_enviar(update, generar_comprobante, dm2, COMPROBANTE_MOVIMIENTO2_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]

    # ── NEQUI QR ────────────────────────────────────────────────────────────
    elif tipo == "comprobante_qr":
        if step == 0:
            data["nombre"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el valor")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v
            if referencia_manual_mode.get(user_id): data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id): data["step"] = 2; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE_QR_CONFIG)
            if ok:
                dm = {"nombre": data["nombre"].upper(), "valor": -abs(v)}
                await generar_y_enviar(update, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO3_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 2:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE_QR_CONFIG)
            if ok:
                dm = {"nombre": data["nombre"].upper(), "valor": -abs(data["valor"])}
                await generar_y_enviar(update, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO3_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id): data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE_QR_CONFIG)
            if ok:
                dm = {"nombre": data["nombre"].upper(), "valor": -abs(data["valor"])}
                await generar_y_enviar(update, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO3_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante, data, COMPROBANTE_QR_CONFIG)
            if ok:
                dm = {"nombre": data["nombre"].upper(), "valor": -abs(data["valor"])}
                await generar_y_enviar(update, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO3_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]

    # ── ANULADO ─────────────────────────────────────────────────────────────
    elif tipo == "comprobante_anulado":
        if step == 0:
            data["nombre"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el valor")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v
            if fecha_manual_mode.get(user_id): data["step"] = 2; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_anulado, data, COMPROBANTE_ANULADO_CONFIG, "ANULADO")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 2:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_anulado, data, COMPROBANTE_ANULADO_CONFIG, "ANULADO")
            if ok: await send_success_message(update)
            del user_data_store[user_id]

    # ── AHORROS ─────────────────────────────────────────────────────────────
    elif tipo == "comprobante_ahorros":
        if step == 0:
            data["nombre"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el número de cuenta")
        elif step == 1:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11: await update.message.reply_text("Cuenta debe tener 11 dígitos"); return
            data["numero_cuenta"] = text; data["step"] = 2
            await update.message.reply_text("Ingresa el valor")
        elif step == 2:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v
            if fecha_manual_mode.get(user_id): data["step"] = 3; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_ahorros, data, COMPROBANTE_AHORROS_CONFIG, "Ahorros")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_ahorros, data, COMPROBANTE_AHORROS_CONFIG, "Ahorros")
            if ok: await send_success_message(update)
            del user_data_store[user_id]

    # ── CORRIENTE ───────────────────────────────────────────────────────────
    elif tipo == "comprobante_corriente":
        if step == 0:
            data["nombre"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el número de cuenta")
        elif step == 1:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11: await update.message.reply_text("Cuenta debe tener 11 dígitos"); return
            data["numero_cuenta"] = text; data["step"] = 2
            await update.message.reply_text("Ingresa el valor")
        elif step == 2:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v
            if fecha_manual_mode.get(user_id): data["step"] = 3; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_ahorros, data, COMPROBANTE_AHORROS2_CONFIG, "Corriente")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_ahorros, data, COMPROBANTE_AHORROS2_CONFIG, "Corriente")
            if ok: await send_success_message(update)
            del user_data_store[user_id]

    # ── DAVIPLATA ───────────────────────────────────────────────────────────
    elif tipo == "comprobante_daviplata":
        if step == 0:
            data["nombre"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el valor")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v; data["step"] = 2
            await update.message.reply_text("Ingresa los 4 dígitos de la cuenta que envía")
        elif step == 2:
            if not text.isdigit() or len(text) != 4: await update.message.reply_text("4 dígitos exactos"); return
            data["recibe"] = text; data["step"] = 3
            await update.message.reply_text("Ingresa los 4 dígitos de la cuenta que recibe")
        elif step == 3:
            if not text.isdigit() or len(text) != 4: await update.message.reply_text("4 dígitos exactos"); return
            data["envia"] = text
            if fecha_manual_mode.get(user_id): data["step"] = 4; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_daviplata, data, COMPROBANTE_DAVIPLATA_CONFIG, "Daviplata")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 4:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_daviplata, data, COMPROBANTE_DAVIPLATA_CONFIG, "Daviplata")
            if ok: await send_success_message(update)
            del user_data_store[user_id]

    # ── BC A NQ ─────────────────────────────────────────────────────────────
    elif tipo == "comprobante_bc_nq_t":
        if step == 0:
            if not text.isdigit() or len(text) != 10 or not text.startswith('3'):
                await update.message.reply_text("❌ Número inválido. 10 dígitos, empieza en 3.\nUsa /cancelar para reiniciar."); return
            data["telefono"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el valor")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v
            if fecha_manual_mode.get(user_id): data["step"] = 2; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_bc_nq_t, data, COMPROBANTE_BC_NQ_T_CONFIG, "BC a NQ")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 2:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_bc_nq_t, data, COMPROBANTE_BC_NQ_T_CONFIG, "BC a NQ")
            if ok: await send_success_message(update)
            del user_data_store[user_id]

    # ── BC QR ────────────────────────────────────────────────────────────────
    elif tipo == "comprobante_bc_qr":
        if step == 0:
            data["descripcion_qr"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el valor")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números, sin letras ni símbolos"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v; data["step"] = 2
            await update.message.reply_text("Ingresa el nombre")
        elif step == 2:
            data["nombre"] = text; data["step"] = 3
            await update.message.reply_text("Ingresa el número de cuenta")
        elif step == 3:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) < 8:
                await update.message.reply_text("❌ Número de cuenta inválido"); return
            data["numero_cuenta"] = text
            if fecha_manual_mode.get(user_id): data["step"] = 4; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_bc_qr, data, COMPROBANTE_BC_QR_CONFIG, "BC QR")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 4:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_bc_qr, data, COMPROBANTE_BC_QR_CONFIG, "BC QR")
            if ok: await send_success_message(update)
            del user_data_store[user_id]

    # ── NEQUI CORRIENTE ─────────────────────────────────────────────────────
    elif tipo == "comprobante_nequi_bc":
        if step == 0:
            data["nombre"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el valor")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v; data["step"] = 2
            await update.message.reply_text("Ingresa el número de cuenta")
        elif step == 2:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11: await update.message.reply_text("Cuenta debe tener 11 dígitos"); return
            data["numero_cuenta"] = text
            if referencia_manual_mode.get(user_id): data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id): data["step"] = 3; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_nequi_bc, data, COMPROBANTE_NEQUI_BC_CONFIG, "Nequi Corriente")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_nequi_bc, data, COMPROBANTE_NEQUI_BC_CONFIG, "Nequi Corriente")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id): data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_nequi_bc, data, COMPROBANTE_NEQUI_BC_CONFIG, "Nequi Corriente")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_nequi_bc, data, COMPROBANTE_NEQUI_BC_CONFIG, "Nequi Corriente")
            if ok: await send_success_message(update)
            del user_data_store[user_id]

    # ── NEQUI AHORROS ───────────────────────────────────────────────────────
    elif tipo == "comprobante_nequi_ahorros":
        if step == 0:
            data["nombre"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el valor")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-","",1).isdigit(): await update.message.reply_text("❌ Ingresa solo números"); return
            v = int(limpio)
            if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
            data["valor"] = v; data["step"] = 2
            await update.message.reply_text("Ingresa el número de cuenta")
        elif step == 2:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11: await update.message.reply_text("Cuenta debe tener 11 dígitos"); return
            data["numero_cuenta"] = text
            if referencia_manual_mode.get(user_id): data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id): data["step"] = 3; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_nequi_ahorros, data, COMPROBANTE_NEQUI_AHORROS_CONFIG, "Nequi Ahorros")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 3:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_nequi_ahorros, data, COMPROBANTE_NEQUI_AHORROS_CONFIG, "Nequi Ahorros")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id): data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_nequi_ahorros, data, COMPROBANTE_NEQUI_AHORROS_CONFIG, "Nequi Ahorros")
            if ok: await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_nequi_ahorros, data, COMPROBANTE_NEQUI_AHORROS_CONFIG, "Nequi Ahorros")
            if ok: await send_success_message(update)
            del user_data_store[user_id]

    # ── BRE B ───────────────────────────────────────────────────────────────
    elif tipo == "comprobante_nuevo":
        if step == 0:
            data["nombre"] = text; data["step"] = 1
            await update.message.reply_text("Ingresa el valor")
        elif step == 1:
            try:
                limpio = limpiar_valor(text)
                v = float(limpio)
                if v < 1000: await update.message.reply_text("Mínimo $1,000"); return
                data["valor"] = v
            except: await update.message.reply_text("❌ Ingresa solo números"); return
            data["step"] = 2; await update.message.reply_text("Ingresa la llave")
        elif step == 2:
            data["llave"] = text; data["step"] = 3
            await update.message.reply_text("Ingresa el banco")
        elif step == 3:
            data["banco"] = text; data["step"] = 4
            await update.message.reply_text("Ingresa el número de quien envía")
        elif step == 4:
            if not text.isdigit() or len(text) != 10 or not text.startswith('3'):
                await update.message.reply_text("❌ Número inválido. 10 dígitos, empieza en 3.\nUsa /cancelar para reiniciar."); return
            data["numero_envia"] = text
            if referencia_manual_mode.get(user_id): data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id): data["step"] = 5; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_nuevo, data, COMPROBANTE_NUEVO_CONFIG)
            if ok:
                await asyncio.sleep(1.5)
                dm = {"nombre": enmascarar_nombre(data["nombre"]), "valor": -abs(float(data["valor"]))}
                await generar_y_enviar(update, generar_comprobante, dm, MVKEY_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 5:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_nuevo, data, COMPROBANTE_NUEVO_CONFIG)
            if ok:
                await asyncio.sleep(1.5)
                dm = {"nombre": enmascarar_nombre(data["nombre"]), "valor": -abs(float(data["valor"]))}
                await generar_y_enviar(update, generar_comprobante, dm, MVKEY_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id): data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            ok = await generar_y_enviar(update, generar_comprobante_nuevo, data, COMPROBANTE_NUEVO_CONFIG)
            if ok:
                await asyncio.sleep(1.5)
                dm = {"nombre": enmascarar_nombre(data["nombre"]), "valor": -abs(float(data["valor"]))}
                await generar_y_enviar(update, generar_comprobante, dm, MVKEY_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]
        elif step == 11:
            data["fecha_manual"] = text
            ok = await generar_y_enviar(update, generar_comprobante_nuevo, data, COMPROBANTE_NUEVO_CONFIG)
            if ok:
                await asyncio.sleep(1.5)
                dm = {"nombre": enmascarar_nombre(data["nombre"]), "valor": -abs(float(data["valor"]))}
                await generar_y_enviar(update, generar_comprobante, dm, MVKEY_CONFIG)
                await send_success_message(update)
            del user_data_store[user_id]

    # ── AGREGAR USUARIO ─────────────────────────────────────────────────────
    elif tipo == "agregar_usuario":
        if step == 0:
            if not text.isdigit(): await update.message.reply_text("❌ ID numérico"); return
            data["target_user_id"] = int(text); data["step"] = 1
            await update.message.reply_text("📝 Nombre del usuario:")
        elif step == 1:
            data["nombre"] = text; data["step"] = 2
            await update.message.reply_text("📅 ¿Cuántos días de acceso? (Ejemplo: 30)")
        elif step == 2:
            if not text.isdigit(): await update.message.reply_text("❌ Número de días numérico"); return
            dias = int(text)
            try:
                auth_system.add_user(data["target_user_id"], data["nombre"])
                fecha_vence = agregar_vencimiento(data["target_user_id"], data["nombre"], dias)
                now = datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S")
                admin_name = data.get("admin_name", "Admin")
                await update.message.reply_text(
                    f"✅ *Usuario Agregado*\n\n"
                    f"👤 ID: `{data['target_user_id']}`\n"
                    f"📝 Nombre: {data['nombre']}\n"
                    f"📅 Vence: {fecha_vence}\n"
                    f"⏳ Días: {dias}\n"
                    f"🕐 Agregado: {now}",
                    parse_mode='Markdown'
                )
                try:
                    await context.bot.send_message(
                        chat_id=data["target_user_id"],
                        text=(
                            f"✅ *¡Acceso Activado!*\n\n"
                            f"Hola {data['nombre']}, tu acceso al bot ha sido activado.\n\n"
                            f"📅 Vence el: *{fecha_vence}*\n"
                            f"⏳ Duración: *{dias} días*\n\n"
                            f"Usa /comprobante para empezar."
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"[VENC] No se pudo notificar al usuario {data['target_user_id']}: {e}")
                if user_id != ADMIN_ID:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"🔔 *Nuevo usuario agregado*\nID: `{data['target_user_id']}`\nNombre: {data['nombre']}\nVence: {fecha_vence}\nPor: {admin_name}",
                        parse_mode='Markdown'
                    )
                del user_data_store[user_id]
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}")
                del user_data_store[user_id]


# ─────────────────────────────────────────────
# Comandos Admin
# ─────────────────────────────────────────────
async def gratis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    auth_system.set_gratis_mode(True)
    await update.message.reply_text("✅ Modo GRATIS activado.", parse_mode='Markdown')

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    auth_system.set_gratis_mode(False)
    await update.message.reply_text("🔴 Modo OFF activado.", parse_mode='Markdown')

async def agregar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    user_data_store[user_id] = {"step": 0, "tipo": "agregar_usuario", "admin_name": update.effective_user.first_name or "Admin"}
    await update.message.reply_text("👤 Ingresa el ID del usuario:")

async def eliminar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /eliminar <id>"); return
    try:
        tid = int(context.args[0])
        auth_system.remove_user(tid)
        eliminar_vencimiento(tid)
        await update.message.reply_text(f"✅ Usuario {tid} eliminado.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /ban <id>"); return
    try:
        tid = int(context.args[0])
        auth_system.ban_user(tid)
        await update.message.reply_text(f"🚫 Usuario {tid} baneado.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /unban <id>"); return
    try:
        tid = int(context.args[0])
        auth_system.unban_user(tid)
        await update.message.reply_text(f"✅ Usuario {tid} desbaneado.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    s = auth_system.get_stats()
    await update.message.reply_text(
        f"📊 *Estadísticas*\n\n"
        f"👥 Autorizados: {s['total_authorized']}\n"
        f"🚫 Baneados: {s['total_banned']}\n"
        f"🛡️ Admins: {s['total_admins']}\n"
        f"🆓 Modo gratis: {'Sí' if s['gratis_mode'] else 'No'}",
        parse_mode='Markdown'
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /admin <id>"); return
    try:
        tid = int(context.args[0])
        auth_system.add_admin(tid)
        await update.message.reply_text(f"✅ {tid} es admin ahora.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def unadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /unadmin <id>"); return
    try:
        tid = int(context.args[0])
        auth_system.remove_admin(tid)
        await update.message.reply_text(f"✅ {tid} ya no es admin.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def cancelar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
        await update.message.reply_text("✅ Operación cancelada.")
    else:
        await update.message.reply_text("No tienes acciones activas. Usa /comprobante para iniciar.")

async def fechas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if auth_system.is_banned(user_id): await update.message.reply_text("Estás baneado."); return
    if not auth_system.can_use_bot(user_id, chat_id) and not auth_system.gratis_mode:
        await update.message.reply_text("⚠️ No tienes acceso."); return
    if fecha_manual_mode.get(user_id):
        fecha_manual_mode[user_id] = False
        await update.message.reply_text("📅 Modo Fecha *Automática* activado.", parse_mode='Markdown')
    else:
        fecha_manual_mode[user_id] = True
        await update.message.reply_text("📅 Modo Fecha *Manual* activado.", parse_mode='Markdown')

async def refes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if auth_system.is_banned(user_id): await update.message.reply_text("Estás baneado."); return
    if not auth_system.can_use_bot(user_id, chat_id) and not auth_system.gratis_mode:
        await update.message.reply_text("⚠️ No tienes acceso."); return
    if referencia_manual_mode.get(user_id):
        referencia_manual_mode[user_id] = False
        await update.message.reply_text("🔢 Modo Referencia *Automática* activado.", parse_mode='Markdown')
    else:
        referencia_manual_mode[user_id] = True
        await update.message.reply_text("🔢 Modo Referencia *Manual* activado.", parse_mode='Markdown')

async def precios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💵 *LISTA DE PRECIOS*\n\n"
        "• 1 Mes: $25,000\n• 2 Meses: $45,000\n• 3 Meses: $55,000\n\n"
        "📞 Contacta a un admin para contratar:",
        parse_mode='Markdown', reply_markup=admin_keyboard()
    )

async def horarios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕰️ *HORARIOS GRATIS*\n\n🌅 9:00 AM - 11:00 AM\n🌞 12:00 PM - 3:00 PM\n\n"
        "👑 VIP: Acceso 24/7\n\n💎 Usa /precios para ser VIP",
        parse_mode='Markdown'
    )

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_main_admin(user_id):
        await update.message.reply_text("⛔ Solo el ADM 1 puede usar este panel."); return
    s = auth_system.get_stats()
    modo = "🟢 GRATIS" if s['gratis_mode'] else "🔴 OFF"
    texto = (
        "👑 *PANEL ADM 1*\n━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Modo: {modo}\n"
        f"👥 Autorizados: {s['total_authorized']}\n"
        f"🚫 Baneados: {s['total_banned']}\n"
        f"🛡️ Admins: {s['total_admins']}\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "⚙️ *COMANDOS:*\n\n"
        "🆓 /gratis — Abrir para todos\n"
        "🔒 /off — Solo autorizados\n"
        "➕ /agregar — Autorizar usuario\n"
        "➖ /eliminar [ID] — Quitar usuario\n"
        "🚫 /ban [ID] — Banear\n"
        "✅ /unban [ID] — Desbanear\n"
        "🛡️ /admin [ID] — Dar admin\n"
        "❌ /unadmin [ID] — Quitar admin\n"
        "📊 /stats — Estadísticas\n"
        "━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 GRATIS", callback_data="panel_gratis"),
         InlineKeyboardButton("🔴 OFF", callback_data="panel_off")],
        [InlineKeyboardButton("📊 Stats", callback_data="panel_stats")]
    ])
    await update.message.reply_text(texto, parse_mode='Markdown', reply_markup=kb)

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not auth_system.is_main_admin(user_id):
        await query.answer("⛔ Sin permisos.", show_alert=True); return
    await query.answer()
    if query.data == "panel_gratis":
        auth_system.set_gratis_mode(True)
        await query.edit_message_text("✅ Modo GRATIS activado.")
    elif query.data == "panel_off":
        auth_system.set_gratis_mode(False)
        await query.edit_message_text("🔒 Modo OFF activado.")
    elif query.data == "panel_stats":
        s = auth_system.get_stats()
        await query.edit_message_text(
            f"📊 *Stats*\nModo: {'🟢' if s['gratis_mode'] else '🔴'}\n"
            f"Autorizados: {s['total_authorized']}\nBaneados: {s['total_banned']}",
            parse_mode='Markdown'
        )

async def apk_precios_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "💵 *LISTA DE PRECIOS*\n\n"
        "• 1 Mes: $25,000\n• 2 Meses: $45,000\n• 3 Meses: $55,000\n\n"
        "📞 Contacta a un admin para contratar:",
        parse_mode='Markdown', reply_markup=admin_keyboard()
    )

async def refe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("❌ Responde a una foto con /refe."); return
    try:
        photo = update.message.reply_to_message.photo[-1]
        referencias = cargar_referencias()
        nueva = {"file_id": photo.file_id, "guardado_por": update.effective_user.first_name or "Admin",
                 "user_id": user_id, "fecha": datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S"),
                 "numero": len(referencias) + 1}
        referencias.append(nueva)
        guardar_referencias(referencias)
        await update.message.reply_text(f"✅ Referencia #{nueva['numero']} guardada.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def referencias_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id): await update.message.reply_text("❌ Solo admins."); return
    referencias = cargar_referencias()
    if not referencias: await update.message.reply_text("📭 No hay referencias."); return
    await enviar_referencias_paginadas(update, context, referencias, 0)

async def enviar_referencias_paginadas(update_or_query, context, referencias, offset):
    if hasattr(update_or_query, 'callback_query') and update_or_query.callback_query:
        chat_id = update_or_query.callback_query.message.chat_id
    else:
        chat_id = update_or_query.effective_chat.id
    total = len(referencias)
    fin = min(offset + 5, total)
    message_ids = []
    for ref in referencias[offset:fin]:
        caption = f"📸 *#{ref['numero']}* — {ref['guardado_por']} — {ref['fecha']}"
        try:
            file = await context.bot.get_file(ref['file_id'])
            file_path = await file.download_to_drive()
            with open(file_path, 'rb') as pf:
                msg = await context.bot.send_document(chat_id=chat_id, document=pf, caption=caption, parse_mode='Markdown', filename=f"ref_{ref['numero']}.jpg")
            message_ids.append(msg.message_id)
            try: os.remove(file_path)
            except: pass
        except Exception as e:
            msg = await context.bot.send_message(chat_id=chat_id, text=f"❌ Error ref #{ref['numero']}: {e}")
            message_ids.append(msg.message_id)
    if fin < total:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"📥 Ver más ({fin+1}-{min(fin+5,total)} de {total})",
            callback_data=f"ref_next_{fin}_{','.join(map(str,message_ids))}")]])
        await context.bot.send_message(chat_id=chat_id, text="👇 Más referencias:", reply_markup=kb)
    else:
        await context.bot.send_message(chat_id=chat_id, text="✅ Todas las referencias enviadas.")

async def referencias_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    offset = int(parts[2])
    for mid in [int(x) for x in parts[3].split(',')]:
        try: await context.bot.delete_message(chat_id=query.message.chat_id, message_id=mid)
        except: pass
    try: await query.message.delete()
    except: pass
    await enviar_referencias_paginadas(update, context, cargar_referencias(), offset)


def main():
    app = Application.builder().token(BOT_TOKEN).job_queue(JobQueue()).build()
    app.job_queue.run_repeating(verificar_vencimientos, interval=43200, first=60)

    app.add_handler(CommandHandler("comprobante", start))
    app.add_handler(CommandHandler("start",       start_redirect))
    app.add_handler(CommandHandler("fechas",      fechas_command))
    app.add_handler(CommandHandler("refes",       refes_command))
    app.add_handler(CommandHandler("precios",     precios_command))
    app.add_handler(CommandHandler("horarios",    horarios_command))
    app.add_handler(CommandHandler("gratis",      gratis_command))
    app.add_handler(CommandHandler("off",         off_command))
    app.add_handler(CommandHandler("agregar",     agregar_command))
    app.add_handler(CommandHandler("eliminar",    eliminar_command))
    app.add_handler(CommandHandler("stats",       stats_command))
    app.add_handler(CommandHandler("ban",         ban_command))
    app.add_handler(CommandHandler("unban",       unban_command))
    app.add_handler(CommandHandler("cancelar",    cancelar_command))
    app.add_handler(CommandHandler("refe",        refe_command))
    app.add_handler(CommandHandler("referencias", referencias_command))
    app.add_handler(CommandHandler("admin",       admin_command))
    app.add_handler(CommandHandler("unadmin",     unadmin_command))
    app.add_handler(CommandHandler("panel",       panel_command))

    app.add_handler(CallbackQueryHandler(apk_precios_callback,  pattern="^apk_precios$"))
    app.add_handler(CallbackQueryHandler(referencias_callback,  pattern="^ref_next_"))
    app.add_handler(CallbackQueryHandler(panel_callback,        pattern="^panel_"))

    app.add_handler(MessageHandler(filters.PHOTO,                   handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
