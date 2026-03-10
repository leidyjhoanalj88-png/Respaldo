import os
import sys
import zipfile
import signal
import subprocess
import urllib.request as _urllib_req
import time as _time

# ══════════════════════════════════════════════════════════════════════════
# FIX CONFLICT: limpiar webhook + sesión previa de Telegram al arrancar
# ══════════════════════════════════════════════════════════════════════════
_BOT_TOKEN_INIT = "8069968534:AAFDKtsi4oIbW-t5Bn-UcR_Sf4DXyWbF9E0"

def limpiar_sesion_telegram():
    """Borra webhook y cierra sesión previa para evitar el error Conflict."""
    base = f"https://api.telegram.org/bot{_BOT_TOKEN_INIT}"
    for i in range(3):
        try:
            _urllib_req.urlopen(f"{base}/deleteWebhook?drop_pending_updates=true", timeout=10)
            _urllib_req.urlopen(f"{base}/close", timeout=10)
            print("✅ Sesión anterior cerrada. Esperando 5s...")
            _time.sleep(5)
            return
        except Exception as e:
            print(f"[limpiar_sesion] intento {i+1}: {e}")
            _time.sleep(2)

limpiar_sesion_telegram()

# ── Kill procesos locales duplicados ──────────────────────────────────────
def kill_otras_instancias():
    current_pid = os.getpid()
    script_name = os.path.basename(__file__)
    try:
        result = subprocess.run(
            ["pgrep", "-f", script_name],
            capture_output=True, text=True
        )
        for pid_str in result.stdout.strip().splitlines():
            try:
                pid = int(pid_str)
                if pid != current_pid:
                    print(f"⚠️ Matando instancia previa PID={pid}")
                    os.kill(pid, signal.SIGKILL)
            except (ValueError, ProcessLookupError, PermissionError):
                pass
    except Exception as e:
        print(f"[kill_otras_instancias] {e}")

kill_otras_instancias()


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

from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from config import (
    COMPROBANTE1_CONFIG, COMPROBANTE4_CONFIG,
    COMPROBANTE_MOVIMIENTO_CONFIG, COMPROBANTE_MOVIMIENTO2_CONFIG,
    COMPROBANTE_QR_CONFIG, COMPROBANTE_NUEVO_CONFIG,
    COMPROBANTE_ANULADO_CONFIG, COMPROBANTE_MOVIMIENTO3_CONFIG,
    MVKEY_CONFIG, COMPROBANTE_AHORROS_CONFIG, COMPROBANTE_AHORROS2_CONFIG,
    COMPROBANTE_DAVIPLATA_CONFIG, COMPROBANTE_BC_NQ_T_CONFIG,
    COMPROBANTE_BC_QR_CONFIG, COMPROBANTE_NEQUI_BC_CONFIG,
    COMPROBANTE_NEQUI_AHORROS_CONFIG, MOVIMIENTO_BC_AHORROS_CONFIG,
    MOVIMIENTO_BC_CORRIENTE_CONFIG, MOVIMIENTO_BC_NEQUI_CONFIG,
    MOVIMIENTO_BC_QR_CONFIG
)
from utils import (
    generar_comprobante, generar_comprobante_nuevo, generar_comprobante_anulado,
    enmascarar_nombre, generar_comprobante_ahorros, generar_comprobante_daviplata,
    generar_comprobante_bc_nq_t, generar_comprobante_bc_qr,
    generar_comprobante_nequi_bc, generar_comprobante_nequi_ahorros,
    generar_movimiento_bancolombia
)
from auth_system import AuthSystem
import asyncio
import logging
import traceback
from datetime import datetime, date, timedelta
import pytz
import json
import urllib.request
import urllib.parse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────
BOT_TOKEN         = "8069968534:AAFDKtsi4oIbW-t5Bn-UcR_Sf4DXyWbF9E0"
ADMIN_ID          = 7422843477
ALLOWED_GROUP     = -1003512376124
REQUIRED_GROUP_ID = -1003512376124
GROUP_LINK        = "https://t.me/nequixxx"

auth_system = AuthSystem(ADMIN_ID, ALLOWED_GROUP)
user_data_store = {}
fecha_manual_mode = {}
referencia_manual_mode = {}
REFERENCIAS_FILE = "referencias.json"
VENCIMIENTOS_FILE = "vencimientos.json"


# ══════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════════════════════════════════════

def limpiar_valor(text):
    import unicodedata
    text = unicodedata.normalize('NFKC', text)
    return (text.strip()
                .replace(".", "").replace(",", "")
                .replace(" ", "").replace("$", "")
                .replace("\xa0", "").replace("\u200b", ""))

def fmt_valor(v):
    return f"${abs(int(v)):,}".replace(",", ".")

def limpiar_usuario(user_id):
    user_data_store.pop(user_id, None)
    fecha_manual_mode.pop(user_id, None)
    referencia_manual_mode.pop(user_id, None)

def parsear_qr_emv(contenido):
    try:
        pos = 0; datos = {}
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
            sub = datos["26"]; sub_pos = 0
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


