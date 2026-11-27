"""Cotización en PDF de un presupuesto (ReportLab, generada en el servidor).

EN SIMPLE
    Arma la "cotización impresa" que se le entrega al cliente: título, logo,
    número y fecha, datos de la empresa y del cliente, la tabla de ítems, los
    totales (costo directo, GG, utilidad, neto, IVA, total) y espacio para
    firmas. Se hace en dos pasos: primero se juntan los datos, luego se dibujan.

TÉCNICO
    ReportLab "platypus": se arma una lista de bloques (Flowables: Table,
    Paragraph, Spacer, Image...) llamada `historia`, y doc.build() los coloca
    en páginas tamaño carta, saltando de página cuando no caben.
    El PDF se escribe en memoria (BytesIO), no en disco.

El diseño sigue la cotización de referencia de SEFEL: encabezado con logo y
recuadro de número/fecha/validez, datos de empresa y cliente, tabla de ítems,
bloque de totales (costo directo, GG, utilidad, neto, IVA, total),
consideraciones y firmas.

datosCotizacion() junta los datos (fácil de testear) y generarPdfCotizacion()
solo dibuja.
"""
import os
from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlmodel import Session, select

from app.core.config import DATOS_EMPRESA, VALIDEZ_COTIZACION_DIAS
from app.models.apu import APU
from app.models.detalle_presupuesto import DetallePresupuesto
from app.models.presupuesto import Presupuesto
from app.templates import BASE_DIR

LOGO = os.path.join(BASE_DIR, "static", "img", "logo_sefel.png")

GRIS = colors.HexColor("#E3E3E3")
NEGRO = colors.black
ANCHO_UTIL = letter[0] - 3 * cm   # márgenes de 1,5 cm


# Datos
# ==========================================

def datosCotizacion(
    session: Session, presupuesto: Presupuesto, fecha: date | None = None
) -> dict:
    """Reúne todo lo que muestra la cotización.

    Los ítems usan el costo real, que es la base sobre la que se calculan los
    porcentajes; así la suma de la tabla coincide con el costo directo.
    """
    filas = session.exec(
        select(DetallePresupuesto, APU)
        .join(APU, APU.id == DetallePresupuesto.id_apu)
        .where(DetallePresupuesto.id_presupuesto == presupuesto.id_presupuesto)
        .order_by(DetallePresupuesto.id)
    ).all()

    items = [
        {
            "numero": numero,
            "descripcion": apu.name.upper(),
            "unidad": detalle.unit.upper(),
            "cantidad": detalle.cantidad,
            "valor_unitario": detalle.real_unit_cost,
            "valor_total": detalle.real_subtotal,
        }
        for numero, (detalle, apu) in enumerate(filas, start=1)
    ]

    return {
        "numero": presupuesto.id_presupuesto,
        "codigo": presupuesto.code,
        "fecha": fecha or date.today(),
        "validez_dias": VALIDEZ_COTIZACION_DIAS,
        "empresa": DATOS_EMPRESA,
        "cliente": {"nombre": presupuesto.client_name},
        "titulo_items": (presupuesto.description or "").upper(),
        "items": items,
        "totales": {
            "costo_directo": presupuesto.base_calculo,
            "pct_gastos_generales": presupuesto.pct_gastos_generales,
            "gastos_generales": presupuesto.monto_gastos_generales,
            "pct_utilidad": presupuesto.pct_utilidad,
            "utilidad": presupuesto.monto_utilidad,
            "neto": presupuesto.neto,
            "pct_iva": presupuesto.pct_iva,
            "iva": presupuesto.monto_iva,
            "total": presupuesto.monto_total,
        },
    }


def nombreArchivo(presupuesto: Presupuesto, fecha: date | None = None) -> str:
    """presupuesto-<id>-<aaaa-mm-dd>.pdf"""
    return f"presupuesto-{presupuesto.id_presupuesto}-{(fecha or date.today()).isoformat()}.pdf"


# Formato
# ==========================================

def _miles(valor: int | float) -> str:
    """1500000 -> '1.500.000' (separador de miles chileno)."""
    return f"{valor:,.0f}".replace(",", ".")


def _pct(valor: float) -> str:
    """19.5 -> '19,5%'; 19.0 -> '19%' (el formato :g quita decimales sobrantes)."""
    return f"{valor:g}".replace(".", ",") + "%"


def _estilo(nombre: str, **kwargs) -> ParagraphStyle:
    """Estilo de texto basado en Helvetica 8,5; kwargs cambia lo que se necesite."""
    base = {"fontName": "Helvetica", "fontSize": 8.5, "leading": 11}
    base.update(kwargs)
    return ParagraphStyle(nombre, **base)


