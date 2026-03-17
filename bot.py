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
import os, sys, logging, json, urllib.parse
from datetime import datetime, date, timedelta
import pytz

logging.basicConfig(level=logging.INFO)

# ═══════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════
ADMIN_ID          = 7422843477
ALLOWED_GROUP     = -1003512376124
REQUIRED_GROUP_ID = -1003512376124

auth_system = AuthSystem(ADMIN_ID, ALLOWED_GROUP)
fecha_manual_mode      = {}
referencia_manual_mode = {}
REFERENCIAS_FILE       = "referencias.json"
VENCIMIENTOS_FILE      = "vencimientos.json"
USER_DATA_FILE         = "user_data_store.json"

# ═══════════════════════════════════════════════
# USER DATA STORE PERSISTENTE
# ═══════════════════════════════════════════════
def _uds_load():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                return {int(k): v for k, v in json.load(f).items()}
        except: pass
    return {}

def _uds_dump(store):
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(k): dict(v) for k, v in store.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[UDS] Error guardando: {e}")

class _InnerDict(dict):
    def __init__(self, data, cb):
        super().__init__(data); self._cb = cb
    def __setitem__(self, k, v):
        super().__setitem__(k, v); self._cb()
    def __delitem__(self, k):
        super().__delitem__(k); self._cb()
    def update(self, *a, **kw):
        super().update(*a, **kw); self._cb()

class UDS(dict):
    def __setitem__(self, k, v):
        super().__setitem__(k, _InnerDict(v, lambda: _uds_dump(self)))
        _uds_dump(self)
    def __delitem__(self, k):
        super().__delitem__(k); _uds_dump(self)

uds = UDS()
for _k, _v in _uds_load().items():
    # Limpiar estados "generando" que quedaron corruptos
    if _v.get("step") != "generando":
        super(UDS, uds).__setitem__(_k, _InnerDict(_v, lambda: _uds_dump(uds)))

user_data_store = uds

# ═══════════════════════════════════════════════
# SMS CRÉDITOS
# ═══════════════════════════════════════════════
SMS_FILE = "sms_creditos.json"

def cargar_sms_creditos():
    if os.path.exists(SMS_FILE):
        try:
            with open(SMS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {}

def guardar_sms_creditos(data):
    with open(SMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def asignar_sms_por_dias(user_id, dias):
    sms = int(round(dias / 30)) * 100
    c = cargar_sms_creditos(); uid = str(user_id)
    c[uid] = c.get(uid, 0) + sms
    guardar_sms_creditos(c); return sms

def recargar_sms(user_id, cantidad):
    c = cargar_sms_creditos(); uid = str(user_id)
    c[uid] = c.get(uid, 0) + cantidad
    guardar_sms_creditos(c); return c[uid]

def puede_enviar_sms(user_id):
    return cargar_sms_creditos().get(str(user_id), 0) > 0

def consumir_sms(user_id):
    c = cargar_sms_creditos(); uid = str(user_id)
    if c.get(uid, 0) > 0:
        c[uid] -= 1; guardar_sms_creditos(c); return c[uid]
    return 0

def get_sms_restantes(user_id):
    return cargar_sms_creditos().get(str(user_id), 0)

# ═══════════════════════════════════════════════
# SMS AUTORIZACIÓN (admin debe autorizar al usuario)
# ═══════════════════════════════════════════════
SMS_AUTH_FILE = "sms_autorizados.json"

def cargar_sms_autorizados():
    if os.path.exists(SMS_AUTH_FILE):
        try:
            with open(SMS_AUTH_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: pass
    return []

def guardar_sms_autorizados(data):
    with open(SMS_AUTH_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def autorizar_sms(user_id):
    a = cargar_sms_autorizados()
    uid = str(user_id)
    if uid not in a:
        a.append(uid)
        guardar_sms_autorizados(a)
    return True

def desautorizar_sms(user_id):
    a = cargar_sms_autorizados()
    uid = str(user_id)
    if uid in a:
        a.remove(uid)
        guardar_sms_autorizados(a)

def sms_autorizado(user_id):
    """Usuario puede enviar SMS si: es admin O está autorizado por admin"""
    if auth_system.is_admin(user_id):
        return True
    return str(user_id) in cargar_sms_autorizados()

# ═══════════════════════════════════════════════
# QR EMV PARSER
# ═══════════════════════════════════════════════
def parsear_qr_emv(contenido):
    try:
        pos = 0; datos = {}
        while pos + 4 <= len(contenido):
            tag = contenido[pos:pos+2]
            try: length = int(contenido[pos+2:pos+4])
            except ValueError: break
            value = contenido[pos+4:pos+4+length]; datos[tag] = value; pos += 4 + length
        if "59" in datos and datos["59"].strip(): return datos["59"].strip()
        if "26" in datos:
            sub = datos["26"]; sp = 0
            while sp + 4 <= len(sub):
                st = sub[sp:sp+2]
                try: sl = int(sub[sp+2:sp+4])
                except ValueError: break
                sv = sub[sp+4:sp+4+sl]
                if st == "02" and sv.strip(): return sv.strip()
                sp += 4 + sl
    except: pass
    return None

def extraer_nombre_qr(contenido):
    n = parsear_qr_emv(contenido)
    if n: return n
    if "=" in contenido:
        try:
            params = dict(urllib.parse.parse_qsl(contenido.split("?")[-1]))
            for k in ["name","Name","merchant","businessName","alias","comercio","negocio"]:
                if k in params and params[k].strip(): return params[k].strip()
        except: pass
    return contenido[:40].strip()

# ═══════════════════════════════════════════════
# VENCIMIENTOS
# ═══════════════════════════════════════════════
def cargar_vencimientos():
    if os.path.exists(VENCIMIENTOS_FILE):
        try:
            with open(VENCIMIENTOS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {}

def guardar_vencimientos(data):
    with open(VENCIMIENTOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def agregar_vencimiento(user_id, nombre, dias=30):
    v = cargar_vencimientos()
    fv = (date.today() + timedelta(days=dias)).isoformat()
    v[str(user_id)] = {"nombre": nombre, "fecha_vence": fv, "dias": dias,
                       "aviso3_enviado": False, "expirado_enviado": False}
    guardar_vencimientos(v); return fv

def eliminar_vencimiento(user_id):
    v = cargar_vencimientos()
    if str(user_id) in v: del v[str(user_id)]; guardar_vencimientos(v)

async def verificar_vencimientos(context: ContextTypes.DEFAULT_TYPE):
    v = cargar_vencimientos(); hoy = date.today(); actualizar = False
    for uid_str, info in v.items():
        uid = int(uid_str)
        fv = date.fromisoformat(info["fecha_vence"])
        dr = (fv - hoy).days
        if dr == 3 and not info.get("aviso3_enviado"):
            try:
                await context.bot.send_message(chat_id=uid, parse_mode="Markdown",
                    text=f"⚠️ *Aviso de Vencimiento*\n\nHola {info['nombre']}, tu acceso vence en *3 días* ({fv.strftime('%d/%m/%Y')}).\n\nRenueva con un administrador.\n\n🔑 ADM 2: @StephenCurry030")
                info["aviso3_enviado"] = True; actualizar = True
            except Exception as e: logging.error(f"[VENC] {e}")
        elif dr <= 0 and not info.get("expirado_enviado"):
            try:
                await context.bot.send_message(chat_id=uid, parse_mode="Markdown",
                    text=f"🔴 *Acceso Expirado*\n\nHola {info['nombre']}, tu acceso ha expirado.\n\nContacta a un administrador para renovar:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔑 ADM 2", url="https://t.me/StephenCurry030")],
                        [InlineKeyboardButton("📢 Grupo", url="https://t.me/nequixxxcurry")]]))
                auth_system.remove_user(uid); info["expirado_enviado"] = True; actualizar = True
            except Exception as e: logging.error(f"[VENC] {e}")
    if actualizar: guardar_vencimientos(v)

# ═══════════════════════════════════════════════
# SMS VONAGE
# ═══════════════════════════════════════════════
def enviar_sms_twilio(numero, valor, mensaje_custom=False):
    try:
        import vonage
        api_key    = os.environ.get('VONAGE_API_KEY')
        api_secret = os.environ.get('VONAGE_API_SECRET')
        remitente  = os.environ.get('VONAGE_FROM_NUMBER', 'Vonage APIs')

        if not all([api_key, api_secret]):
            logging.error("[SMS] Faltan variables VONAGE"); return False

        num = str(numero).strip() if numero else ""
        if not num:
            logging.error("[SMS] Número vacío"); return False
        if not num.startswith('+'):
            num = f"+57{num}"

        try:
            valor_num = float(str(valor).replace(".", "").replace(",", "").replace(" ", "")) if valor is not None else 0
            valor_seguro = int(abs(valor_num))
        except (TypeError, ValueError):
            valor_seguro = 0

        if mensaje_custom:
            msg = str(valor) if valor else "Transferencia recibida"
        else:
            msg = f"Te han transferido ${valor_seguro:,} COP. Verifica en tu app".replace(",", ".")

        client = vonage.Client(key=api_key, secret=api_secret)
        sms    = vonage.Sms(client)
        resp   = sms.send_message({
            "from": remitente,
            "to":   num,
            "text": msg
        })

        if resp["messages"][0]["status"] == "0":
            logging.info(f"[SMS] Enviado OK a {num}")
            return True
        else:
            logging.error(f"[SMS] Error Vonage: {resp['messages'][0]['error-text']}")
            return False
    except Exception as e:
        logging.error(f"[SMS] Error: {e}"); return False

def puede_enviar_sms_comprobante(user_id):
    """Solo puede enviar SMS si tiene autorización del ADM"""
    return sms_autorizado(user_id) and (
        auth_system.is_admin(user_id) or puede_enviar_sms(user_id)
    )

# ═══════════════════════════════════════════════
# REFERENCIAS
# ═══════════════════════════════════════════════
def cargar_referencias():
    if os.path.exists(REFERENCIAS_FILE):
        try:
            with open(REFERENCIAS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return []

def guardar_referencias(r):
    with open(REFERENCIAS_FILE, 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=2)

# ═══════════════════════════════════════════════
# TECLADOS
# ═══════════════════════════════════════════════
def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 ¿Necesitas acceso?", callback_data="apk_precios")],
        [InlineKeyboardButton("🔑 ADM 2", url="https://t.me/StephenCurry030")],
        [InlineKeyboardButton("📢 Grupo", url="https://t.me/nequixxxcurry")]
    ])

def sms_anuncio_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Ver Paquetes SMS", callback_data="sms_ofertas")],
        [InlineKeyboardButton("🔑 ADM 2", url="https://t.me/StephenCurry030")],
    ])

