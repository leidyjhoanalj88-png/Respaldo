commit -m "Agregar utils.py" git push origin main
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import pytz
import random
import uuid
import locale

try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Colombia.1252')
    except:
        pass


def draw_text_with_outline(draw, position, text, font, fill, outline_fill, outline_width):
    x, y = position
    draw.text((x, y), text, font=font, fill=fill)


def dibujar_valor_movimiento(draw, base_style, valor, font_path, ancho_imagen, decimal_style=None):
    valor_formateado = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    valor_str = f"-$ {valor_formateado}" if valor < 0 else f"$ {valor_formateado}"
    entero, decimal = valor_str[:-3], valor_str[-3:]

    pos_y = base_style["pos"][1]
    limite_izquierdo = 100
    limite_derecho = 580
    margen_derecho = 20

    size_entero = base_style["size"]
    size_decimal = int(size_entero * 0.75)

    font_entero = ImageFont.truetype(base_style.get("font", font_path), size_entero)
    font_decimal = ImageFont.truetype(decimal_style.get("font", font_path) if decimal_style else font_path, size_decimal)

    ancho_entero = draw.textlength(entero, font=font_entero)
    ancho_decimal = draw.textlength(decimal, font=font_decimal)

    while (ancho_entero + ancho_decimal) > (limite_derecho - limite_izquierdo - margen_derecho) and size_entero > 8:
        size_entero -= 1
        size_decimal = int(size_entero * 0.75)
        font_entero = ImageFont.truetype(base_style.get("font", font_path), size_entero)
        font_decimal = ImageFont.truetype(decimal_style.get("font", font_path) if decimal_style else font_path, size_decimal)
        ancho_entero = draw.textlength(entero, font=font_entero)
        ancho_decimal = draw.textlength(decimal, font=font_decimal)

    x_decimal = limite_derecho - margen_derecho
    x_entero = x_decimal - ancho_entero

    if x_entero < limite_izquierdo:
        x_entero = limite_izquierdo
        x_decimal = x_entero + ancho_entero

    x_entero -= 13
    x_decimal -= 13

    bbox_entero = font_entero.getbbox("0")
    bbox_decimal = font_decimal.getbbox("0")
    offset_y = bbox_entero[3] - bbox_decimal[3]
    decimal_y = pos_y + offset_y

    draw_text_with_outline(draw, (x_entero, pos_y), entero, font_entero, base_style["color"], "white", 2)
    draw.text((x_decimal, decimal_y), decimal, font=font_decimal,
              fill=decimal_style.get("color", base_style["color"]) if decimal_style else base_style["color"])


def formatear_telefono_co(numero: str) -> str:
    if not numero:
        return ""
    digitos = "".join(ch for ch in numero if ch.isdigit())
    if digitos.startswith("57") and len(digitos) == 12:
        digitos = digitos[2:]
    if len(digitos) == 10:
        return f"{digitos[:3]} {digitos[3:6]} {digitos[6:]}"
    return numero


def enmascarar_nombre(nombre: str) -> str:
    if not nombre:
        return ""
    partes = nombre.split()
    partes_mask = []
    for palabra in partes:
        if len(palabra) <= 3:
            partes_mask.append(palabra + "***")
        else:
            visibles = palabra[:3]
            partes_mask.append(visibles + "***")
    return " ".join(partes_mask)


