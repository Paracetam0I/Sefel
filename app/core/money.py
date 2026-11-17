from decimal import Decimal

from sqlalchemy.types import String, TypeDecorator


class DecimalText(TypeDecorator):
    """Guarda un Decimal como texto ('10500.50') y lo devuelve como Decimal.

    SQLite no tiene Decimal nativo: una columna NUMERIC lo pasaría por float y
    perdería exactitud. Regla del proyecto: dinero y cantidades se calculan SOLO
    en Python; nunca con SUM, ORDER BY ni comparaciones en SQL (verían texto).
    """

    impl = String(40)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, float) or isinstance(value, bool):
            raise TypeError("No se permite float para dinero: usa Decimal, int o str")
        if not isinstance(value, Decimal):
            value = Decimal(value)
        if not value.is_finite():
            raise ValueError("El valor debe ser un número finito")
        return format(value, "f")  # 'f' evita la notación científica

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(value)