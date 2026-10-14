from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
'''
Schemes es el esquema elegido para el hash de la contraseña, en este caso bcrypt.
Deprecated indica si el esquema está obsoleto o no. En este caso, se establece en "auto", 
lo que significa que se considerará obsoleto si hay un esquema más seguro disponible.
'''



def hashPassword(plain: str) -> str:
    return pwd_context.hash(plain)


def verifyPassword(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)