SMS_ANUNCIO = (
    "📲 *¡SERVICIO SMS DISPONIBLE!*\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "✅ Este bot puede enviar un *SMS real* al celular del destinatario notificando la transferencia.\n\n"
    "💡 *¿Cómo obtener SMS?*\n"
    "• Los usuarios *ADM* tienen SMS ilimitados ✅\n"
    "• Los usuarios *VIP* pueden comprar paquetes SMS\n"
    "• Contacta a un ADM para recargar tus créditos\n\n"
    "📦 *Paquetes disponibles:*\n"
    "• 100 SMS → $10.000 COP\n"
    "• 200 SMS → $20.000 COP\n"
    "• 300 SMS → $30.000 COP\n"
    "• 500 SMS → $50.000 COP"
)

SMS_SIN_CREDITOS = (
    "📲 *SMS no enviado*\n\n"
    "⚠️ No tienes créditos SMS disponibles.\n\n"
    "📦 *Compra un paquete SMS con el ADM:*\n"
    "• 100 SMS → $10.000 COP\n"
    "• 200 SMS → $20.000 COP\n"
    "• 300 SMS → $30.000 COP\n"
    "• 500 SMS → $50.000 COP\n\n"
    "Tu comprobante fue generado correctamente ✅"
)

SMS_NO_AUTORIZADO = (
    "📲 *SMS no disponible*\n\n"
    "⚠️ No tienes autorización para usar el servicio SMS.\n\n"
    "📩 *Solicita autorización al ADM:*\n"
    "Escríbele al administrador para que te autorice con el comando `/autorizarsms`\n\n"
    "Tu comprobante fue generado correctamente ✅"
)

# ═══════════════════════════════════════════════
# CACHÉ MEMBRESÍA
# ═══════════════════════════════════════════════
_membresia_cache = {}
MEMBRESIA_TTL = 21600

async def is_member_of_group(bot, user_id):
    import time
    cached = _membresia_cache.get(user_id)
    if cached and (time.time() - cached[0]) < MEMBRESIA_TTL: return cached[1]
    try:
        m = await bot.get_chat_member(chat_id=REQUIRED_GROUP_ID, user_id=user_id)
        result = m.status in ['member', 'administrator', 'creator']
    except:
        result = True
    _membresia_cache[user_id] = (time.time(), result)
    return result

# ═══════════════════════════════════════════════
# NOTIFY ADMIN
# ═══════════════════════════════════════════════
async def notify_main_admin(context, admin_id, admin_name, action, target=""):
    if admin_id == ADMIN_ID: return
    try:
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        msg = f"🔔 *Notificación*\n👤 {admin_id} ({admin_name})\n⚡ {action}"
        if target: msg += f"\n🎯 {target}"
        msg += f"\n🕐 {now}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='Markdown')
    except: pass

# ═══════════════════════════════════════════════
# SEND SUCCESS MESSAGE
# ═══════════════════════════════════════════════
async def send_success_message(update: Update, sms_data: dict = None):
    user_id = update.effective_user.id
    nombre  = update.effective_user.first_name or "Usuario"

    await update.message.reply_text(
        f"✅ <b>Comprobante generado con éxito</b>\n\n"
        f"👤 <b>{nombre}</b>, usa /comprobante para generar otro\n\n"
        f"🙏 <b>Gracias por utilizar nuestros servicios</b>",
        parse_mode='HTML')

# ═══════════════════════════════════════════════
# HELPER: parsers
# ═══════════════════════════════════════════════
def parse_valor(text):
    if not text or not isinstance(text, str):
        raise ValueError("Valor vacío o nulo")
    limpio = text.strip().replace(".", "").replace(",", "").replace(" ", "")
    if limpio.startswith("-"):
        limpio = limpio[1:]
    if not limpio:
        raise ValueError("Valor vacío")
    if not limpio.isdigit():
        raise ValueError(f"No es numérico: {limpio}")
    v = int(limpio)
    if v == 0:
        raise ValueError("Valor cero")
    return v

def parse_tel(text):
    if not text or not isinstance(text, str):
        return None
    d = text.strip().replace(" ", "").replace("-", "")
    if d.isdigit() and len(d) == 10 and d.startswith('3'):
        return d
    return None

def parse_nombre(text):
    if not text or not isinstance(text, str):
        return None
    n = text.strip()
    if len(n) < 2:
        return None
    return n