# ══════════════════════════════════════════════════════════════════════════
# VENCIMIENTOS
# ══════════════════════════════════════════════════════════════════════════

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
        "nombre": nombre, "fecha_vence": fecha_vence,
        "dias": dias, "aviso3_enviado": False, "expirado_enviado": False
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
                    text=f"⚠️ *Aviso*\n\nHola {info['nombre']}, tu acceso vence en *3 días* ({fecha_vence.strftime('%d/%m/%Y')}).\n\nRenueva con un admin 👑 @nequixxx",
                    parse_mode="Markdown"
                )
                info["aviso3_enviado"] = True
                actualizar = True
            except Exception as e:
                logging.error(f"[VENC] {uid}: {e}")
        elif dias_restantes <= 0 and not info.get("expirado_enviado"):
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🔴 *Acceso Expirado*\n\nHola {info['nombre']}, tu acceso expiró.\nContacta al admin:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👑 ADM", url="tg://user?id=7422843477")],
                        [InlineKeyboardButton("📢 Grupo", url=GROUP_LINK)]
                    ])
                )
                auth_system.remove_user(uid)
                info["expirado_enviado"] = True
                actualizar = True
            except Exception as e:
                logging.error(f"[VENC] {uid}: {e}")
    if actualizar:
        guardar_vencimientos(vencimientos)


# ══════════════════════════════════════════════════════════════════════════
# REFERENCIAS
# ══════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════
# TECLADOS
# ══════════════════════════════════════════════════════════════════════════

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 ¿Necesitas acceso?", callback_data="apk_precios")],
        [InlineKeyboardButton("👑 ADM", url="tg://user?id=7422843477")],
        [InlineKeyboardButton("📢 Grupo", url=GROUP_LINK)]
    ])

def confirm_keyboard(user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirmar", callback_data=f"gen_ok_{user_id}"),
         InlineKeyboardButton("❌ Cancelar", callback_data=f"gen_no_{user_id}")]
    ])

