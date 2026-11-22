"""Reglas de validación compartidas entre backend y frontend.

Fuente única: los modelos de validación (APUValidacion, PresupuestoValidacion)
llaman a estas funciones en creación y edición, y las plantillas usan
REGLAS_HTML (registrada como global de Jinja) para los atributos pattern/min/max
de los formularios, así ambas capas no divergen.

Texto permitido: letras (con tildes, ñ y de cualquier alfabeto), números,
espacios, guion (-) y guion bajo (_). Cliente y nombre del presupuesto aceptan
además punto y coma, para razones sociales como "Constructora Andes Ltda." o
"Inmobiliaria Maule S.A.".
"""
import re
import unicodedata
from datetime import date, datetime

# Backend (re de Python): \w = letras y números Unicode + "_"
PATRON_TEXTO = re.compile(r"^[\w \-]+$")
PATRON_TEXTO_PUNTUACION = re.compile(r"^[\w \-.,]+$")

# Frontend (atributo pattern de HTML: regex de JavaScript con flag "v")
PATRON_HTML_TEXTO = r"[\p{L}\p{N}_ \-]+"
PATRON_HTML_TEXTO_PUNTUACION = r"[\p{L}\p{N}_ \-.,]+"

AYUDA_TEXTO = "Solo letras, números, espacios, guion (-) y guion bajo (_)."
AYUDA_TEXTO_PUNTUACION = (
    "Solo letras, números, espacios, guion (-), guion bajo (_), punto y coma."
)

# Periodo de los presupuestos
FECHA_INICIO_MINIMA = date(2026, 1, 1)
FECHA_TERMINO_MAXIMA = date(2500, 12, 31)


class ErrorValidacion(ValueError):
    """Regla incumplida; su mensaje ya está listo para mostrarse al usuario."""


def normalizarTexto(valor: str) -> str:
    """Quita espacios externos y une tildes escritas como dos caracteres (NFC)."""
    return unicodedata.normalize("NFC", valor).strip()


def validarTexto(valor: str, etiqueta: str, *, puntuacion: bool = False) -> str:
    """Devuelve el texto normalizado o lanza ErrorValidacion.

    `etiqueta` es el nombre del campo con artículo, p. ej. "El código".
    No valida vacíos: eso lo decide cada campo (obligatorio u opcional).
    """
    valor = normalizarTexto(valor)
    patron = PATRON_TEXTO_PUNTUACION if puntuacion else PATRON_TEXTO
    if valor and not patron.match(valor):
        ayuda = AYUDA_TEXTO_PUNTUACION if puntuacion else AYUDA_TEXTO
        raise ErrorValidacion(f"{etiqueta} tiene caracteres no permitidos. {ayuda}")
    return valor


def validarCodigo(valor: str) -> str:
    """Códigos de APU y presupuestos: mismas reglas de texto y siempre en MAYÚSCULAS.

    Se guarda en mayúsculas sin importar cómo se escriba ("pre-01" -> "PRE-01").
    """
    return validarTexto(valor, "El código").upper()


def _comoFecha(valor: date | datetime) -> date:
    return valor.date() if isinstance(valor, datetime) else valor


def validarFechaInicio(inicio: date | datetime | None) -> date | datetime:
    if inicio is None:
        raise ErrorValidacion("La fecha de inicio es obligatoria.")
    if _comoFecha(inicio) < FECHA_INICIO_MINIMA:
        raise ErrorValidacion(
            "La fecha de inicio no puede ser anterior al "
            f"{FECHA_INICIO_MINIMA.strftime('%d/%m/%Y')}."
        )
    return inicio


def validarFechaTermino(
    termino: date | datetime | None, inicio: date | datetime | None
) -> date | datetime:
    if termino is None:
        raise ErrorValidacion("La fecha de término es obligatoria.")
    if _comoFecha(termino) > FECHA_TERMINO_MAXIMA:
        raise ErrorValidacion(
            "La fecha de término no puede ser posterior al "
            f"{FECHA_TERMINO_MAXIMA.strftime('%d/%m/%Y')}."
        )
    if inicio is not None and _comoFecha(termino) < _comoFecha(inicio):
        raise ErrorValidacion(
            "La fecha de término no puede ser anterior a la fecha de inicio."
        )
    return termino


def mensajeDe(error: dict) -> str | None:
    """Mensaje de una ErrorValidacion dentro de un error de pydantic (o None)."""
    causa = (error.get("ctx") or {}).get("error")
    return str(causa) if isinstance(causa, ErrorValidacion) else None


# Para las plantillas: {{ REGLAS_HTML.texto.patron }}, {{ REGLAS_HTML.fecha_min }} ...
REGLAS_HTML = {
    "texto": {"patron": PATRON_HTML_TEXTO, "ayuda": AYUDA_TEXTO},
    "texto_puntuacion": {
        "patron": PATRON_HTML_TEXTO_PUNTUACION,
        "ayuda": AYUDA_TEXTO_PUNTUACION,
    },
    "fecha_min": FECHA_INICIO_MINIMA.isoformat(),
    "fecha_max": FECHA_TERMINO_MAXIMA.isoformat(),
}