# ═══════════════════════════════════════════════
# COMANDOS PÚBLICOS
# ═══════════════════════════════════════════════
async def start_redirect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.effective_user.first_name or "Usuario"
    await update.message.reply_text(
        f"👋 Hola *{nombre}*! Bienvenido al bot.\n\n"
        "📋 *MENÚ DE COMANDOS*\n━━━━━━━━━━━━━━━━━\n\n"
        "🧾 /comprobante — Generar comprobante\n"
        "📅 /fechas — Activar fecha manual\n"
        "🔢 /refes — Activar referencia manual\n"
        "💵 /precios — Ver planes y precios\n"
        "📲 /sms — Paquetes SMS\n"
        "🕰️ /horarios — Horarios de acceso gratis\n"
        "🔲 /brqr — Comprobante por QR\n"
        "✅ /verificar — Verificar tu membresía\n"
        "❌ /cancelar — Cancelar operación actual\n\n"
        "━━━━━━━━━━━━━━━━━\nUsa /comprobante para empezar 👇",
        parse_mode='Markdown', reply_markup=admin_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if auth_system.is_banned(user_id):
        await update.message.reply_text("Estás baneado. Contacta al administrador."); return
    if not auth_system.can_use_bot(user_id, chat_id) and not auth_system.gratis_mode:
        await update.message.reply_text("🔴 *Bot en Modo OFF*\n\n💰 Contacta a un administrador para acceso premium.",
            parse_mode='Markdown', reply_markup=admin_keyboard()); return
    keyboard = [
        [KeyboardButton("💚 Nequi"),          KeyboardButton("🔴 Daviplata")],
        [KeyboardButton("🔵 Bre B"),           KeyboardButton("🟣 Transfiya")],
        [KeyboardButton("🏦 BC a NQ"),         KeyboardButton("🏦 BC QR")],
        [KeyboardButton("💰 Ahorros"),         KeyboardButton("💳 Corriente")],
        [KeyboardButton("🟢 Nequi Corriente"), KeyboardButton("🟢 Nequi Ahorros")],
        [KeyboardButton("📷 QR Escanear"),     KeyboardButton("❌ Anulado")],
        [KeyboardButton("🔲 Nequi QR")]
    ]
    await update.message.reply_text(
        f"╔══════════════════╗\n      🧾 *COMPROBANTES*\n╚══════════════════╝\n\n"
        f"👋 Hola *{update.effective_user.first_name or 'Usuario'}*!\n"
        f"Selecciona el tipo de comprobante que deseas generar 👇",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False))

# ═══════════════════════════════════════════════
# SMS COMANDOS
# ═══════════════════════════════════════════════
async def sms_ofertas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(SMS_ANUNCIO, parse_mode='Markdown', reply_markup=sms_anuncio_kb())

async def sms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(SMS_ANUNCIO, parse_mode='Markdown', reply_markup=sms_anuncio_kb())

async def smss_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("❌ Solo admins."); return
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /smss <id_usuario> <cantidad>\nEjemplo: /smss 123456789 100"); return
    try:
        tid = int(context.args[0]); cant = int(context.args[1])
        if cant <= 0: await update.message.reply_text("❌ Cantidad debe ser mayor a 0."); return
        total = recargar_sms(tid, cant)
        await update.message.reply_text(
            f"✅ *SMS Recargados*\n\n👤 Usuario: `{tid}`\n➕ Recarga: {cant} SMS\n💳 Total: {total} SMS",
            parse_mode='Markdown')
        try:
            await context.bot.send_message(chat_id=tid,
                text=f"📲 *¡SMS Recargados!*\n\nTe han recargado *{cant} SMS*.\nTotal disponible: *{total} SMS*.",
                parse_mode='Markdown')
        except: pass
        await notify_main_admin(context, user_id, update.effective_user.first_name, f"Recargó {cant} SMS", str(tid))
    except ValueError:
        await update.message.reply_text("❌ ID o cantidad inválida.")

async def autorizarsms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid):
        await update.message.reply_text("❌ Solo admins."); return
    if not context.args:
        await update.message.reply_text("Uso: /autorizarsms <id>\nEjemplo: /autorizarsms 123456789"); return
    try:
        tid = int(context.args[0])
        autorizar_sms(tid)
        await update.message.reply_text(
            f"✅ *Usuario `{tid}` autorizado para SMS*\n\n"
            f"Ahora puede enviar SMS al generar comprobantes.\n"
            f"Recuerda recargarle créditos con `/smss {tid} 100`",
            parse_mode='Markdown')
        try:
            await context.bot.send_message(chat_id=tid, parse_mode="Markdown",
                text="✅ *¡Autorizado para SMS!*\n\n"
                     "El ADM te autorizó a usar el servicio SMS.\n"
                     "Cuando generes comprobantes, podrás enviar SMS al destinatario. 📲\n\n"
                     "Usa /sms para ver los paquetes disponibles.")
        except: pass
        await notify_main_admin(context, uid, update.effective_user.first_name, "Autorizó SMS a usuario", str(tid))
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def desautorizarsms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid):
        await update.message.reply_text("❌ Solo admins."); return
    if not context.args:
        await update.message.reply_text("Uso: /desautorizarsms <id>"); return
    try:
        tid = int(context.args[0])
        desautorizar_sms(tid)
        await update.message.reply_text(f"🚫 Usuario `{tid}` desautorizado para SMS.", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

# ═══════════════════════════════════════════════
# PANEL SMS
# ═══════════════════════════════════════════════
async def panelsms_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not auth_system.is_admin(user_id):
        await update.message.reply_text("❌ Solo admins."); return
    c = cargar_sms_creditos()
    a = cargar_sms_autorizados()
    await update.message.reply_text(
        f"📲 *PANEL SMS — ADMINISTRACIÓN*\n━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Usuarios con SMS: *{len(c)}*\n💳 Total en circulación: *{sum(c.values())}*\n"
        f"🔑 Usuarios autorizados SMS: *{len(a)}*\n\n"
        "━━━━━━━━━━━━━━━━━\n⚙️ *COMANDOS SMS:*\n\n"
        "📥 `/smss <ID> <cant>` — Recargar SMS\n"
        "✅ `/autorizarsms <ID>` — Autorizar usuario para SMS\n"
        "❌ `/desautorizarsms <ID>` — Quitar autorización SMS\n"
        "🔍 `/smschk <ID>` — Ver SMS de usuario\n"
        "📋 `/smslista` — Ver todos los saldos\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "💡 SMS automáticos al agregar VIP:\n• 30d→100 • 60d→200 • 90d→300\n\n"
        "⚠️ *El usuario debe ser autorizado por el ADM para poder usar SMS.*",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Ver Saldos", callback_data="panelsms_lista"),
             InlineKeyboardButton("📊 Stats", callback_data="panelsms_stats")],
            [InlineKeyboardButton("🔄 Recargar SMS", callback_data="panelsms_recargar")],
            [InlineKeyboardButton("✅ Activar VIP + SMS", callback_data="panelsms_activar_vip")]]))

