"""
dashboard.py — Página de resumen ("tablero") que se ve al entrar.

EN SIMPLE
    Muestra tarjetas con números clave: cuántos presupuestos hay por estado,
    cuánto suman los activos, cuántos APU hay, cuántos usuarios están activos
    o bloqueados, y los últimos movimientos. Cada persona ve solo las
    tarjetas de los módulos a los que tiene acceso.

TÉCNICO
    Ruta: GET /dashboard. Hace consultas de agregación (COUNT, SUM, GROUP BY)
    en la BD en vez de traer todas las filas a Python. Cada bloque se calcula
    solo si puede(usuario, "...") lo permite; si no, se pasa None y la
    plantilla no lo dibuja.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.db import getSession
from app.core.dependencies import CurrentUser
from app.core.permisos import puede
from app.models.apu import APU
from app.models.auditoria import AuditoriaCuenta
from app.models.presupuesto import Presupuesto, StatusPresupuestos
from app.models.user import User
from app.templates import templates


# Todos los roles autenticados entran; cada bloque se arma solo si el rol
# tiene acceso al módulo (un VIEWER no ve conteos de usuarios ni de APU).
router = APIRouter(tags=["dashboard"])

ULTIMOS = 5             # cuántos elementos mostrar en las listas "últimos/recientes"
DIAS_ACTUALIZADOS = 30  # ventana para contar APU "actualizados recientemente"


def _contar(session: Session, modelo, *condiciones) -> int:
    """SELECT COUNT(*) FROM modelo [WHERE condiciones]. Ej.: _contar(s, User, User.is_active.is_(True))."""
    consulta = select(func.count()).select_from(modelo)
    if condiciones:
        consulta = consulta.where(*condiciones)
    return session.exec(consulta).one()


def _resumenPresupuestos(session: Session) -> dict:
    """Conteo por estado, suma de montos activos y los últimos creados.

    GROUP BY status devuelve pares (estado, cantidad) -> se pasan a dict.
    coalesce(sum(...), 0): si no hay activos, SUM da NULL; así queda 0.
    """
    por_estado = dict(session.exec(
        select(Presupuesto.status, func.count()).group_by(Presupuesto.status)
    ).all())
    monto_activos = session.exec(
        select(func.coalesce(func.sum(Presupuesto.monto_total), 0))
        .where(Presupuesto.status == StatusPresupuestos.ACTIVE)
    ).one()
    return {
        "total": sum(por_estado.values()),
        "borradores": por_estado.get(StatusPresupuestos.DRAFT, 0),
        "activos": por_estado.get(StatusPresupuestos.ACTIVE, 0),
        "cerrados": por_estado.get(StatusPresupuestos.CLOSE, 0),
        "monto_activos": monto_activos,
        "ultimos": session.exec(
            select(Presupuesto)
            .order_by(Presupuesto.created_at.desc())
            .limit(ULTIMOS)
        ).all(),
    }


def _resumenApu(session: Session) -> dict:
    """Totales de APU y los más recientes (por fecha de edición, o de creación si nunca se editó)."""
    desde = datetime.now(timezone.utc) - timedelta(days=DIAS_ACTUALIZADOS)
    return {
        "total": _contar(session, APU),
        "activos": _contar(session, APU, APU.is_active.is_(True)),
        "actualizados": _contar(session, APU, APU.updated_at >= desde),
        "recientes": session.exec(
            select(APU)
            .order_by(func.coalesce(APU.updated_at, APU.created_at).desc())
            .limit(ULTIMOS)
        ).all(),
    }


def _resumenUsuarios(session: Session) -> dict:
    """Conteos de usuarios y últimos eventos de auditoría con nombres legibles.

    Se arma un dict {id: username} una sola vez para traducir los ids de la
    auditoría sin hacer una consulta por cada evento.
    """
    nombres = dict(session.exec(select(User.id, User.username)).all())
    eventos = session.exec(
        select(AuditoriaCuenta)
        .order_by(AuditoriaCuenta.created_at.desc())
        .limit(ULTIMOS)
    ).all()
    return {
        "total": _contar(session, User),
        "activos": _contar(session, User, User.is_active.is_(True)),
        "inactivos": _contar(session, User, User.is_active.is_(False)),
        "bloqueados": _contar(session, User, User.lock_reason.is_not(None)),
        "auditoria": [
            {
                "evento": e,
                "usuario": nombres.get(e.id_usuario, "—"),
                "actor": nombres.get(e.id_actor, "—") if e.id_actor else "Sistema",
            }
            for e in eventos
        ],
    }


@router.get("/dashboard")
def mostrarDashboard(
    request: Request,
    usuario: CurrentUser,
    session: Session = Depends(getSession),
):
    """GET /dashboard: cualquier usuario con sesión; el contenido depende del rol."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "usuario": usuario,
            "presupuestos": (
                _resumenPresupuestos(session) if puede(usuario, "presupuestos") else None
            ),
            "apus": _resumenApu(session) if puede(usuario, "apu") else None,
            "usuarios": (
                _resumenUsuarios(session) if puede(usuario, "usuarios") else None
            ),
        },
    )
