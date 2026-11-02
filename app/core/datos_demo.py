"""Datos de ejemplo TEMPORALES para maquetar las pantallas.

Se eliminan cuando existan los modelos reales (Proyecto, Material) en la base de datos.
"""
from datetime import date

RESUMEN_PROYECTOS_DEMO = {
    "total": 42,
    "total_detalle": "+3 este mes",
    "en_ejecucion": 11,
    "en_ejecucion_detalle": "26% del total",
    "presupuestados": 7,
    "presupuestados_detalle": "Pendientes de aprobación",
    "monto": "$ 1.284 M",
    "monto_detalle": "Total general CLP",
}

PROYECTOS_DEMO = [
    {"codigo": "PRY-2026-014", "nombre": "Galpón industrial Lote 7", "cliente": "Agrícola Los Robles SpA", "creacion": date(2026, 10, 12), "estado": "En ejecución", "avance": 62, "total": 184350000},
    {"codigo": "PRY-2026-013", "nombre": "Ampliación oficinas centrales", "cliente": "Constructora Andes Ltda.", "creacion": date(2026, 10, 3), "estado": "Presupuestado", "avance": 0, "total": 96720500},
    {"codigo": "PRY-2026-012", "nombre": "Bodega refrigerada 1.200 m²", "cliente": "Frutícola Maule S.A.", "creacion": date(2026, 9, 21), "estado": "En ejecución", "avance": 38, "total": 241900000},
    {"codigo": "PRY-2026-011", "nombre": "Cubierta metálica gimnasio", "cliente": "I. Municipalidad de Linares", "creacion": date(2026, 9, 9), "estado": "En ejecución", "avance": 81, "total": 58410300},
    {"codigo": "PRY-2026-010", "nombre": "Estructura soporte paneles FV", "cliente": "Energía Central SpA", "creacion": date(2026, 8, 28), "estado": "Finalizado", "avance": 100, "total": 73200000},
    {"codigo": "PRY-2026-009", "nombre": "Mezzanine metálico planta", "cliente": "Viña Santa Elena", "creacion": date(2026, 8, 14), "estado": "Finalizado", "avance": 100, "total": 31860000},
    {"codigo": "PRY-2026-008", "nombre": "Reforzamiento puente peatonal", "cliente": "I. Municipalidad de Talca", "creacion": date(2026, 8, 2), "estado": "En revisión", "avance": 0, "total": 44115750},
    {"codigo": "PRY-2026-007", "nombre": "Galpón maquinaria agrícola", "cliente": "Agrícola Los Robles SpA", "creacion": date(2026, 7, 18), "estado": "Cancelado", "avance": 15, "total": 67300000},
]

RESUMEN_APU_DEMO = {
    "registrados": 214,
    "registrados_detalle": "En 9 categorías",
    "activos": 198,
    "activos_detalle": "Disponibles para presupuestar",
    "inactivos": 16,
    "inactivos_detalle": "No aparecen en presupuestos",
    "actualizados": 37,
    "actualizados_detalle": "En los últimos 30 días",
}

MATERIALES_DEMO = [
    {"codigo": "MAT-0101", "nombre": "Perfil C 150x50x3 mm", "tipo": "Acero", "unidad": "ml", "precio": 9850, "actualizado": date(2026, 10, 14), "activo": True},
    {"codigo": "MAT-0102", "nombre": "Plancha acero A37 e=6 mm", "tipo": "Acero", "unidad": "m²", "precio": 58200, "actualizado": date(2026, 10, 14), "activo": True},
    {"codigo": "MAT-0115", "nombre": "Hormigón premezclado H-25", "tipo": "Hormigón", "unidad": "m³", "precio": 112400, "actualizado": date(2026, 10, 9), "activo": True},
    {"codigo": "MAT-0116", "nombre": "Barra acero A630 Ø12 mm", "tipo": "Acero", "unidad": "kg", "precio": 1180, "actualizado": date(2026, 10, 9), "activo": True},
    {"codigo": "MAT-0124", "nombre": "Panel PIR 100 mm", "tipo": "Panel", "unidad": "m²", "precio": 31600, "actualizado": date(2026, 10, 2), "activo": True},
    {"codigo": "MAT-0130", "nombre": "Pintura anticorrosiva epóxica", "tipo": "Pintura", "unidad": "gl", "precio": 42900, "actualizado": date(2026, 9, 28), "activo": True},
    {"codigo": "MAT-0131", "nombre": "Perno de anclaje 3/4\" galv.", "tipo": "Fijación", "unidad": "un", "precio": 3450, "actualizado": date(2026, 9, 28), "activo": False},
    {"codigo": "MAT-0142", "nombre": "Ladrillo fiscal 29x14x7 cm", "tipo": "Albañilería", "unidad": "un", "precio": 390, "actualizado": date(2026, 9, 15), "activo": False},
]