ESTILO_TITULO = _estilo("titulo", fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=TA_CENTER)
ESTILO_MARCA = _estilo("marca", fontName="Times-Bold", fontSize=22, leading=24, alignment=TA_CENTER)
ESTILO_LEMA = _estilo("lema", fontName="Helvetica-Bold", fontSize=6, leading=8, alignment=TA_CENTER)
ESTILO = _estilo("normal")
ESTILO_NEGRITA = _estilo("negrita", fontName="Helvetica-Bold")
ESTILO_DATO = _estilo("dato", fontName="Helvetica-Oblique")


def _dato(etiqueta: str, valor: str) -> Paragraph:
    """Línea "Etiqueta: valor" con la etiqueta en negrita cursiva."""
    # Paragraph interpreta etiquetas: se escapan los datos ingresados por usuarios
    return Paragraph(f"<b><i>{etiqueta}</i></b> {escape(valor or '')}", ESTILO_DATO)


# Secciones
# ==========================================

def _encabezado(datos: dict) -> list:
    """Título "COTIZACIÓN", logo a la izquierda y recuadro gris con Nº/fecha/código/validez.

    Se maqueta como una tabla invisible de 2 filas x 3 columnas (la primera
    fila une sus 3 celdas con SPAN para el título). Si falta el logo, deja un
    espacio vacío en su lugar.
    """
    logo = [
        Image(LOGO, width=3.2 * cm, height=3.2 * cm * 365 / 794)
        if os.path.exists(LOGO) else Spacer(1, 1.2 * cm),
        Paragraph("SEFEL", ESTILO_MARCA),
        Paragraph("Ingeniería &amp; Construcción", ESTILO_LEMA),
    ]
    recuadro = Table(
        [
            [Paragraph(f"<b>Nº cotización: {datos['numero']}</b>", ESTILO)],
            [Paragraph(f"<b>Fecha: {datos['fecha'].strftime('%d-%m-%Y')}</b>", ESTILO)],
            [Paragraph(f"<b>Código: {escape(datos['codigo'])}</b>", ESTILO)],
            [Paragraph(f"<b>*COTIZACIÓN VÁLIDA POR {datos['validez_dias']} DÍAS</b>", ESTILO)],
        ],
        colWidths=[7 * cm],
    )
    recuadro.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS),
        ("LINEABOVE", (0, 3), (-1, 3), 0.8, NEGRO),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    cabecera = Table(
        [[Paragraph("C O T I Z A C I Ó N", ESTILO_TITULO), "", ""],
         [logo, "", recuadro]],
        colWidths=[5 * cm, ANCHO_UTIL - 12 * cm, 7 * cm],
    )
    cabecera.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("VALIGN", (0, 1), (-1, 1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [cabecera, Spacer(1, 0.4 * cm)]


def _datosEmpresaCliente(datos: dict) -> list:
    """Dos columnas: datos de la empresa (izquierda) y del cliente (derecha)."""
    empresa, cliente = datos["empresa"], datos["cliente"]
    filas = [
        [Paragraph("<b>Datos Empresa</b>", ESTILO), Paragraph("<b><i>Datos Cliente</i></b>", ESTILO)],
        [_dato("Nombre:", empresa["nombre"]), _dato("Nombre:", cliente.get("nombre", ""))],
        [_dato("Dirección:", empresa["direccion"]), _dato("Dirección:", cliente.get("direccion", ""))],
        [_dato("Rut.:", empresa["rut"]), _dato("Rut.:", cliente.get("rut", ""))],
        [_dato("Teléfono:", empresa["telefono"]), _dato("Teléfono:", cliente.get("telefono", ""))],
        [_dato("Mail:", empresa["mail"]), _dato("Correo:", cliente.get("correo", ""))],
    ]
    mitad = ANCHO_UTIL / 2
    tabla = Table(filas, colWidths=[mitad, mitad])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRIS),
        ("LEFTPADDING", (0, 0), (0, -1), 0.9 * cm),
        ("TOPPADDING", (0, 1), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 0),
    ]))
    return [tabla, Spacer(1, 0.6 * cm)]