async def smschk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins."); return
    if not context.args:
        await update.message.reply_text("Uso: /smschk <id>"); return
    try:
        tid = int(context.args[0]); sms = get_sms_restantes(tid)
        v = cargar_vencimientos(); info = v.get(str(tid))
        autorizado = sms_autorizado(tid)
        txt = f"🔍 *Info SMS*\n\n🆔 ID: `{tid}`\n💳 SMS disponibles: *{sms}*\n🔑 Autorizado SMS: *{'✅ Sí' if autorizado else '❌ No'}*\n"
        if info:
            txt += f"📅 VIP vence: {info.get('fecha_vence','N/A')}\n👤 Nombre: {info.get('nombre','N/A')}"
        else:
            txt += "⚠️ Sin membresía VIP activa"
        await update.message.reply_text(txt, parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")

async def smslista_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth_system.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Solo admins."); return
    c = cargar_sms_creditos(); v = cargar_vencimientos(); a = cargar_sms_autorizados()
    if not c: await update.message.reply_text("📭 No hay usuarios con SMS."); return
    lineas = ["📋 *LISTA SMS USUARIOS*\n━━━━━━━━━━━━━━━━━\n"]
    for uid_str, sms in sorted(c.items(), key=lambda x: -x[1]):
        nombre = v.get(uid_str, {}).get("nombre", "Desconocido")
        aut = "✅" if uid_str in a else "❌"
        lineas.append(f"👤 `{uid_str}` ({nombre}): *{sms} SMS* {aut}")
    txt = "\n".join(lineas)
    if len(txt) > 4000: txt = txt[:4000] + "\n...(truncado)"
    await update.message.reply_text(txt, parse_mode='Markdown')

async def panelsms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; user_id = q.from_user.id
    if not auth_system.is_admin(user_id):
        await q.answer("⛔ Sin permisos.", show_alert=True); return
    await q.answer()
    c = cargar_sms_creditos(); v = cargar_vencimientos()
    if q.data == "panelsms_lista":
        if not c: await q.message.reply_text("📭 Sin datos."); return
        a = cargar_sms_autorizados()
        lineas = ["📋 *SALDOS SMS*\n━━━━━━━━━━━━━━━━━\n"]
        for uid_str, sms in sorted(c.items(), key=lambda x: -x[1])[:20]:
            nombre = v.get(uid_str, {}).get("nombre", "Desconocido")
            aut = "✅" if uid_str in a else "❌"
            lineas.append(f"👤 `{uid_str}` ({nombre}): *{sms} SMS* {aut}")
        await q.message.reply_text("\n".join(lineas), parse_mode='Markdown')
    elif q.data == "panelsms_stats":
        a = cargar_sms_autorizados()
        total = sum(c.values())
        await q.edit_message_text(
            f"📊 *Estadísticas SMS*\n\n💳 Total: *{total}*\n✅ Con SMS: *{sum(1 for x in c.values() if x>0)}*\n"
            f"⚠️ Sin SMS: *{sum(1 for x in c.values() if x==0)}*\n🔑 Autorizados: *{len(a)}*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data="panelsms_back")]]))
    elif q.data == "panelsms_recargar":
        await q.message.reply_text("📥 Usa:\n`/smss <ID> <cantidad>`\n\nEjemplo: `/smss 123456789 100`", parse_mode='Markdown')
    elif q.data == "panelsms_activar_vip":
        await q.message.reply_text(
            "✅ Usa `/agregar` para activar VIP.\n"
            "Los SMS se asignan automáticamente.\n\n"
            "Luego autoriza con:\n`/autorizarsms <ID>`", parse_mode='Markdown')
    elif q.data == "panelsms_back":
        a = cargar_sms_autorizados()
        await q.edit_message_text(
            f"📲 *PANEL SMS*\n\n👥 Usuarios: *{len(c)}*\n💳 Total: *{sum(c.values())}*\n🔑 Autorizados: *{len(a)}*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Ver Saldos", callback_data="panelsms_lista"),
                 InlineKeyboardButton("📊 Stats", callback_data="panelsms_stats")],
                [InlineKeyboardButton("🔄 Recargar SMS", callback_data="panelsms_recargar")],
                [InlineKeyboardButton("✅ Activar VIP + SMS", callback_data="panelsms_activar_vip")]]))

