from logging.config import fileConfig

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    # disable_existing_loggers=False: al migrar desde la app (client.py) no se
    # deben apagar los loggers que ya existan
    fileConfig(config.config_file_name, disable_existing_loggers=False)

from sqlmodel import SQLModel

from app.core.db import engine
from app.models.user import User
from app.models.presupuesto import Presupuesto
from app.models.apu import APU
from app.models.material import Material  # noqa: F401
from app.models.detalle_apu import DetalleApu  # noqa: F401
from app.models.detalle_presupuesto import DetallePresupuesto  # noqa: F401
from app.models.auditoria import AuditoriaCuenta  # noqa: F401

target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = engine.url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite no soporta ALTER TABLE completo
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine

    with connectable.connect() as connection:
        # El modo batch recrea tablas (copiar, borrar, renombrar). Con las FK
        # activas (app.core.db las enciende) borrar una tabla referenciada,
        # p. ej. apu desde detalle_presupuesto, falla. Se apagan solo durante
        # la migración; el PRAGMA debe ir fuera de una transacción.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite no soporta ALTER TABLE completo
        )

        with context.begin_transaction():
            context.run_migrations()

        # Verifica que la migración no haya dejado referencias rotas
        rotas = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        if rotas:
            raise RuntimeError(f"La migración dejó claves foráneas rotas: {rotas}")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
