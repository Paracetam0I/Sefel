"""
security.py — Hash y verificación de contraseñas.

EN SIMPLE
    Las contraseñas NUNCA se guardan tal cual. Se guardan "trituradas"
    (hash): es fácil triturar una contraseña, pero imposible reconstruirla
    desde lo triturado. Para comprobar un login se tritura lo que escribió
    el usuario y se compara.

TÉCNICO
    passlib + bcrypt. bcrypt agrega una "sal" aleatoria a cada hash (dos
    usuarios con la misma contraseña tienen hashes distintos) y es lento a
    propósito, lo que dificulta los ataques de fuerza bruta.
"""
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
'''
Schemes es el esquema elegido para el hash de la contraseña, en este caso bcrypt.
Deprecated indica si el esquema está obsoleto o no. En este caso, se establece en "auto",
lo que significa que se considerará obsoleto si hay un esquema más seguro disponible.
'''



def hashPassword(plain: str) -> str:
    """Contraseña en texto plano -> hash bcrypt (lo que se guarda en la BD)."""
    return pwd_context.hash(plain)


def verifyPassword(plain: str, hashed: str) -> bool:
    """True si `plain` corresponde al hash guardado. Se usa en el login."""
    return pwd_context.verify(plain, hashed)