# ═══════════════════════════════════════════════
# HANDLE PHOTO
# ═══════════════════════════════════════════════
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; chat_id = update.effective_chat.id
    if auth_system.is_banned(user_id):
        await update.message.reply_text("Estás baneado."); return
    if not auth_system.gratis_mode and not auth_system.can_use_bot(user_id, chat_id):
        await update.message.reply_text("⛔ No tienes acceso.", reply_markup=admin_keyboard()); return
    if user_id in user_data_store and user_data_store[user_id].get("step") == "brqr_esperando_foto":
        await update.message.reply_text("🔍 Leyendo código QR...")
        try:
            import cv2, numpy as np
            photo = update.message.photo[-1]; file = await context.bot.get_file(photo.file_id)
            fb = await file.download_as_bytearray()
            img = cv2.imdecode(np.frombuffer(fb, np.uint8), cv2.IMREAD_COLOR)
            contenido, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
            if not contenido:
                await update.message.reply_text("❌ No se pudo leer el QR. Usa /brqr modo manual.")
                del user_data_store[user_id]; return
            nombre = extraer_nombre_qr(contenido)[:40].strip()
            user_data_store[user_id]["nombre"] = nombre
            user_data_store[user_id]["step"] = "brqr_monto"
            await update.message.reply_text(f"✅ *QR leído*\n\n🏪 *Negocio:* `{nombre}`\n\n💰 ¿Cuánto es el monto?", parse_mode="Markdown")
        except ImportError:
            await update.message.reply_text("❌ Error QR. Usa /brqr modo manual."); del user_data_store[user_id]
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}\n\nUsa /brqr modo manual."); del user_data_store[user_id]
        return
    if user_id in user_data_store: return
    await update.message.reply_text("🔍 Leyendo código QR...")
    try:
        import cv2, numpy as np
        photo = update.message.photo[-1]; file = await context.bot.get_file(photo.file_id)
        fb = await file.download_as_bytearray()
        img = cv2.imdecode(np.frombuffer(fb, np.uint8), cv2.IMREAD_COLOR)
        contenido, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
        if not contenido:
            await update.message.reply_text("❌ No se pudo leer el QR."); return
        nombre = extraer_nombre_qr(contenido)[:30].strip()
        user_data_store[user_id] = {"step": "qr_monto", "tipo": "comprobante_qr", "nombre": nombre}
        await update.message.reply_text(f"✅ *QR leído*\n\n🏪 *Negocio:* {nombre}\n\n💰 ¿Cuánto es el monto?", parse_mode="Markdown")
    except ImportError:
        await update.message.reply_text("❌ Error QR. Usa /brqr modo manual.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ═══════════════════════════════════════════════
# HANDLE MESSAGE — flujo principal
# ═══════════════════════════════════════════════
BUTTON_MAPPING = {
    "💚 Nequi":           "comprobante1",
    "🟣 Transfiya":        "comprobante4",
    "🔴 Daviplata":        "comprobante_daviplata",
    "🔲 Nequi QR":         "comprobante_qr",
    "🔵 Bre B":            "comprobante_nuevo",
    "❌ Anulado":          "comprobante_anulado",
    "💰 Ahorros":          "comprobante_ahorros",
    "💳 Corriente":        "comprobante_corriente",
    "🏦 BC a NQ":          "comprobante_bc_nq_t",
    "🏦 BC QR":            "comprobante_bc_qr",
    "🟢 Nequi Corriente":  "comprobante_nequi_bc",
    "🟢 Nequi Ahorros":    "comprobante_nequi_ahorros",
    "📷 QR Escanear":      "brqr_directo",
}

PROMPTS = {
    "comprobante1":           "👤 Ingresa el *nombre* del destinatario:",
    "comprobante4":           "📱 Ingresa el *número* a transferir (10 dígitos, empieza en 3):",
    "comprobante_qr":         "🏪 Ingresa el *nombre del negocio*:",
    "comprobante_nuevo":      "👤 Ingresa el *nombre*:",
    "comprobante_anulado":    "👤 Ingresa el *nombre*:",
    "comprobante_corriente":  "👤 Ingresa el *nombre*:",
    "comprobante_daviplata":  "👤 Ingresa el *nombre* del titular Daviplata:",
    "comprobante_ahorros":    "👤 Ingresa el *nombre*:",
    "comprobante_bc_nq_t":    "📱 Ingresa el *número de teléfono* (10 dígitos, empieza en 3):",
    "comprobante_bc_qr":      "📝 Ingresa la *descripción del QR*:",
    "comprobante_nequi_bc":   "👤 Ingresa el *nombre*:",
    "comprobante_nequi_ahorros": "👤 Ingresa el *nombre*:",
}

STEP_HINTS = {
    0:                    "👤 Ingresa el *nombre* del destinatario:",
    1:                    "📱 Ingresa el *número de teléfono* (10 dígitos, empieza en 3):",
    2:                    "💰 Ingresa el *valor* a transferir (solo números, ej: 50000):",
    3:                    "📅 Ingresa la *fecha* (ej: 28/02/2026 10:30 AM):",
    10:                   "🔢 Ingresa la *referencia* (ej: M12345678):",
    20:                   "💰 Ingresa el *valor* a transferir (solo números, ej: 50000):",
    "brqr_nombre_manual": "✏️ Escribe el *nombre del negocio*:",
    "brqr_monto":         "💰 Ingresa el *monto* (solo números, ej: 50000):",
    "qr_monto":           "💰 Ingresa el *monto* (solo números, ej: 50000):",
}

BASURA = {".", "..", "...", ",", "-", "_", "/", "\\", "!", "?", " ", "  "}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text    = (update.message.text or "").strip()

    logging.info(f"[MSG] user={user_id} text='{text}' en_store={user_id in user_data_store} store={user_data_store.get(user_id)}")

    if not text:
        return

    if user_id in user_data_store and text in BASURA:
        step = user_data_store[user_id].get("step")
        hint = STEP_HINTS.get(step, "⚠️ Continúa ingresando los datos correctamente.")
        await update.message.reply_text(hint, parse_mode="Markdown"); return

    # ── brqr nombre manual ──
    if user_id in user_data_store and user_data_store[user_id].get("step") == "brqr_nombre_manual":
        nombre = parse_nombre(text)
        if not nombre:
            await update.message.reply_text("❌ Nombre muy corto. Escribe el nombre del negocio:"); return
        user_data_store[user_id]["nombre"] = nombre
        user_data_store[user_id]["step"]   = "brqr_monto"
        await update.message.reply_text(f"🏪 Negocio: *{nombre}*\n\n💰 ¿Cuánto es el monto?", parse_mode="Markdown"); return

    # ── brqr monto ──
    if user_id in user_data_store and user_data_store[user_id].get("step") == "brqr_monto":
        data = user_data_store[user_id]
        try: valor = parse_valor(text)
        except: await update.message.reply_text("❌ El valor debe ser numérico. Ej: 50000"); return
        if valor < 1000: await update.message.reply_text("❌ Mínimo $1,000."); return
        data["valor"] = valor
        await update.message.reply_text("⏳ Generando comprobante QR...")
        try:
            out = generar_comprobante(data, COMPROBANTE_QR_CONFIG)
            with open(out,"rb") as f: await update.message.reply_document(document=f, caption=" ")
            os.remove(out)
            dm = {"nombre": (data.get("nombre") or "").upper(), "valor": -abs(valor)}
            out2 = generar_comprobante(dm, COMPROBANTE_MOVIMIENTO3_CONFIG)
            with open(out2,"rb") as f: await update.message.reply_document(document=f, caption=" ")
            os.remove(out2)
            await send_success_message(update)
        except Exception as e:
            await update.message.reply_text(f"❌ Error generando comprobante: {e}")
        del user_data_store[user_id]; return

    # ── qr_monto (QR libre desde foto) ──
    if user_id in user_data_store and user_data_store[user_id].get("step") == "qr_monto":
        data = user_data_store[user_id]
        try: valor = parse_valor(text)
        except: await update.message.reply_text("❌ El valor debe ser numérico. Ej: 50000"); return
        if valor < 1000: await update.message.reply_text("❌ Mínimo $1,000."); return
        data["valor"] = valor
        await update.message.reply_text("⏳ Generando comprobante QR...")
        try:
            out = generar_comprobante(data, COMPROBANTE_QR_CONFIG)
            with open(out,"rb") as f: await update.message.reply_document(document=f, caption=" ")
            os.remove(out)
            dm = {"nombre": (data.get("nombre") or "").upper(), "valor": -abs(valor)}
            out2 = generar_comprobante(dm, COMPROBANTE_MOVIMIENTO3_CONFIG)
            with open(out2,"rb") as f: await update.message.reply_document(document=f, caption=" ")
            os.remove(out2)
            await send_success_message(update)
        except Exception as e:
            await update.message.reply_text(f"❌ Error generando comprobante: {e}")
        del user_data_store[user_id]; return

    # ══════════════════════════════════════════════
    # Botón del menú → cancela flujo anterior y reinicia
    # ══════════════════════════════════════════════
    if text in BUTTON_MAPPING:
        if user_id in user_data_store:
            del user_data_store[user_id]
        if auth_system.is_banned(user_id):
            await update.message.reply_text("Estás baneado."); return
        if not auth_system.gratis_mode:
            if not auth_system.can_use_bot(user_id, chat_id):
                await update.message.reply_text("🔴 Bot en Modo OFF\n\nContacta a un administrador:", reply_markup=admin_keyboard()); return
        tipo = BUTTON_MAPPING[text]
        if tipo == "brqr_directo":
            await update.message.reply_text("🔲 *Generador Comprobante QR*\n\n¿Cómo quieres ingresar el nombre?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📷 Escanear QR", callback_data="brqr_scan"),
                    InlineKeyboardButton("✏️ Ingresar Manual", callback_data="brqr_manual")]])); return
        user_data_store[user_id] = {"step": 0, "tipo": tipo}
        await update.message.reply_text(PROMPTS.get(tipo, "Ingresa los datos:"), parse_mode="Markdown"); return

    if user_id not in user_data_store: return
    if auth_system.is_banned(user_id):
        await update.message.reply_text("Estás baneado."); return

    data = user_data_store[user_id]
    tipo = data.get("tipo")
    step = data.get("step")

    if not tipo:
        del user_data_store[user_id]; return

    # Si ya está generando, limpiar estado y dejar continuar
    if step == "generando":
        del user_data_store[user_id]
        await update.message.reply_text("⚠️ Operación anterior interrumpida. Usa /comprobante para iniciar.")
        return

    # ─────────────────────────────────────────
    # COMPROBANTE 1 — NEQUI
    # ─────────────────────────────────────────
    if tipo == "comprobante1":
        if step == 0:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Ingresa el nombre completo del destinatario:"); return
            data["nombre"] = nombre; data["step"] = 1
            await update.message.reply_text("📱 Ingresa el *número de teléfono* del destinatario (10 dígitos, empieza en 3):", parse_mode="Markdown")
        elif step == 1:
            tel = parse_tel(text)
            if not tel:
                await update.message.reply_text("❌ Número inválido. Debe tener 10 dígitos y empezar en 3.\nEjemplo: 3001234567"); return
            data["telefono"] = tel; data["step"] = 2
            await update.message.reply_text("💰 Ingresa el *valor* a transferir (ej: 50000):", parse_mode="Markdown")
        elif step == 2:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido. Solo números.\nEjemplo: 50000"); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v
            if referencia_manual_mode.get(user_id):
                data["step"] = 10; await update.message.reply_text("🔢 Ingresa la referencia\nEjemplo: M12345678"); return
            if fecha_manual_mode.get(user_id):
                data["step"] = 3; await update.message.reply_text("📅 Ingresa la fecha\nEjemplo: 28/02/2026 10:30 AM"); return
            await _gen_nequi(update, data, v)
        elif step == 3:
            data["fecha_manual"] = text; await _gen_nequi(update, data, data["valor"])
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11; await update.message.reply_text("📅 Ingresa la fecha\nEjemplo: 28/02/2026 10:30 AM"); return
            await _gen_nequi(update, data, data["valor"])
        elif step == 11:
            data["fecha_manual"] = text; await _gen_nequi(update, data, data["valor"])

    # ─────────────────────────────────────────
    # COMPROBANTE 4 — TRANSFIYA
    # ─────────────────────────────────────────
    elif tipo == "comprobante4":
        if step == 0:
            tel = parse_tel(text)
            if not tel:
                await update.message.reply_text("❌ Número inválido. Debe tener 10 dígitos y empezar en 3.\nEjemplo: 3001234567"); return
            data["telefono"] = tel; data["step"] = 1
            await update.message.reply_text("💰 Ingresa el *valor* a transferir (ej: 50000):", parse_mode="Markdown")
        elif step == 1:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido. Solo números.\nEjemplo: 50000"); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v
            if referencia_manual_mode.get(user_id):
                data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id):
                data["step"] = 2; await update.message.reply_text("📅 Fecha:"); return
            await _gen_transfiya(update, data, v)
        elif step == 2:
            data["fecha_manual"] = text; await _gen_transfiya(update, data, data["valor"])
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            await _gen_transfiya(update, data, data["valor"])
        elif step == 11:
            data["fecha_manual"] = text; await _gen_transfiya(update, data, data["valor"])

    # ─────────────────────────────────────────
    # COMPROBANTE QR — NEQUI QR
    # ─────────────────────────────────────────
    elif tipo == "comprobante_qr":
        if step == 0:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Ingresa el nombre del negocio:"); return
            data["nombre"] = nombre; data["step"] = 1
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 1:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido. Solo números.\nEjemplo: 50000"); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v
            if referencia_manual_mode.get(user_id):
                data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id):
                data["step"] = 2; await update.message.reply_text("📅 Fecha:"); return
            await _gen_nequi_qr(update, data, v)
        elif step == 2:
            data["fecha_manual"] = text; await _gen_nequi_qr(update, data, data["valor"])
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            await _gen_nequi_qr(update, data, data["valor"])
        elif step == 11:
            data["fecha_manual"] = text; await _gen_nequi_qr(update, data, data["valor"])

    # ─────────────────────────────────────────
    # COMPROBANTE ANULADO
    # ─────────────────────────────────────────
    elif tipo == "comprobante_anulado":
        if step == 0:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Intenta de nuevo:"); return
            data["nombre"] = nombre; data["step"] = 1
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 1:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor numérico. Ej: 50000"); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v
            if fecha_manual_mode.get(user_id):
                data["step"] = 2; await update.message.reply_text("📅 Fecha:"); return
            await _gen_anulado(update, data)
        elif step == 2:
            data["fecha_manual"] = text; await _gen_anulado(update, data)

    # ─────────────────────────────────────────
    # COMPROBANTE AHORROS  ✅ CON SMS
    # ─────────────────────────────────────────
    elif tipo == "comprobante_ahorros":
        if step == 0:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Intenta de nuevo:"); return
            data["nombre"] = nombre; data["step"] = 1
            await update.message.reply_text("🔢 Ingresa el *número de cuenta* (11 dígitos):", parse_mode="Markdown")
        elif step == 1:
            digitos = "".join(c for c in text if c.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text("❌ La cuenta debe tener exactamente 11 dígitos"); return
            data["numero_cuenta"] = text; data["step"] = 2
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 2:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido. Solo números."); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v
            if fecha_manual_mode.get(user_id):
                data["step"] = 3; await update.message.reply_text("📅 Fecha:"); return
            await _gen_ahorros(update, data, COMPROBANTE_AHORROS_CONFIG, "Ahorros")
        elif step == 3:
            data["fecha_manual"] = text
            await _gen_ahorros(update, data, COMPROBANTE_AHORROS_CONFIG, "Ahorros")

    # ─────────────────────────────────────────
    # COMPROBANTE CORRIENTE  ✅ CON SMS
    # ─────────────────────────────────────────
    elif tipo == "comprobante_corriente":
        if step == 0:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Intenta de nuevo:"); return
            data["nombre"] = nombre; data["step"] = 1
            await update.message.reply_text("🔢 Ingresa el *número de cuenta* (11 dígitos):", parse_mode="Markdown")
        elif step == 1:
            digitos = "".join(c for c in text if c.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text("❌ La cuenta debe tener exactamente 11 dígitos"); return
            data["numero_cuenta"] = text; data["step"] = 2
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 2:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido. Solo números."); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v
            if fecha_manual_mode.get(user_id):
                data["step"] = 3; await update.message.reply_text("📅 Fecha:"); return
            await _gen_ahorros(update, data, COMPROBANTE_AHORROS2_CONFIG, "Corriente")
        elif step == 3:
            data["fecha_manual"] = text
            await _gen_ahorros(update, data, COMPROBANTE_AHORROS2_CONFIG, "Corriente")

    # ─────────────────────────────────────────
    # DAVIPLATA
    # ─────────────────────────────────────────
    elif tipo == "comprobante_daviplata":
        if step == 0:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Intenta de nuevo:"); return
            data["nombre"] = nombre; data["step"] = 1
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 1:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido."); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v; data["step"] = 2
            await update.message.reply_text("🔢 Ingresa los *4 dígitos* de la cuenta que ENVÍA:", parse_mode="Markdown")
        elif step == 2:
            if not text.isdigit() or len(text) != 4:
                await update.message.reply_text("❌ Exactamente 4 dígitos numéricos"); return
            data["recibe"] = text; data["step"] = 3
            await update.message.reply_text("🔢 Ingresa los *4 dígitos* de la cuenta que RECIBE:", parse_mode="Markdown")
        elif step == 3:
            if not text.isdigit() or len(text) != 4:
                await update.message.reply_text("❌ Exactamente 4 dígitos numéricos"); return
            data["envia"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 4; await update.message.reply_text("📅 Fecha:"); return
            await _gen_daviplata(update, data)
        elif step == 4:
            data["fecha_manual"] = text; await _gen_daviplata(update, data)

    # ─────────────────────────────────────────
    # BC a NQ
    # ─────────────────────────────────────────
    elif tipo == "comprobante_bc_nq_t":
        if step == 0:
            tel = parse_tel(text)
            if not tel:
                await update.message.reply_text("❌ Número inválido. 10 dígitos, empieza en 3.\nEjemplo: 3001234567"); return
            data["telefono"] = tel; data["step"] = 1
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 1:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido."); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v
            if fecha_manual_mode.get(user_id):
                data["step"] = 2; await update.message.reply_text("📅 Fecha:"); return
            await _gen_bc_nq(update, data, v)
        elif step == 2:
            data["fecha_manual"] = text; await _gen_bc_nq(update, data, data["valor"])

    # ─────────────────────────────────────────
    # BC QR
    # ─────────────────────────────────────────
    elif tipo == "comprobante_bc_qr":
        if step == 0:
            if not text or len(text.strip()) < 2:
                await update.message.reply_text("❌ Descripción muy corta. Intenta de nuevo:"); return
            data["descripcion_qr"] = text; data["step"] = 1
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 1:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido."); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v; data["step"] = 2
            await update.message.reply_text("👤 Ingresa el *nombre*:", parse_mode="Markdown")
        elif step == 2:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Intenta de nuevo:"); return
            data["nombre"] = nombre; data["step"] = 3
            await update.message.reply_text("🔢 Ingresa el *número de cuenta* (11 dígitos):", parse_mode="Markdown")
        elif step == 3:
            digitos = "".join(c for c in text if c.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text("❌ La cuenta debe tener exactamente 11 dígitos"); return
            data["numero_cuenta"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 4; await update.message.reply_text("📅 Fecha:"); return
            await _gen_bc_qr(update, data)
        elif step == 4:
            data["fecha_manual"] = text; await _gen_bc_qr(update, data)

    # ─────────────────────────────────────────
    # NEQUI → CORRIENTE BC  ✅ CON SMS
    # ─────────────────────────────────────────
    elif tipo == "comprobante_nequi_bc":
        if step == 0:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Intenta de nuevo:"); return
            data["nombre"] = nombre; data["step"] = 1
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 1:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido."); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v; data["step"] = 2
            await update.message.reply_text("🔢 Ingresa el *número de cuenta* (11 dígitos):", parse_mode="Markdown")
        elif step == 2:
            digitos = "".join(c for c in text if c.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text("❌ La cuenta debe tener exactamente 11 dígitos"); return
            data["numero_cuenta"] = text
            if referencia_manual_mode.get(user_id):
                data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id):
                data["step"] = 3; await update.message.reply_text("📅 Fecha:"); return
            await _gen_nequi_bc(update, data)
        elif step == 3:
            data["fecha_manual"] = text; await _gen_nequi_bc(update, data)
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            await _gen_nequi_bc(update, data)
        elif step == 11:
            data["fecha_manual"] = text; await _gen_nequi_bc(update, data)

    # ─────────────────────────────────────────
    # NEQUI → AHORROS BC  ✅ CON SMS
    # ─────────────────────────────────────────
    elif tipo == "comprobante_nequi_ahorros":
        if step == 0:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Intenta de nuevo:"); return
            data["nombre"] = nombre; data["step"] = 1
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 1:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor inválido."); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v; data["step"] = 2
            await update.message.reply_text("🔢 Ingresa el *número de cuenta* (11 dígitos):", parse_mode="Markdown")
        elif step == 2:
            digitos = "".join(c for c in text if c.isdigit())
            if len(digitos) != 11:
                await update.message.reply_text("❌ La cuenta debe tener exactamente 11 dígitos"); return
            data["numero_cuenta"] = text
            if referencia_manual_mode.get(user_id):
                data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id):
                data["step"] = 3; await update.message.reply_text("📅 Fecha:"); return
            await _gen_nequi_ahorros(update, data)
        elif step == 3:
            data["fecha_manual"] = text; await _gen_nequi_ahorros(update, data)
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            await _gen_nequi_ahorros(update, data)
        elif step == 11:
            data["fecha_manual"] = text; await _gen_nequi_ahorros(update, data)

    # ─────────────────────────────────────────
    # BRE B (COMPROBANTE NUEVO)
    # ─────────────────────────────────────────
    elif tipo == "comprobante_nuevo":
        if step == 0:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Intenta de nuevo:"); return
            data["nombre"] = nombre; data["step"] = 1
            await update.message.reply_text("💰 Ingresa el *valor* (ej: 50000):", parse_mode="Markdown")
        elif step == 1:
            try: v = parse_valor(text)
            except: await update.message.reply_text("❌ Valor numérico. Ej: 50000"); return
            if v < 1000: await update.message.reply_text("❌ Mínimo $1,000"); return
            data["valor"] = v; data["step"] = 2
            await update.message.reply_text("🔑 Ingresa la *llave*:", parse_mode="Markdown")
        elif step == 2:
            if not text or len(text.strip()) < 1:
                await update.message.reply_text("❌ Llave inválida. Intenta de nuevo:"); return
            data["llave"] = text; data["step"] = 3
            await update.message.reply_text("🏦 Ingresa el *banco*:", parse_mode="Markdown")
        elif step == 3:
            if not text or len(text.strip()) < 1:
                await update.message.reply_text("❌ Banco inválido. Intenta de nuevo:"); return
            data["banco"] = text; data["step"] = 4
            await update.message.reply_text("📱 Ingresa el *número de quien envía* (10 dígitos, empieza en 3):", parse_mode="Markdown")
        elif step == 4:
            tel = parse_tel(text)
            if not tel:
                await update.message.reply_text("❌ Número inválido. 10 dígitos, empieza en 3.\nEjemplo: 3001234567"); return
            data["numero_envia"] = tel
            if referencia_manual_mode.get(user_id):
                data["step"] = 10; await update.message.reply_text("🔢 Referencia:"); return
            if fecha_manual_mode.get(user_id):
                data["step"] = 5; await update.message.reply_text("📅 Fecha:"); return
            await _gen_nuevo(update, data)
        elif step == 5:
            data["fecha_manual"] = text; await _gen_nuevo(update, data)
        elif step == 10:
            data["referencia_manual"] = text
            if fecha_manual_mode.get(user_id):
                data["step"] = 11; await update.message.reply_text("📅 Fecha:"); return
            await _gen_nuevo(update, data)
        elif step == 11:
            data["fecha_manual"] = text; await _gen_nuevo(update, data)

    # ─────────────────────────────────────────
    # AGREGAR USUARIO (flujo admin)
    # ─────────────────────────────────────────
    elif tipo == "agregar_usuario":
        if step == 0:
            if not text.isdigit():
                await update.message.reply_text("❌ ID debe ser numérico. Ingresa el ID de Telegram:"); return
            data["target_user_id"] = int(text); data["step"] = 1
            await update.message.reply_text("📝 Nombre del usuario:")
        elif step == 1:
            nombre = parse_nombre(text)
            if not nombre:
                await update.message.reply_text("❌ Nombre inválido. Intenta de nuevo:"); return
            data["nombre"] = nombre; data["step"] = 2
            await update.message.reply_text("📅 ¿Cuántos días de acceso? (Ejemplo: 30)")
        elif step == 2:
            if not text.isdigit():
                await update.message.reply_text("❌ Número de días debe ser numérico. Ej: 30"); return
            dias = int(text)
            if dias < 1:
                await update.message.reply_text("❌ Mínimo 1 día."); return
            try:
                auth_system.add_user(data["target_user_id"], data["nombre"])
                fv  = agregar_vencimiento(data["target_user_id"], data["nombre"], dias)
                sms = asignar_sms_por_dias(data["target_user_id"], dias)
                now = datetime.now(pytz.timezone("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S")
                await update.message.reply_text(
                    f"✅ *Usuario Agregado*\n\n👤 ID: `{data['target_user_id']}`\n📝 Nombre: {data['nombre']}\n"
                    f"📅 Vence: {fv}\n⏳ Días: {dias}\n📲 SMS asignados: {sms}\n🕐 {now}\n\n"
                    f"💡 Para autorizar SMS usa:\n`/autorizarsms {data['target_user_id']}`",
                    parse_mode='Markdown')
                try:
                    await context.bot.send_message(chat_id=data["target_user_id"], parse_mode="Markdown",
                        text=f"✅ *¡Acceso Activado!*\n\nHola {data['nombre']}, tu acceso ha sido activado.\n\n"
                             f"📅 Vence: *{fv}*\n⏳ Duración: *{dias} días*\n📲 SMS disponibles: *{sms}*\n\n"
                             f"Usa /comprobante para empezar.")
                except: pass
                if user_id != ADMIN_ID:
                    await context.bot.send_message(chat_id=ADMIN_ID, parse_mode='Markdown',
                        text=f"🔔 *Nuevo VIP agregado*\nID: `{data['target_user_id']}`\nNombre: {data['nombre']}\n"
                             f"Vence: {fv}\nSMS: {sms}\nPor: {data.get('admin_name','Admin')}")
                del user_data_store[user_id]
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}")
                if user_id in user_data_store: del user_data_store[user_id]

# ═══════════════════════════════════════════════
# GENERADORES
# ═══════════════════════════════════════════════
async def _gen_nequi(update, data, v):
    data["step"] = "generando"
    try:
        out = generar_comprobante(data, COMPROBANTE1_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption=" ")
        os.remove(out)
        dm = data.copy()
        dm["nombre"] = (data.get("nombre") or "").upper()
        dm["valor"]  = -abs(v)
        out2 = generar_comprobante(dm, COMPROBANTE_MOVIMIENTO_CONFIG)
        with open(out2,"rb") as f: await update.message.reply_document(document=f, caption=" ")
        os.remove(out2)
        await send_success_message(update, sms_data={"telefono": data.get("telefono"), "valor": v})
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_transfiya(update, data, v):
    data["step"] = "generando"
    try:
        out = generar_comprobante(data, COMPROBANTE4_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption=" ")
        os.remove(out)
        tel = data.get("telefono") or ""
        dm2 = {"telefono": tel, "valor": -abs(v), "nombre": tel}
        out2 = generar_comprobante(dm2, COMPROBANTE_MOVIMIENTO2_CONFIG)
        with open(out2,"rb") as f: await update.message.reply_document(document=f, caption=" ")
        os.remove(out2)
        await send_success_message(update, sms_data={"telefono": data.get("telefono"), "valor": v})
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_nequi_qr(update, data, v):
    data["step"] = "generando"
    try:
        out = generar_comprobante(data, COMPROBANTE_QR_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption=" ")
        os.remove(out)
        dm = {"nombre": (data.get("nombre") or "").upper(), "valor": -abs(v)}
        out2 = generar_comprobante(dm, COMPROBANTE_MOVIMIENTO3_CONFIG)
        with open(out2,"rb") as f: await update.message.reply_document(document=f, caption=" ")
        os.remove(out2)
        await send_success_message(update)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_anulado(update, data):
    data["step"] = "generando"
    try:
        out = generar_comprobante_anulado(data, COMPROBANTE_ANULADO_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption="ANULADO")
        os.remove(out)
        await send_success_message(update)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_ahorros(update, data, config, caption):
    data["step"] = "generando"
    try:
        out = generar_comprobante_ahorros(data, config)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption=caption)
        os.remove(out)
        # ✅ Usa sms_tel si existe
        sms_data = None
        if data.get("sms_tel"):
            sms_data = {"telefono": data["sms_tel"], "valor": data.get("valor", 0)}
        await send_success_message(update, sms_data=sms_data)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_daviplata(update, data):
    data["step"] = "generando"
    try:
        out = generar_comprobante_daviplata(data, COMPROBANTE_DAVIPLATA_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption="Daviplata")
        os.remove(out)
        await send_success_message(update)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_bc_nq(update, data, v):
    data["step"] = "generando"
    try:
        out = generar_comprobante_bc_nq_t(data, COMPROBANTE_BC_NQ_T_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption="BC a NQ")
        os.remove(out)
        await send_success_message(update, sms_data={"telefono": data.get("telefono"), "valor": v})
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_bc_qr(update, data):
    data["step"] = "generando"
    try:
        out = generar_comprobante_bc_qr(data, COMPROBANTE_BC_QR_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption="BC QR")
        os.remove(out)
        await send_success_message(update)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_nequi_bc(update, data):
    data["step"] = "generando"
    try:
        out = generar_comprobante_nequi_bc(data, COMPROBANTE_NEQUI_BC_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption="Nequi Corriente")
        os.remove(out)
        # ✅ Usa sms_tel si existe
        sms_data = None
        if data.get("sms_tel"):
            sms_data = {"telefono": data["sms_tel"], "valor": data.get("valor", 0)}
        await send_success_message(update, sms_data=sms_data)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_nequi_ahorros(update, data):
    data["step"] = "generando"
    try:
        out = generar_comprobante_nequi_ahorros(data, COMPROBANTE_NEQUI_AHORROS_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption="Nequi Ahorros")
        os.remove(out)
        # ✅ Usa sms_tel si existe
        sms_data = None
        if data.get("sms_tel"):
            sms_data = {"telefono": data["sms_tel"], "valor": data.get("valor", 0)}
        await send_success_message(update, sms_data=sms_data)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

async def _gen_nuevo(update, data):
    data["step"] = "generando"
    try:
        out = generar_comprobante_nuevo(data, COMPROBANTE_NUEVO_CONFIG)
        with open(out,"rb") as f: await update.message.reply_document(document=f, caption=" ")
        os.remove(out)
        nombre_raw = data.get("nombre") or ""
        valor_raw  = data.get("valor", 0)
        try: valor_float = float(valor_raw)
        except (TypeError, ValueError): valor_float = 0.0
        dm = {"nombre": enmascarar_nombre(nombre_raw), "valor": -abs(valor_float)}
        out2 = generar_comprobante(dm, MVKEY_CONFIG)
        with open(out2,"rb") as f: await update.message.reply_document(document=f, caption=" ")
        os.remove(out2)
        await send_success_message(update)
    except Exception as e:
        await update.message.reply_text(f"❌ Error generando comprobante: {e}")
    finally:
        uid = update.effective_user.id
        if uid in user_data_store: del user_data_store[uid]

# ═══════════════════════════════════════════════
# COMANDOS ADMIN
# ═══════════════════════════════════════════════
async def gratis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    auth_system.set_gratis_mode(True)
    await update.message.reply_text("✅ Modo GRATIS activado.")
    await notify_main_admin(context, uid, update.effective_user.first_name, "Activó modo gratis")

async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    auth_system.set_gratis_mode(False)
    await update.message.reply_text("🔴 Modo OFF activado.")
    await notify_main_admin(context, uid, update.effective_user.first_name, "Desactivó modo gratis")

async def agregar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    user_data_store[uid] = {"step": 0, "tipo": "agregar_usuario", "admin_name": update.effective_user.first_name or "Admin"}
    await update.message.reply_text("👤 Ingresa el ID del usuario:")

async def eliminar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /eliminar <id>"); return
    try:
        tid = int(context.args[0]); auth_system.remove_user(tid); eliminar_vencimiento(tid)
        await update.message.reply_text(f"✅ Usuario {tid} eliminado.")
        await notify_main_admin(context, uid, update.effective_user.first_name, "Eliminó usuario", str(tid))
    except ValueError: await update.message.reply_text("❌ ID inválido.")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /ban <id>"); return
    try:
        tid = int(context.args[0]); auth_system.ban_user(tid)
        await update.message.reply_text(f"🚫 Usuario {tid} baneado.")
        await notify_main_admin(context, uid, update.effective_user.first_name, "Baneó usuario", str(tid))
    except ValueError: await update.message.reply_text("❌ ID inválido.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /unban <id>"); return
    try:
        tid = int(context.args[0]); auth_system.unban_user(tid)
        await update.message.reply_text(f"✅ Usuario {tid} desbaneado.")
    except ValueError: await update.message.reply_text("❌ ID inválido.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    s = auth_system.get_stats()
    a = cargar_sms_autorizados()
    await update.message.reply_text(
        f"📊 *Estadísticas*\n\n👥 Autorizados: {s['total_authorized']}\n"
        f"🚫 Baneados: {s['total_banned']}\n🛡️ Admins: {s['total_admins']}\n"
        f"🆓 Modo gratis: {'Sí' if s['gratis_mode'] else 'No'}\n"
        f"📲 Autorizados SMS: {len(a)}", parse_mode='Markdown')

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /admin <id>"); return
    try:
        tid = int(context.args[0]); auth_system.add_admin(tid)
        await update.message.reply_text(f"✅ {tid} es admin ahora.")
    except ValueError: await update.message.reply_text("❌ ID inválido.")

async def unadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not auth_system.is_admin(uid): await update.message.reply_text("❌ Solo admins."); return
    if not context.args: await update.message.reply_text("Uso: /unadmin <id>"); return
    try:
        tid = int(context.args[0]); auth_system.remove_admin(tid)
        await update.message.reply_text(f"✅ {tid} ya no es admin.")
    except ValueError: await update.message.reply_text("❌ ID inválido.")

async def cancelar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in user_data_store:
        del user_data_store[uid]
        await update.message.reply_text("✅ Operación cancelada. Usa /comprobante para iniciar.")
    else:
        await update.message.reply_text("No tienes acciones activas. Usa /comprobante para iniciar.")

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
# MAIN
# ═══════════════════════════════════════════════
def main():
    token = os.environ.get("BOT_TOKEN", "8720781455:AAEeVb3_5vnEMrHRkfEVbUN2Pr_lJaBBzDI").strip()
    if not token:
        raise ValueError("❌ BOT_TOKEN no está definido en las variables de entorno.")

    import asyncio, time
    # Esperar un poco para que la instancia anterior cierre su conexión con Telegram
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
    app.add_handler(CallbackQueryHandler(apk_precios_callback,  pattern="^apk_precios$"))
    app.add_handler(CallbackQueryHandler(referencias_callback,  pattern="^ref_next_"))
    app.add_handler(CallbackQueryHandler(panel_callback,        pattern="^panel_"))
    app.add_handler(CallbackQueryHandler(brqr_callback,         pattern="^brqr_"))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("🤖 Bot iniciado correctamente.")
    app.run_polling(drop_pending_updates=True, timeout=30, read_timeout=30, write_timeout=30, connect_timeout=30)

if __name__ == "__main__":
    main()