def generar_comprobante(data, config):
    template_path = config["template"]
    output_path = f"gen_{uuid.uuid4().hex}.png"
    styles = config["styles"]
    font_path = config["font"]

    image = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    tipo_movimiento = "valor1" in styles and "nombre" in styles and "valor_decimal" in styles
    es_comprobante_qr = config["output"] == "comprobante_qr_generado.png"
    es_comprobante4 = config["output"] == "comprobante4_generado.png"

    if tipo_movimiento:
        decimal_style = styles.get("valor_decimal")
        dibujar_valor_movimiento(draw, styles["valor1"], data["valor"], font_path, image.width, decimal_style)
        font_nombre = ImageFont.truetype(styles["nombre"].get("font", font_path), styles["nombre"]["size"])
        draw_text_with_outline(draw, styles["nombre"]["pos"], data["nombre"], font_nombre, styles["nombre"]["color"], "white", 2)
    else:
        if "fecha_manual" in data and data["fecha_manual"]:
            fecha = data["fecha_manual"]
        else:
            meses_es = {
                "january": "enero", "february": "febrero", "march": "marzo", "april": "abril",
                "may": "mayo", "june": "junio", "july": "julio", "august": "agosto",
                "september": "septiembre", "october": "octubre", "november": "noviembre", "december": "diciembre"
            }
            now = datetime.now(pytz.timezone("America/Bogota"))
            mes_en = now.strftime("%B").lower()
            mes = meses_es.get(mes_en, mes_en)
            fecha = now.strftime(f"%d de {mes} de %Y a las %I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")

        if "referencia_manual" in data and data["referencia_manual"]:
            referencia = data["referencia_manual"]
        else:
            referencia = f"M{random.randint(10000000, 99999999)}"

        valor_formateado = "$ {:,.2f}".format(data["valor"]).replace(",", "X").replace(".", ",").replace("X", ".")

        telefono_raw = data.get("telefono", "")
        telefono_formateado = (
            telefono_raw if es_comprobante4 or es_comprobante_qr else
            f"{telefono_raw[:3]} {telefono_raw[3:6]} {telefono_raw[6:]}" if telefono_raw.isdigit() and len(telefono_raw) == 10 else telefono_raw
        )

        datos = {
            "telefono": telefono_formateado,
            "nombre": data.get("nombre", ""),
            "valor1": valor_formateado,
            "fecha": fecha,
            "referencia": referencia,
            "disponible": "Disponible",
        }

        if es_comprobante_qr:
            datos = {
                "nombre": data.get("nombre", ""),
                "valor1": valor_formateado,
                "fecha": fecha,
                "referencia": referencia,
                "disponible": "Disponible",
            }

        for campo, texto in datos.items():
            if campo in styles:
                style = styles[campo]
                font = ImageFont.truetype(font_path, style["size"])
                draw_text_with_outline(draw, style["pos"], str(texto), font, style["color"], "#2e2b33", 2)

    image.save(output_path)
    return output_path


def generar_comprobante_nuevo(data, config):
    template_path = config["template"]
    output_path = f"gen_{uuid.uuid4().hex}.png"
    styles = config["styles"]
    font_path = config["font"]

    image = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    if "fecha_manual" in data and data["fecha_manual"]:
        fecha = data["fecha_manual"]
    else:
        try:
            meses_es = {
                "january": "enero", "february": "febrero", "march": "marzo", "april": "abril",
                "may": "mayo", "june": "junio", "july": "julio", "august": "agosto",
                "september": "septiembre", "october": "octubre", "november": "noviembre", "december": "diciembre"
            }
            now = datetime.now(pytz.timezone("America/Bogota"))
            mes_en = now.strftime("%B").lower()
            mes = meses_es.get(mes_en, mes_en)
            fecha = now.strftime(f"%d de {mes} de %Y a las %I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")
        except Exception:
            fecha = ""

    if "referencia_manual" in data and data["referencia_manual"]:
        referencia = data["referencia_manual"]
    else:
        referencia = f"M{random.randint(1000000, 9999999)}"

    valor_formateado = "$ {:,.2f}".format(float(data.get("valor", 0))).replace(",", "X").replace(".", ",").replace("X", ".")
    numero_envia_fmt = formatear_telefono_co(data.get("numero_envia", ""))
    nombre_mask = enmascarar_nombre(data.get("nombre", ""))

    datos = {
        "nombre": nombre_mask,
        "valor1": valor_formateado,
        "llave": data.get("llave", ""),
        "banco": data.get("banco", ""),
        "numero_envia": numero_envia_fmt,
        "fecha": fecha,
        "referencia": referencia,
        "disponible": "Disponible",
    }

    for campo, texto in datos.items():
        if campo in styles:
            style = styles[campo]
            font = ImageFont.truetype(font_path, style.get("size", 22))
            draw_text_with_outline(draw, style["pos"], str(texto), font, style.get("color", "#2e2b33"), "white", 2)

    image.save(output_path)
    return output_path


def generar_comprobante_anulado(data, config):
    return generar_comprobante(data, config)


def formatear_nombre_ahorros(nombre: str) -> str:
    if not nombre:
        return ""
    return nombre.title()


def formatear_numero_cuenta_ahorros(numero: str) -> str:
    if not numero:
        return ""
    digitos = "".join(ch for ch in numero if ch.isdigit())
    if len(digitos) != 11:
        return numero
    return f"{digitos[:3]} - {digitos[3:9]} - {digitos[9:]}"


def formatear_valor_ahorros(valor_str: str) -> str:
    if not valor_str:
        return ""
    valor_limpio = valor_str.replace(".", "").replace(",", "").replace(" ", "").replace("$", "")
    try:
        valor = int(valor_limpio)
        return f"$ {valor:,}".replace(",", ".")
    except ValueError:
        return valor_str


def formatear_valor_sin_signo(valor_str: str) -> str:
    if not valor_str:
        return ""
    valor_limpio = valor_str.replace(".", "").replace(",", "").replace(" ", "").replace("$", "")
    try:
        valor = int(valor_limpio)
        return f"{valor:,}".replace(",", ".")
    except ValueError:
        return valor_str