def _tablaItems(datos: dict) -> list:
    """Tabla de ítems: Nº, descripción, unidad, cantidad, valor unitario y total.

    Coordenadas de TableStyle: (columna, fila); -1 = la última.
    El "$" va en una columna propia para que los montos queden alineados.
    repeatRows=1 repite el encabezado si la tabla pasa a otra página.
    La columna de descripción ocupa el ancho que sobra de las demás.
    """
    filas = [[
        Paragraph("<b>Item</b>", ESTILO), Paragraph("<b>Descripción</b>", ESTILO),
        Paragraph("<b>Unid.</b>", ESTILO), Paragraph("<b>Cantidad</b>", ESTILO),
        Paragraph("<b>Valor unit.</b>", ESTILO), "",
        Paragraph("<b>Valor total</b>", ESTILO), "",
    ]]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), GRIS),
        ("SPAN", (4, 0), (5, 0)),
        ("SPAN", (6, 0), (7, 0)),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (3, -1), "CENTER"),
        ("ALIGN", (5, 1), (5, -1), "RIGHT"),
        ("ALIGN", (7, 1), (7, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
    ]

    if datos["titulo_items"]:
        filas.append([Paragraph(f"<b>{escape(datos['titulo_items'])}</b>", ESTILO), "", "", "", "", "", "", ""])
        estilo.append(("SPAN", (0, 1), (4, 1)))

    for item in datos["items"]:
        filas.append([
            str(item["numero"]),
            Paragraph(f"<b>{escape(item['descripcion'])}</b>", ESTILO),
            item["unidad"],
            _miles(item["cantidad"]),
            "$", _miles(item["valor_unitario"]),
            "$", _miles(item["valor_total"]),
        ])

    if not datos["items"]:
        filas.append(["", Paragraph("<i>Sin ítems asignados.</i>", ESTILO), "", "", "", "", "", ""])

    anchos = [1.2 * cm, None, 1.4 * cm, 1.8 * cm, 0.5 * cm, 2 * cm, 0.5 * cm, 2.4 * cm]
    anchos[1] = ANCHO_UTIL - sum(a for a in anchos if a)
    tabla = Table(filas, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle(estilo))
    return [tabla, Spacer(1, 0.8 * cm)]


def _bloqueTotales(datos: dict) -> Table:
    """Recuadro gris de totales, alineado a la derecha de la página."""
    t = datos["totales"]
    filas = [
        ["COSTO DIRECTO", "", "$", _miles(t["costo_directo"])],
        ["GG", _pct(t["pct_gastos_generales"]), "$", _miles(t["gastos_generales"])],
        ["UTILIDAD", _pct(t["pct_utilidad"]), "$", _miles(t["utilidad"])],
        ["NETO", "", "$", _miles(t["neto"])],
        ["IVA", _pct(t["pct_iva"]), "$", _miles(t["iva"])],
        ["TOTAL", "", "$", _miles(t["total"])],
    ]
    anchos = [3 * cm, 1.6 * cm, 0.6 * cm, 3 * cm]
    tabla = Table(filas, colWidths=anchos)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-BoldOblique"),
        ("FONTNAME", (3, 0), (3, 2), "Helvetica-BoldOblique"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    # Alineado a la derecha, como en la cotización de referencia
    contenedor = Table([["", tabla]], colWidths=[ANCHO_UTIL - sum(anchos), sum(anchos)])
    contenedor.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return contenedor


def _consideracionesYFirmas() -> list:
    """Cuadro vacío de "Consideraciones" y dos espacios de firma (empresa / cliente)."""
    consideraciones = Table(
        [[Paragraph("<b><i>Consideraciones:</i></b>", ESTILO)]],
        colWidths=[ANCHO_UTIL], rowHeights=[2 * cm],
    )
    consideraciones.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    mitad = ANCHO_UTIL / 2
    firmas = Table(
        [[Paragraph("<b>Firma de la Empresa</b>", _estilo("f1", alignment=TA_CENTER)),
          Paragraph("<b>Firma del Cliente</b>", _estilo("f2", alignment=TA_CENTER))]],
        colWidths=[mitad, mitad], rowHeights=[3.6 * cm],
    )
    firmas.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    return [consideraciones, Spacer(1, 0.8 * cm), firmas]


def _pie(canvas, doc) -> None:
    """Número de página abajo a la derecha. ReportLab lo llama al dibujar cada página."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawRightString(letter[0] - 1.5 * cm, 1 * cm, f"Página {doc.page}")
    canvas.restoreState()


# PDF
# ==========================================

def generarPdfCotizacion(datos: dict) -> bytes:
    """Dibuja el PDF a partir del dict de datosCotizacion() y devuelve sus bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.2 * cm, bottomMargin=1.5 * cm,
        title=f"Cotización {datos['numero']} - {datos['codigo']}",
        author=datos["empresa"]["nombre"],
        creator="SEFEL",
    )
    historia = (
        _encabezado(datos)
        + _datosEmpresaCliente(datos)
        + _tablaItems(datos)
        # Totales, consideraciones y firmas no se separan entre páginas
        + [KeepTogether([_bloqueTotales(datos), Spacer(1, 1 * cm)] + _consideracionesYFirmas())]
    )
    doc.build(historia, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()


def generarPdfPresupuesto(session: Session, presupuesto: Presupuesto) -> bytes:
    """Atajo que usa el router: junta los datos y dibuja el PDF."""
    return generarPdfCotizacion(datosCotizacion(session, presupuesto))
