"""Bloqueo de cuentas por intentos fallidos de inicio de sesión y su auditoría.

Regla:
- Tras MAX_INTENTOS fallos seguidos la cuenta se desactiva (is_active = False)
  y solo un ADMIN puede reactivarla desde admin/users.
- Excepción: si la cuenta es el ÚNICO ADMIN activo no se desactiva; se reinicia
  el contador y se aplica un bloqueo temporal corto (BLOQUEO_TEMPORAL).

Atomicidad: la decisión "¿hay otro ADMIN activo?" va dentro del mismo UPDATE
que desactiva la cuenta. En SQLite un UPDATE toma el lock de escritura al
empezar, así que si dos admins fallan a la vez los UPDATE se ejecutan uno tras
otro y el segundo ya ve al primero desactivado: nunca quedan ambos fuera.
"""
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import func, or_, select, update
from sqlmodel import Session

from app.core.logging import configuracionLogging
from app.models.auditoria import AccionAuditoria, AuditoriaCuenta
from app.models.user import User, UserRole

logger = configuracionLogging()

MAX_INTENTOS = 5
BLOQUEO_TEMPORAL = timedelta(minutes=15)

MOTIVO_INTENTOS = f"{MAX_INTENTOS} intentos fallidos de inicio de sesión"
MENSAJE_DESACTIVADA = (
    "Tu cuenta ha sido desactivada. Contacta a un administrador para reactivarla."
)


class ResultadoIntento(str, Enum):
    FALLIDO = "FALLIDO"                    # aún quedan intentos
    DESACTIVADA = "DESACTIVADA"            # se alcanzó el máximo: cuenta desactivada
    BLOQUEO_TEMPORAL = "BLOQUEO_TEMPORAL"  # único ADMIN activo: bloqueo corto


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def _conZona(fecha: datetime) -> datetime:
    # SQLite devuelve datetimes sin zona; se guardan siempre en UTC
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def bloqueoTemporalRestante(usuario: User) -> timedelta | None:
    """Tiempo que falta del bloqueo temporal, o None si no hay bloqueo vigente."""
    if usuario.locked_until is None:
        return None
    restante = _conZona(usuario.locked_until) - ahora()
    return restante if restante > timedelta(0) else None


def registrarAuditoria(
    session: Session,
    usuario_id: int,
    accion: AccionAuditoria,
    motivo: str,
    actor_id: int | None = None,
) -> None:
    """Agrega un registro de auditoría (sin commit) y lo deja en el log."""
    session.add(AuditoriaCuenta(
        id_usuario=usuario_id, id_actor=actor_id, accion=accion, motivo=motivo,
    ))
    logger.warning(
        "Auditoría cuenta: usuario=%s accion=%s actor=%s motivo=%s",
        usuario_id, accion.value, actor_id or "sistema", motivo,
    )


def registrarIntentoFallido(session: Session, usuario_id: int) -> tuple[ResultadoIntento, int]:
    """Suma un intento fallido y aplica la regla de bloqueo.

    Devuelve el resultado y los intentos que quedan. Hace commit.
    """
    tabla = User.__table__
    # Cierra la transacción de lectura del login: el primer statement de la
    # nueva transacción es un UPDATE, que toma el lock de escritura.
    session.rollback()

    intentos = session.execute(
        update(tabla)
        .where(tabla.c.id == usuario_id)
        .values(failed_attempts=tabla.c.failed_attempts + 1)
        .returning(tabla.c.failed_attempts)
    ).scalar_one()

    if intentos < MAX_INTENTOS:
        session.commit()
        return ResultadoIntento.FALLIDO, MAX_INTENTOS - intentos

    momento = ahora()
    otros = tabla.alias("otros")
    otros_admins_activos = (
        select(func.count())
        .select_from(otros)
        .where(
            otros.c.role == UserRole.ADMIN,
            otros.c.is_active.is_(True),
            otros.c.id != usuario_id,
        )
        .scalar_subquery()
    )

    # Desactiva salvo que sea el único ADMIN activo (todo en un solo UPDATE)
    desactivada = session.execute(
        update(tabla)
        .where(
            tabla.c.id == usuario_id,
            or_(tabla.c.role != UserRole.ADMIN, otros_admins_activos >= 1),
        )
        .values(is_active=False, lock_reason=MOTIVO_INTENTOS, locked_at=momento)
    ).rowcount == 1

    if desactivada:
        registrarAuditoria(session, usuario_id, AccionAuditoria.BLOQUEO, MOTIVO_INTENTOS)
        session.commit()
        return ResultadoIntento.DESACTIVADA, 0

    # Único ADMIN activo: se mantiene usable con un bloqueo corto
    session.execute(
        update(tabla)
        .where(tabla.c.id == usuario_id)
        .values(failed_attempts=0, locked_until=momento + BLOQUEO_TEMPORAL)
    )
    minutos = int(BLOQUEO_TEMPORAL.total_seconds() // 60)
    registrarAuditoria(
        session, usuario_id, AccionAuditoria.BLOQUEO_TEMPORAL,
        f"{MOTIVO_INTENTOS}; único ADMIN activo, bloqueo temporal de {minutos} min",
    )
    session.commit()
    return ResultadoIntento.BLOQUEO_TEMPORAL, 0


def registrarLoginCorrecto(usuario: User) -> None:
    """Reinicia el contador al entrar bien (sin commit)."""
    usuario.failed_attempts = 0
    usuario.locked_until = None
    usuario.last_login = ahora()


def reactivarCuenta(session: Session, usuario: User, actor: User) -> None:
    """Reactivación hecha por un ADMIN: limpia el bloqueo y lo audita (sin commit)."""
    motivo_previo = usuario.lock_reason
    usuario.is_active = True
    usuario.failed_attempts = 0
    usuario.lock_reason = None
    usuario.locked_at = None
    usuario.locked_until = None
    session.add(usuario)
    registrarAuditoria(
        session, usuario.id, AccionAuditoria.REACTIVACION,
        f"Reactivada por {actor.username}"
        + (f" (bloqueo previo: {motivo_previo})" if motivo_previo else ""),
        actor_id=actor.id,
    )


def desactivarCuenta(session: Session, usuario: User, actor: User) -> None:
    """Desactivación manual hecha por un ADMIN (sin commit)."""
    usuario.is_active = False
    session.add(usuario)
    registrarAuditoria(
        session, usuario.id, AccionAuditoria.DESACTIVACION,
        f"Desactivada por {actor.username}", actor_id=actor.id,
    )