def generar_fecha_ahorros() -> str:
    try:
        meses_abrev = {
            1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Sept", 10: "Oct", 11: "Nov", 12: "Dic"
        }
        now = datetime.now(pytz.timezone("America/Bogota"))
        dia = now.strftime("%d")
        mes = meses_abrev[now.month]
        año = now.year
        hora = now.strftime("%I:%M").lstrip("0")
        periodo = "a. m." if now.hour < 12 else "p. m."
        return f"{dia} {mes} {año} - {hora} {periodo}"
    except Exception:
        return ""


def generar_fecha_bc_qr() -> str:
    try:
        meses_abrev = {
            1: "ene.", 2: "feb.", 3: "mar.", 4: "abr.", 5: "may.", 6: "jun.",
            7: "jul.", 8: "ago.", 9: "sept.", 10: "oct.", 11: "nov.", 12: "dic."
        }
        now = datetime.now(pytz.timezone("America/Bogota"))
        dia = now.strftime("%d")
        mes = meses_abrev[now.month]
        año = now.year
        hora = now.strftime("%I:%M").lstrip("0")
        periodo = "a. m." if now.hour < 12 else "p. m."
        return f"{dia} {mes} {año} - {hora} {periodo}"
    except Exception:
        return ""


def generar_comprobante_ahorros(data, config):
    template_path = config["template"]
    output_path = f"gen_{uuid.uuid4().hex}.png"
    styles = config["styles"]
    font_path = config["font"]

    image = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    nombre_formateado = formatear_nombre_ahorros(data.get("nombre", ""))
    numero_cuenta_formateado = formatear_numero_cuenta_ahorros(data.get("numero_cuenta", ""))
    valor_formateado = formatear_valor_ahorros(str(data.get("valor", "")))

    if "fecha_manual" in data and data["fecha_manual"]:
        fecha_formateada = data["fecha_manual"]
    else:
        fecha_formateada = generar_fecha_ahorros()

    datos = {
        "nombre": nombre_formateado,
        "numero_cuenta": numero_cuenta_formateado,
        "valor": valor_formateado,
        "fecha": fecha_formateada,
    }

    for campo, texto in datos.items():
        if campo in styles:
            style = styles[campo]
            fuente_campo = style.get("font", font_path)
            font = ImageFont.truetype(fuente_campo, style["size"])
            draw.text(style["pos"], str(texto), font=font, fill=style["color"])

    image.save(output_path)
    return output_path


def generar_comprobante_daviplata(data, config):
    template_path = config["template"]
    output_path = f"gen_{uuid.uuid4().hex}.png"
    styles = config["styles"]
    font_path = config["font"]

    image = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    if "fecha_manual" in data and data["fecha_manual"]:
        fecha_formateada = data["fecha_manual"]
    else:
        now = datetime.now(pytz.timezone("America/Bogota"))
        fecha_formateada = now.strftime("%d/%m/%Y - %I:%M %p")

    numero_aprobacion = str(random.randint(100000, 999999))
    valor_formateado = f"{data.get('valor', 0):,}".replace(",", ".")

    datos = {
        "nombre": data.get("nombre", ""),
        "recibe": data.get("recibe", ""),
        "valor": valor_formateado,
        "envia": data.get("envia", ""),
        "fecha": fecha_formateada,
        "aprobacion": numero_aprobacion,
    }

    for campo, texto in datos.items():
        if campo in styles:
            style = styles[campo]
            fuente_campo = style.get("font", font_path)
            font = ImageFont.truetype(fuente_campo, style["size"])
            draw.text(style["pos"], str(texto), font=font, fill=style["color"])

    image.save(output_path)
    return output_path


def generar_comprobante_bc_nq_t(data, config):
    template_path = config["template"]
    output_path = f"gen_{uuid.uuid4().hex}.png"
    styles = config["styles"]
    font_path = config["font"]

    image = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    numero_cuenta_formateado = formatear_numero_cuenta_ahorros(data.get("telefono", ""))
    valor_formateado = formatear_valor_sin_signo(str(data.get("valor", "")))

    if "fecha_manual" in data and data["fecha_manual"]:
        fecha_formateada = data["fecha_manual"]
    else:
        fecha_formateada = generar_fecha_ahorros()

    datos = {
        "numero_cuenta": numero_cuenta_formateado,
        "valor": valor_formateado,
        "fecha": fecha_formateada,
    }

    for campo, texto in datos.items():
        if campo in styles:
            style = styles[campo]
            fuente_campo = style.get("font", font_path)
            font = ImageFont.truetype(fuente_campo, style["size"])
            draw.text(style["pos"], str(texto), font=font, fill=style["color"])

    image.save(output_path)
    return output_path