def main_keyboard():
    keyboard = [
        [KeyboardButton("Nequi"),           KeyboardButton("Nequi QR")],
        [KeyboardButton("Daviplata"),        KeyboardButton("Bre B")],
        [KeyboardButton("Ahorros"),          KeyboardButton("Corriente")],
        [KeyboardButton("BC a NQ"),          KeyboardButton("BC QR")],
        [KeyboardButton("Nequi Corriente"),  KeyboardButton("Nequi Ahorros")],
        [KeyboardButton("Anulado")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


# ══════════════════════════════════════════════════════════════════════════
# VERIFICACIÓN DE ACCESO (helper reutilizable)
# ══════════════════════════════════════════════════════════════════════════

async def verificar_acceso(update: Update, context) -> bool:
    """Retorna True si el usuario puede usar el bot, False si no."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if auth_system.is_banned(user_id):
        await update.message.reply_text("🚫 Estás baneado.")
        return False

    if auth_system.is_admin(user_id):
        return True

    if auth_system.gratis_mode or auth_system.can_use_bot(user_id, chat_id):
        return True

    await update.message.reply_text(
        "🔴 *Bot en Modo OFF*\n\n💰 Contacta a un admin para obtener acceso.",
        parse_mode='Markdown',
        reply_markup=admin_keyboard()
    )
    return False


# ══════════════════════════════════════════════════════════════════════════
# GENERACIÓN
# ══════════════════════════════════════════════════════════════════════════

async def generar_y_enviar_a_chat(chat_id, context, fn, data, config, caption=" "):
    out = None
    try:
        out = fn(data, config)
        if not out or not os.path.exists(out):
            raise ValueError(f"No se generó archivo: {out}")
        for intento in range(2):
            try:
                with open(out, "rb") as f:
                    await context.bot.send_document(chat_id=chat_id, document=f, caption=caption)
                return True
            except Exception as e:
                if "TimedOut" in str(e) and intento == 0:
                    await asyncio.sleep(3)
                    continue
                raise
    except Exception:
        tb = traceback.format_exc()
        logging.error(f"[ERROR generacion] {tb}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Error generando comprobante:\n<code>{tb[-600:]}</code>",
            parse_mode="HTML"
        )
        return False
    finally:
        if out and os.path.exists(out):
            try:
                os.remove(out)
            except:
                pass


def construir_resumen(data, tipo):
    tipo_nombres = {
        "comprobante1":          "🟣 Nequi",
        "comprobante4":          "💸 Transfiya",
        "comprobante_qr":        "📱 Nequi QR",
        "comprobante_nuevo":     "🔑 Bre B",
        "comprobante_anulado":   "❌ Anulado",
        "comprobante_ahorros":   "🏦 Ahorros BC",
        "comprobante_corriente": "🏦 Corriente BC",
        "comprobante_daviplata": "🔴 Daviplata",
        "comprobante_bc_nq_t":   "🏦➡️🟣 BC a NQ",
        "comprobante_bc_qr":     "🏦 BC QR",
        "comprobante_nequi_bc":  "🟣➡️🏦 Nequi Corriente",
        "comprobante_nequi_ahorros": "🟣➡️🏦 Nequi Ahorros",
    }
    v = data.get("valor", 0)
    lineas = [
        "📋 *Confirma los datos:*",
        "━━━━━━━━━━━━━━━━━",
        f"📌 {tipo_nombres.get(tipo, tipo)}"
    ]
    if "nombre"        in data: lineas.append(f"👤 Nombre: {data['nombre']}")
    if "telefono"      in data: lineas.append(f"📱 Teléfono: {data['telefono']}")
    if "numero_cuenta" in data: lineas.append(f"🏦 Cuenta: {data['numero_cuenta']}")
    if "descripcion_qr" in data: lineas.append(f"📲 QR: {data['descripcion_qr']}")
    if "llave"         in data: lineas.append(f"🔑 Llave: {data['llave']}")
    if "banco"         in data: lineas.append(f"🏛️ Banco: {data['banco']}")
    if "numero_envia"  in data: lineas.append(f"📞 Núm. envía: {data['numero_envia']}")
    if "recibe"        in data: lineas.append(f"📤 Cuenta envía: ****{data['recibe']}")
    if "envia"         in data: lineas.append(f"📥 Cuenta recibe: ****{data['envia']}")
    lineas.append(f"💰 Valor: {fmt_valor(v)}")
    lineas.append(f"📅 Fecha: {'Manual: ' + data['fecha_manual'] if data.get('fecha_manual') else 'Automática'}")
    lineas.append(f"🔢 Ref: {'Manual: ' + data['referencia_manual'] if data.get('referencia_manual') else 'Automática'}")
    lineas.append("━━━━━━━━━━━━━━━━━\n¿Está correcto?")
    return "\n".join(lineas)


async def mostrar_confirmacion(update, user_id, data, tipo):
    data["_pendiente"] = True
    await update.message.reply_text(
        construir_resumen(data, tipo),
        parse_mode="Markdown",
        reply_markup=confirm_keyboard(user_id)
    )


async def ejecutar_generacion(chat_id, context, user_id):
    if user_id not in user_data_store:
        await context.bot.send_message(chat_id=chat_id, text="❌ Sesión expirada. Usa /comprobante")
        return
    data = user_data_store[user_id]
    tipo = data["tipo"]
    v    = data.get("valor", 0)

    await context.bot.send_message(chat_id=chat_id, text="⏳ Generando comprobante...")
    ok = False

    if tipo == "comprobante1":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante, data, COMPROBANTE1_CONFIG)
        if ok:
            dm = data.copy()
            dm["nombre"] = data["nombre"].upper()
            dm["valor"]  = -abs(v)
            await generar_y_enviar_a_chat(chat_id, context, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO_CONFIG)

    elif tipo == "comprobante4":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante, data, COMPROBANTE4_CONFIG)
        if ok:
            dm2 = {"telefono": data["telefono"], "valor": -abs(v), "nombre": data["telefono"]}
            await generar_y_enviar_a_chat(chat_id, context, generar_comprobante, dm2, COMPROBANTE_MOVIMIENTO2_CONFIG)

    elif tipo == "comprobante_qr":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante, data, COMPROBANTE_QR_CONFIG)
        if ok:
            dm = {"nombre": data["nombre"].upper(), "valor": -abs(v)}
            await generar_y_enviar_a_chat(chat_id, context, generar_comprobante, dm, COMPROBANTE_MOVIMIENTO3_CONFIG)

    elif tipo == "comprobante_anulado":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante_anulado, data, COMPROBANTE_ANULADO_CONFIG, "ANULADO")

    elif tipo == "comprobante_ahorros":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante_ahorros, data, COMPROBANTE_AHORROS_CONFIG, "Ahorros")

    elif tipo == "comprobante_corriente":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante_ahorros, data, COMPROBANTE_AHORROS2_CONFIG, "Corriente")

    elif tipo == "comprobante_daviplata":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante_daviplata, data, COMPROBANTE_DAVIPLATA_CONFIG, "Daviplata")

    elif tipo == "comprobante_bc_nq_t":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante_bc_nq_t, data, COMPROBANTE_BC_NQ_T_CONFIG, "BC a NQ")

    elif tipo == "comprobante_bc_qr":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante_bc_qr, data, COMPROBANTE_BC_QR_CONFIG, "BC QR")

    elif tipo == "comprobante_nequi_bc":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante_nequi_bc, data, COMPROBANTE_NEQUI_BC_CONFIG, "Nequi Corriente")

    elif tipo == "comprobante_nequi_ahorros":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante_nequi_ahorros, data, COMPROBANTE_NEQUI_AHORROS_CONFIG, "Nequi Ahorros")

    elif tipo == "comprobante_nuevo":
        ok = await generar_y_enviar_a_chat(chat_id, context, generar_comprobante_nuevo, data, COMPROBANTE_NUEVO_CONFIG)
        if ok:
            await asyncio.sleep(1.5)
            dm = {"nombre": enmascarar_nombre(data["nombre"]), "valor": -abs(float(v))}
            await generar_y_enviar_a_chat(chat_id, context, generar_comprobante, dm, MVKEY_CONFIG)

    if ok:
        await context.bot.send_message(
            chat_id=chat_id,
            text="✅ *Comprobante generado con éxito*\n\nUsa /comprobante para generar otro",
            parse_mode='Markdown',
            reply_markup=main_keyboard()
        )
    limpiar_usuario(user_id)


# ══════════════════════════════════════════════════════════════════════════
# CALLBACK CONFIRMACIÓN
# ══════════════════════════════════════════════════════════════════════════

async def confirmar_generacion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split("_")
    action = parts[1]
    user_id = int(parts[2])

    if query.from_user.id != user_id:
        await query.answer("❌ Esta confirmación no es tuya.", show_alert=True)
        return

    if action == "no":
        limpiar_usuario(user_id)
        await query.edit_message_text("❌ Cancelado.\n\nUsa /comprobante para empezar de nuevo.")
        return

    await query.edit_message_text("✅ Confirmado, procesando...")
    await ejecutar_generacion(query.message.chat_id, context, user_id)


# ══════════════════════════════════════════════════════════════════════════
# COMANDOS PRINCIPALES
# ══════════════════════════════════════════════════════════════════════════

async def start_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bienvenido al generador de comprobantes\n\n"
        "/comprobante - Iniciar\n"
        "/fechas - Activar fechas manuales\n"
        "/refes - Activar referencias manuales\n"
        "/horarios - Horarios gratis\n"
        "/precios - Planes premium",
        reply_markup=admin_keyboard()
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Solo responder en grupo permitido o en privado
    if update.effective_chat.type in ("group", "supergroup") and chat_id != ALLOWED_GROUP:
        return

    if not await verificar_acceso(update, context):
        return

    await update.message.reply_text(
        "✅ Selecciona el tipo de comprobante:",
        reply_markup=main_keyboard()
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not await verificar_acceso(update, context):
        return

    # Si ya tiene una sesión activa, ignorar foto
    if user_id in user_data_store:
        await update.message.reply_text("⏳ Ya tienes una operación en curso. Usa /cancelar para reiniciar.")
        return

    await update.message.reply_text("🔍 Leyendo QR...")
    try:
        import cv2
        import numpy as np
        photo     = update.message.photo[-1]
        file      = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        nparr     = np.frombuffer(file_bytes, np.uint8)
        img       = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        detector  = cv2.QRCodeDetector()
        contenido, _, _ = detector.detectAndDecode(img)
        if not contenido:
            await update.message.reply_text("❌ No se pudo leer el QR. Intenta con otra imagen.")
            return
        nombre_negocio = extraer_nombre_qr(contenido)[:30].strip()
        user_data_store[user_id] = {"step": "qr_monto", "tipo": "comprobante_qr", "nombre": nombre_negocio}
        await update.message.reply_text(
            f"✅ *QR leído*\n\n🏪 *Negocio:* {nombre_negocio}\n\n💰 ¿Cuánto es el monto?",
            parse_mode="Markdown"
        )
    except ImportError:
        await update.message.reply_text("❌ cv2 no instalado. Usa el flujo manual.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error leyendo QR: {e}")


# ══════════════════════════════════════════════════════════════════════════
# MANEJADOR PRINCIPAL DE MENSAJES
# ══════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text    = update.message.text.strip()

    # Ignorar mensajes de otros grupos
    if update.effective_chat.type in ("group", "supergroup") and chat_id != ALLOWED_GROUP:
        return

    if auth_system.is_banned(user_id):
        await update.message.reply_text("🚫 Estás baneado.")
        return

    button_mapping = {
        "Nequi":            "comprobante1",
        "Transfiya":        "comprobante4",
        "Daviplata":        "comprobante_daviplata",
        "Nequi QR":         "comprobante_qr",
        "Bre B":            "comprobante_nuevo",
        "Anulado":          "comprobante_anulado",
        "Ahorros":          "comprobante_ahorros",
        "Corriente":        "comprobante_corriente",
        "BC a NQ":          "comprobante_bc_nq_t",
        "BC QR":            "comprobante_bc_qr",
        "Nequi Corriente":  "comprobante_nequi_bc",
        "Nequi Ahorros":    "comprobante_nequi_ahorros",
    }

    # ── Botones del menú ──────────────────────────────────────────────────
    if text in button_mapping:
        if not await verificar_acceso(update, context):
            return
        limpiar_usuario(user_id)
        tipo = button_mapping[text]
        user_data_store[user_id] = {"step": 0, "tipo": tipo}
        prompts = {
            "comprobante1":          "👤 ¿Nombre del destinatario?",
            "comprobante4":          "📱 ¿Número a transferir? (10 dígitos)",
            "comprobante_qr":        "🏪 ¿Nombre del negocio?",
            "comprobante_nuevo":     "👤 ¿Nombre del destinatario?",
            "comprobante_anulado":   "👤 ¿Nombre?",
            "comprobante_corriente": "👤 ¿Nombre?",
            "comprobante_daviplata": "👤 ¿Nombre de quien envía?",
            "comprobante_ahorros":   "👤 ¿Nombre?",
            "comprobante_bc_nq_t":   "📱 ¿Número de teléfono? (10 dígitos)",
            "comprobante_bc_qr":     "📲 ¿Descripción del QR?",
            "comprobante_nequi_bc":  "👤 ¿Nombre?",
            "comprobante_nequi_ahorros": "👤 ¿Nombre?",
        }
        await update.message.reply_text(prompts.get(tipo, "Ingresa los datos:"))
        return

    # ── QR por foto: esperando monto ──────────────────────────────────────
    if user_id in user_data_store and user_data_store[user_id].get("step") == "qr_monto":
        data   = user_data_store[user_id]
        limpio = limpiar_valor(text)
        if not limpio.replace("-", "", 1).isdigit():
            await update.message.reply_text("❌ Ingresa un valor numérico. Ejemplo: 50000")
            return
        valor = int(limpio)
        if valor < 1000:
            await update.message.reply_text("❌ El mínimo es $1,000")
            return
        data["valor"] = valor
        await mostrar_confirmacion(update, user_id, data, data["tipo"])
        return

    # ── Sin sesión activa ─────────────────────────────────────────────────
    if user_id not in user_data_store:
        return

    data = user_data_store[user_id]
    tipo = data["tipo"]
    step = data["step"]

    # Esperando confirmación de botones
    if data.get("_pendiente"):
        await update.message.reply_text("⏳ Por favor confirma o cancela la operación de arriba 👆")
        return

    # ══════════════════════════════════════════════════════════════════════
    # FLUJOS POR TIPO
    # ══════════════════════════════════════════════════════════════════════

    # ── AGREGAR USUARIO (admin) ───────────────────────────────────────────
    if tipo == "agregar_usuario":
        if step == 0:
            if not text.strip().isdigit():
                await update.message.reply_text("❌ El ID debe ser numérico.\nEjemplo: 7422843477\n\n/cancelar para salir")
                return
            data["target_user_id"] = int(text.strip())
            data["step"] = 1
            await update.message.reply_text("📝 Nombre del usuario:")
        elif step == 1:
            data["nombre"] = text
            data["step"] = 2
            await update.message.reply_text("📅 ¿Cuántos días de acceso? (Ejemplo: 30)")
        elif step == 2:
            if not text.isdigit():
                await update.message.reply_text("❌ Ingresa un número de días válido")
                return
            dias = int(text)
            try:
                auth_system.add_user(data["target_user_id"], data["nombre"])
                fecha_vence = agregar_vencimiento(data["target_user_id"], data["nombre"], dias)
                now = datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S")
                await update.message.reply_text(
                    f"✅ *Usuario Agregado*\n\n"
                    f"👤 ID: `{data['target_user_id']}`\n"
                    f"📝 Nombre: {data['nombre']}\n"
                    f"📅 Vence: {fecha_vence}\n"
                    f"⏳ Días: {dias}\n"
                    f"🕐 {now}",
                    parse_mode='Markdown'
                )
                try:
                    await context.bot.send_message(
                        chat_id=data["target_user_id"],
                        text=f"✅ *¡Acceso Activado!*\n\n"
                             f"Hola {data['nombre']}!\n"
                             f"📅 Vence: *{fecha_vence}*\n"
                             f"⏳ Duración: *{dias} días*\n\n"
                             f"Usa /comprobante para empezar.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"No se notificó a {data['target_user_id']}: {e}")
                if user_id != ADMIN_ID:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"🔔 *Nuevo usuario agregado*\nID: `{data['target_user_id']}`\nNombre: {data['nombre']}\nVence: {fecha_vence}",
                        parse_mode='Markdown'
                    )
                limpiar_usuario(user_id)
            except Exception as e:
                await update.message.reply_text(f"❌ Error al agregar usuario: {e}")
                limpiar_usuario(user_id)
        return

    # ── NEQUI ─────────────────────────────────────────────────────────────
    if tipo == "comprobante1":
        if step == 0:
            data["nombre"] = text
            data["step"]   = 1
            await update.message.reply_text("📱 Número de teléfono (10 dígitos, empieza en 3):")
        elif step == 1:
            tel = text.strip().replace(" ", "").replace("-", "")
            if tel.startswith("+57"):   tel = tel[3:]
            elif tel.startswith("57") and len(tel) == 12: tel = tel[2:]
            if not tel.isdigit() or len(tel) != 10 or not tel.startswith("3"):
                await update.message.reply_text("❌ Número inválido. Debe tener 10 dígitos y empezar en 3.\nEjemplo: 3001234567\n\n/cancelar para reiniciar")
                return
            data["telefono"] = tel
            data["step"]     = 2
            await update.message.reply_text("💰 Valor a transferir:")
        elif step == 2:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números. Ejemplo: 50000")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            if referencia_manual_mode.get(user_id):
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia:")
                return
            if fecha_manual_mode.get(user_id):
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha (Ej: 10/03/2026 12:00):")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 3:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha (Ej: 10/03/2026 12:00):")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 11:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── TRANSFIYA ─────────────────────────────────────────────────────────
    elif tipo == "comprobante4":
        if step == 0:
            tel = text.strip().replace(" ", "").replace("-", "")
            if not tel.isdigit() or len(tel) != 10 or not tel.startswith('3'):
                await update.message.reply_text("❌ Número inválido. 10 dígitos, empieza en 3.\n/cancelar para reiniciar")
                return
            data["telefono"] = tel
            data["step"]     = 1
            await update.message.reply_text("💰 Valor a transferir:")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            if referencia_manual_mode.get(user_id):
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia:")
                return
            if fecha_manual_mode.get(user_id):
                data["step"] = 2
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 2:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 11:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── NEQUI QR ──────────────────────────────────────────────────────────
    elif tipo == "comprobante_qr":
        if step == 0:
            data["nombre"] = text
            data["step"]   = 1
            await update.message.reply_text("💰 Valor:")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            if referencia_manual_mode.get(user_id):
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia:")
                return
            if fecha_manual_mode.get(user_id):
                data["step"] = 2
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 2:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 11:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── ANULADO ───────────────────────────────────────────────────────────
    elif tipo == "comprobante_anulado":
        if step == 0:
            data["nombre"] = text
            data["step"]   = 1
            await update.message.reply_text("💰 Valor:")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            if fecha_manual_mode.get(user_id):
                data["step"] = 2
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 2:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── AHORROS ───────────────────────────────────────────────────────────
    elif tipo == "comprobante_ahorros":
        if step == 0:
            data["nombre"] = text
            data["step"]   = 1
            await update.message.reply_text("🏦 Número de cuenta (11 dígitos):")
        elif step == 1:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text("❌ La cuenta debe tener exactamente 11 dígitos")
                return
            data["numero_cuenta"] = text
            data["step"]          = 2
            await update.message.reply_text("💰 Valor:")
        elif step == 2:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            if fecha_manual_mode.get(user_id):
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 3:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── CORRIENTE ─────────────────────────────────────────────────────────
    elif tipo == "comprobante_corriente":
        if step == 0:
            data["nombre"] = text
            data["step"]   = 1
            await update.message.reply_text("🏦 Número de cuenta (11 dígitos):")
        elif step == 1:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text("❌ La cuenta debe tener exactamente 11 dígitos")
                return
            data["numero_cuenta"] = text
            data["step"]          = 2
            await update.message.reply_text("💰 Valor:")
        elif step == 2:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            if fecha_manual_mode.get(user_id):
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 3:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── DAVIPLATA ─────────────────────────────────────────────────────────
    elif tipo == "comprobante_daviplata":
        if step == 0:
            data["nombre"] = text
            data["step"]   = 1
            await update.message.reply_text("💰 Valor:")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            data["step"]  = 2
            await update.message.reply_text("📤 Últimos 4 dígitos de la cuenta que ENVÍA:")
        elif step == 2:
            if not text.isdigit() or len(text) != 4:
                await update.message.reply_text("❌ Ingresa exactamente 4 dígitos")
                return
            data["recibe"] = text
            data["step"]   = 3
            await update.message.reply_text("📥 Últimos 4 dígitos de la cuenta que RECIBE:")
        elif step == 3:
            if not text.isdigit() or len(text) != 4:
                await update.message.reply_text("❌ Ingresa exactamente 4 dígitos")
                return
            data["envia"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 4
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 4:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── BC A NQ ───────────────────────────────────────────────────────────
    elif tipo == "comprobante_bc_nq_t":
        if step == 0:
            tel = text.strip().replace(" ", "").replace("-", "")
            if not tel.isdigit() or len(tel) != 10 or not tel.startswith('3'):
                await update.message.reply_text("❌ Número inválido. 10 dígitos, empieza en 3.\n/cancelar para reiniciar")
                return
            data["telefono"] = tel
            data["step"]     = 1
            await update.message.reply_text("💰 Valor:")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            if fecha_manual_mode.get(user_id):
                data["step"] = 2
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 2:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── BC QR ─────────────────────────────────────────────────────────────
    elif tipo == "comprobante_bc_qr":
        if step == 0:
            data["descripcion_qr"] = text
            data["step"]           = 1
            await update.message.reply_text("💰 Valor:")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            data["step"]  = 2
            await update.message.reply_text("👤 Nombre del titular:")
        elif step == 2:
            data["nombre"] = text
            data["step"]   = 3
            await update.message.reply_text("🏦 Número de cuenta:")
        elif step == 3:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) < 8:
                await update.message.reply_text("❌ Número de cuenta inválido")
                return
            data["numero_cuenta"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 4
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 4:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── NEQUI CORRIENTE ───────────────────────────────────────────────────
    elif tipo == "comprobante_nequi_bc":
        if step == 0:
            data["nombre"] = text
            data["step"]   = 1
            await update.message.reply_text("💰 Valor:")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            data["step"]  = 2
            await update.message.reply_text("🏦 Número de cuenta (11 dígitos):")
        elif step == 2:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text("❌ La cuenta debe tener exactamente 11 dígitos")
                return
            data["numero_cuenta"] = text
            if referencia_manual_mode.get(user_id):
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia:")
                return
            if fecha_manual_mode.get(user_id):
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 3:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 11:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── NEQUI AHORROS ─────────────────────────────────────────────────────
    elif tipo == "comprobante_nequi_ahorros":
        if step == 0:
            data["nombre"] = text
            data["step"]   = 1
            await update.message.reply_text("💰 Valor:")
        elif step == 1:
            limpio = limpiar_valor(text)
            if not limpio.replace("-", "", 1).isdigit():
                await update.message.reply_text("❌ Ingresa solo números")
                return
            v = int(limpio)
            if v < 1000:
                await update.message.reply_text("❌ El mínimo es $1,000")
                return
            data["valor"] = v
            data["step"]  = 2
            await update.message.reply_text("🏦 Número de cuenta (11 dígitos):")
        elif step == 2:
            digitos = "".join(ch for ch in text if ch.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text("❌ La cuenta debe tener exactamente 11 dígitos")
                return
            data["numero_cuenta"] = text
            if referencia_manual_mode.get(user_id):
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia:")
                return
            if fecha_manual_mode.get(user_id):
                data["step"] = 3
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 3:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 11:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)

    # ── BRE B ─────────────────────────────────────────────────────────────
    elif tipo == "comprobante_nuevo":
        if step == 0:
            data["nombre"] = text
            data["step"]   = 1
            await update.message.reply_text("💰 Valor:")
        elif step == 1:
            try:
                limpio = limpiar_valor(text)
                v = float(limpio)
                if v < 1000:
                    await update.message.reply_text("❌ El mínimo es $1,000")
                    return
                data["valor"] = v
            except:
                await update.message.reply_text("❌ Ingresa solo números")
                return
            data["step"] = 2
            await update.message.reply_text("🔑 Llave (alias/número):")
        elif step == 2:
            data["llave"] = text
            data["step"]  = 3
            await update.message.reply_text("🏛️ Banco:")
        elif step == 3:
            data["banco"] = text
            data["step"]  = 4
            await update.message.reply_text("📞 Número de quien envía (10 dígitos):")
        elif step == 4:
            tel = text.strip().replace(" ", "").replace("-", "")
            if not tel.isdigit() or len(tel) != 10 or not tel.startswith('3'):
                await update.message.reply_text("❌ Número inválido. 10 dígitos, empieza en 3.\n/cancelar para reiniciar")
                return
            data["numero_envia"] = tel
            if referencia_manual_mode.get(user_id):
                data["step"] = 10
                await update.message.reply_text("🔢 Ingresa la referencia:")
                return
            if fecha_manual_mode.get(user_id):
                data["step"] = 5
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 5:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11
                await update.message.reply_text("📅 Ingresa la fecha:")
                return
            await mostrar_confirmacion(update, user_id, data, tipo)
        elif step == 11:
            data["fecha_manual"] = text
            await mostrar_confirmacion(update, user_id, data, tipo)


# ══════════════════════════════════════════════════════════════════════════
# COMANDOS ADMIN
# ══════════════════════════════════════════════════════════════════════════

async def gratis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins.")
        return
    auth_system.set_gratis_mode(True)
    await update.message.reply_text("✅ Modo GRATIS activado.")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins.")
        return
    auth_system.set_gratis_mode(False)
    await update.message.reply_text("🔴 Modo OFF activado.")

async def agregar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("❌ Solo admins.")
        return
    user_data_store[user_id] = {
        "step": 0,
        "tipo": "agregar_usuario",
        "admin_name": update.effective_user.first_name or "Admin"
    }
    await update.message.reply_text("👤 Ingresa el ID del usuario:")

async def eliminar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins.")
        return
    if not context.args:
        await update.message.reply_text("Uso: /eliminar <id>")
        return
    try:
        tid = int(context.args[0])
        auth_system.remove_user(tid)
        eliminar_vencimiento(tid)
        await update.message.reply_text(f"✅ Usuario {tid} eliminado.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins.")
        return
    if not context.args:
        await update.message.reply_text("Uso: /ban <id>")
        return
    try:
        auth_system.ban_user(int(context.args[0]))
        await update.message.reply_text(f"🚫 {context.args[0]} baneado.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins.")
        return
    if not context.args:
        await update.message.reply_text("Uso: /unban <id>")
        return
    try:
        auth_system.unban_user(int(context.args[0]))
        await update.message.reply_text(f"✅ {context.args[0]} desbaneado.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins.")
        return
    s = auth_system.get_stats()
    await update.message.reply_text(
        f"📊 *Estadísticas*\n\n"
        f"👥 Autorizados: {s['total_authorized']}\n"
        f"🚫 Baneados: {s['total_banned']}\n"
        f"🛡️ Admins: {s['total_admins']}\n"
        f"🆓 Modo Gratis: {'✅ Sí' if s['gratis_mode'] else '❌ No'}",
        parse_mode='Markdown'
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins.")
        return
    if not context.args:
        await update.message.reply_text("Uso: /admin <id>")
        return
    try:
        auth_system.add_admin(int(context.args[0]))
        await update.message.reply_text(f"✅ {context.args[0]} ahora es admin.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def unadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins.")
        return
    if not context.args:
        await update.message.reply_text("Uso: /unadmin <id>")
        return
    try:
        auth_system.remove_admin(int(context.args[0]))
        await update.message.reply_text(f"✅ {context.args[0]} ya no es admin.")
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def cancelar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data_store:
        limpiar_usuario(user_id)
        await update.message.reply_text("✅ Operación cancelada.", reply_markup=main_keyboard())
    else:
        await update.message.reply_text("No tienes operaciones activas. Usa /comprobante.")

async def fechas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if auth_system.is_banned(user_id):
        return
    if fecha_manual_mode.get(user_id):
        fecha_manual_mode[user_id] = False
        await update.message.reply_text("📅 Fecha *Automática* activada.", parse_mode='Markdown')
    else:
        fecha_manual_mode[user_id] = True
        await update.message.reply_text("📅 Fecha *Manual* activada.", parse_mode='Markdown')

async def refes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if auth_system.is_banned(user_id):
        return
    if referencia_manual_mode.get(user_id):
        referencia_manual_mode[user_id] = False
        await update.message.reply_text("🔢 Referencia *Automática* activada.", parse_mode='Markdown')
    else:
        referencia_manual_mode[user_id] = True
        await update.message.reply_text("🔢 Referencia *Manual* activada.", parse_mode='Markdown')

async def precios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💵 *PRECIOS*\n\n"
        "• 1 Mes:   $25,000\n"
        "• 2 Meses: $45,000\n"
        "• 3 Meses: $55,000\n\n"
        "📞 Contacta al admin:",
        parse_mode='Markdown',
        reply_markup=admin_keyboard()
    )

async def horarios_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕰️ *HORARIOS GRATIS*\n\n"
        "🌅 9:00 AM - 11:00 AM\n"
        "🌞 12:00 PM - 3:00 PM\n\n"
        "👑 VIP: 24/7\n\n"
        "💎 /precios para planes premium",
        parse_mode='Markdown'
    )

async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_main_admin(user_id):
        await update.message.reply_text("⛔ Solo el ADM principal.")
        return
    s = auth_system.get_stats()
    texto = (
        f"👑 *PANEL ADMINISTRADOR*\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Modo: {'🟢 GRATIS' if s['gratis_mode'] else '🔴 OFF'}\n"
        f"👥 Autorizados: {s['total_authorized']}\n"
        f"🚫 Baneados: {s['total_banned']}\n"
        f"🛡️ Admins: {s['total_admins']}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⚙️ *COMANDOS:*\n\n"
        f"🆓 /gratis  |  🔒 /off\n"
        f"➕ /agregar  |  ➖ /eliminar [ID]\n"
        f"🚫 /ban [ID]  |  ✅ /unban [ID]\n"
        f"🛡️ /admin [ID]  |  ❌ /unadmin [ID]\n"
        f"📊 /stats\n"
        f"━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 GRATIS", callback_data="panel_gratis"),
         InlineKeyboardButton("🔴 OFF",    callback_data="panel_off")],
        [InlineKeyboardButton("📊 Stats",  callback_data="panel_stats")]
    ])
    await update.message.reply_text(texto, parse_mode='Markdown', reply_markup=kb)

async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not auth_system.is_main_admin(query.from_user.id):
        await query.answer("⛔ Sin permisos.", show_alert=True)
        return
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
            f"📊 *Estadísticas*\n"
            f"Modo: {'🟢 Gratis' if s['gratis_mode'] else '🔴 OFF'}\n"
            f"Autorizados: {s['total_authorized']}\n"
            f"Baneados: {s['total_banned']}",
            parse_mode='Markdown'
        )

async def apk_precios_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "💵 *PRECIOS*\n\n"
        "• 1 Mes:   $25,000\n"
        "• 2 Meses: $45,000\n"
        "• 3 Meses: $55,000\n\n"
        "📞 Contacta:",
        parse_mode='Markdown',
        reply_markup=admin_keyboard()
    )

async def refe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("❌ Solo admins.")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("❌ Responde a una foto con /refe.")
        return
    try:
        photo      = update.message.reply_to_message.photo[-1]
        referencias = cargar_referencias()
        nueva = {
            "file_id":     photo.file_id,
            "guardado_por": update.effective_user.first_name or "Admin",
            "user_id":     user_id,
            "fecha":       datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S"),
            "numero":      len(referencias) + 1
        }
        referencias.append(nueva)
        guardar_referencias(referencias)
        await update.message.reply_text(f"✅ Referencia #{nueva['numero']} guardada.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def referencias_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins.")
        return
    referencias = cargar_referencias()
    if not referencias:
        await update.message.reply_text("📭 No hay referencias guardadas.")
        return
    await enviar_referencias_paginadas(update, context, referencias, 0)

async def enviar_referencias_paginadas(update_or_query, context, referencias, offset):
    if hasattr(update_or_query, 'callback_query') and update_or_query.callback_query:
        chat_id = update_or_query.callback_query.message.chat_id
    else:
        chat_id = update_or_query.effective_chat.id
    total       = len(referencias)
    fin         = min(offset + 5, total)
    message_ids = []
    for ref in referencias[offset:fin]:
        caption = f"📸 *#{ref['numero']}* — {ref['guardado_por']} — {ref['fecha']}"
        try:
            file      = await context.bot.get_file(ref['file_id'])
            file_path = await file.download_to_drive()
            with open(file_path, 'rb') as pf:
                msg = await context.bot.send_document(
                    chat_id=chat_id, document=pf,
                    caption=caption, parse_mode='Markdown',
                    filename=f"ref_{ref['numero']}.jpg"
                )
            message_ids.append(msg.message_id)
            try: os.remove(file_path)
            except: pass
        except Exception as e:
            msg = await context.bot.send_message(chat_id=chat_id, text=f"❌ Error ref #{ref['numero']}: {e}")
            message_ids.append(msg.message_id)
    if fin < total:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"📥 Ver más ({fin+1}-{min(fin+5, total)} de {total})",
                callback_data=f"ref_next_{fin}_{','.join(map(str, message_ids))}"
            )
        ]])
        await context.bot.send_message(chat_id=chat_id, text="👇 Más referencias:", reply_markup=kb)
    else:
        await context.bot.send_message(chat_id=chat_id, text="✅ Todas las referencias mostradas.")

async def referencias_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split('_')
    offset = int(parts[2])
    for mid in [int(x) for x in parts[3].split(',')]:
        try: await context.bot.delete_message(chat_id=query.message.chat_id, message_id=mid)
        except: pass
    try: await query.message.delete()
    except: pass
    await enviar_referencias_paginadas(update, context, cargar_referencias(), offset)


# ══════════════════════════════════════════════════════════════════════════
# MAIN — con manejo robusto del error Conflict
# ══════════════════════════════════════════════════════════════════════════

def main():
    import time
    from telegram.request import HTTPXRequest

    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=60,
        write_timeout=60,
        connect_timeout=30,
        pool_timeout=30
    )

    app = Application.builder().token(BOT_TOKEN).request(request).build()

    # Job de vencimientos cada 12 horas
    app.job_queue.run_repeating(verificar_vencimientos, interval=43200, first=60)

    # Comandos
    app.add_handler(CommandHandler("comprobante",  start))
    app.add_handler(CommandHandler("start",        start_redirect))
    app.add_handler(CommandHandler("fechas",       fechas_command))
    app.add_handler(CommandHandler("refes",        refes_command))
    app.add_handler(CommandHandler("precios",      precios_command))
    app.add_handler(CommandHandler("horarios",     horarios_command))
    app.add_handler(CommandHandler("gratis",       gratis_command))
    app.add_handler(CommandHandler("off",          off_command))
    app.add_handler(CommandHandler("agregar",      agregar_command))
    app.add_handler(CommandHandler("eliminar",     eliminar_command))
    app.add_handler(CommandHandler("stats",        stats_command))
    app.add_handler(CommandHandler("ban",          ban_command))
    app.add_handler(CommandHandler("unban",        unban_command))
    app.add_handler(CommandHandler("cancelar",     cancelar_command))
    app.add_handler(CommandHandler("refe",         refe_command))
    app.add_handler(CommandHandler("referencias",  referencias_command))
    app.add_handler(CommandHandler("admin",        admin_command))
    app.add_handler(CommandHandler("unadmin",      unadmin_command))
    app.add_handler(CommandHandler("panel",        panel_command))

    # Callbacks
    app.add_handler(CallbackQueryHandler(confirmar_generacion_callback, pattern="^gen_(ok|no)_"))
    app.add_handler(CallbackQueryHandler(apk_precios_callback,          pattern="^apk_precios$"))
    app.add_handler(CallbackQueryHandler(referencias_callback,          pattern="^ref_next_"))
    app.add_handler(CallbackQueryHandler(panel_callback,                pattern="^panel_"))

    # Mensajes
    app.add_handler(MessageHandler(filters.PHOTO,                   handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot iniciado correctamente.")

    MAX_REINTENTOS = 5
    reintentos     = 0

    while True:
        try:
            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            break  # salida limpia si termina normalmente
        except Exception as e:
            error_str = str(e)
            if "Conflict" in error_str:
                reintentos += 1
                espera = min(30, 5 * reintentos)
                logging.warning(
                    f"⚠️ Conflict detectado (intento {reintentos}/{MAX_REINTENTOS}). "
                    f"Esperando {espera}s..."
                )
                time.sleep(espera)
                if reintentos >= MAX_REINTENTOS:
                    logging.error("❌ Demasiados Conflicts. Abortando.")
                    sys.exit(1)
            else:
                logging.error(f"❌ Error inesperado: {e}. Reiniciando en 10s...")
                time.sleep(10)


if __name__ == "__main__":
    main()