def generar_comprobante_bc_qr(data, config):
    template_path = config["template"]
    output_path = f"gen_{uuid.uuid4().hex}.png"
    styles = config["styles"]

    image = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    descripcion_qr = data.get("descripcion_qr", "").upper()

    valor_raw = str(data.get("valor", "")).replace(".", "").replace(",", "").replace(" ", "")
    if valor_raw.isdigit():
        valor_num = int(valor_raw)
        valor = f"$ {valor_num:,}".replace(",", ".")
    else:
        valor = "$ " + str(data.get("valor", ""))

    nombre = data.get("nombre", "").upper()

    numero_cuenta_raw = data.get("numero_cuenta", "").replace(" ", "").replace("-", "")
    if len(numero_cuenta_raw) >= 11:
        numero_cuenta = f"{numero_cuenta_raw[:3]} - {numero_cuenta_raw[3:9]} - {numero_cuenta_raw[9:11]}"
    else:
        numero_cuenta = data.get("numero_cuenta", "")

    if "fecha_manual" in data and data["fecha_manual"]:
        fecha = data["fecha_manual"]
    else:
        fecha = generar_fecha_bc_qr()

    datos = {
        "punto_venta": descripcion_qr,
        "valor": valor,
        "nombre_enmascarado": nombre,
        "codigo_comercio": numero_cuenta,
        "fecha": fecha,
    }

    for campo, texto in datos.items():
        if campo in styles:
            style = styles[campo]
            fuente_campo = style.get("font")
            font = ImageFont.truetype(fuente_campo, style["size"])
            draw.text(style["pos"], str(texto), font=font, fill=style["color"])

    image.save(output_path)
    return output_path


def generar_comprobante_nequi_bc(data, config):
    template_path = config["template"]
    output_path = f"gen_{uuid.uuid4().hex}.png"
    styles = config["styles"]
    font_path = config["font"]

    image = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    valor_formateado = "$ {:,.2f}".format(float(data.get("valor", 0))).replace(",", "X").replace(".", ",").replace("X", ".")
    numero_cuenta = data.get("numero_cuenta", "")
    nombre = data.get("nombre", "")
    banco = data.get("banco", "")

    if "fecha_manual" in data and data["fecha_manual"]:
        fecha = data["fecha_manual"]
    else:
        meses_es = {
            "january": "enero", "february": "febrero", "march": "marzo", "april": "abril",
            "may": "mayo", "june": "junio", "july": "julio", "august": "agosto",
            "september": "septiembre", "october": "octubre", "november": "noviembre", "december": "diciembre"
        }
        now = datetime.now(pytz.timezone("America/Bogota"))
        mes_en = now.strftime("%B").lower()
        mes = meses_es.get(mes_en, mes_en)
        fecha = now.strftime(f"%d de {mes} de %Y a las %I:%M %p").lower().replace("am", "a. m.").replace("pm", "p. m.")

    if "referencia_manual" in data and data["referencia_manual"]:
        referencia = data["referencia_manual"]
    else:
        referencia = f"M{random.randint(10000000, 99999999)}"

    datos = {
        "nombre": nombre,
        "valor": valor_formateado,
        "fecha": fecha,
        "banco": banco,
        "numero_cuenta": numero_cuenta,
        "referencia": referencia,
        "disponible": "Disponible",
    }

    for campo, texto in datos.items():
        if campo in styles:
            style = styles[campo]
            font = ImageFont.truetype(font_path, style["size"])
            draw_text_with_outline(draw, style["pos"], str(texto), font, style["color"], "#2e2b33", 2)

    image.save(output_path)
    return output_path


def generar_comprobante_nequi_ahorros(data, config):
    return generar_comprobante_nequi_bc(data, config)


def generar_movimiento_bancolombia(data, config):
    template_path = config["template"]
    output_path = f"gen_{uuid.uuid4().hex}.png"
    styles = config["styles"]
    font_path = config["font"]

    image = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    if "fecha_manual" in data and data["fecha_manual"]:
        fecha = data["fecha_manual"]
    else:
        now = datetime.now(pytz.timezone("America/Bogota"))
        fecha = now.strftime("%d/%m/%Y %I:%M %p")

    valor_raw = str(data.get("valor", "")).replace(".", "").replace(",", "").replace(" ", "").replace("$", "")
    if valor_raw.lstrip("-").isdigit():
        valor_num = int(valor_raw)
        valor = f"-$ {abs(valor_num):,}".replace(",", ".") if valor_num < 0 else f"$ {valor_num:,}".replace(",", ".")
    else:
        valor = str(data.get("valor", ""))

    datos = {
        "valor": valor,
        "fecha": fecha,
        "nombre": data.get("nombre", ""),
    }

    for campo, texto in datos.items():
        if campo in styles:
            style = styles[campo]
            fuente_campo = style.get("font", font_path)
            font = ImageFont.truetype(fuente_campo, style["size"])
            draw.text(style["pos"], str(texto), font=font, fill=style["color"])

    image.save(output_path)
    return output_path
