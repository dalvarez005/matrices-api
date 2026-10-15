from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, String, create_engine, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import get_settings

# JSONB en PostgreSQL; JSON plano en SQLite (pruebas).
Json = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(200), default="")
    picture: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=_now)
    last_login_at: Mapped[datetime] = mapped_column(default=_now)


class Operation(Base):
    """Una operación guardada en el historial del usuario.

    matrix_a / matrix_b son las dos primeras matrices; [matrices] y
    [operators] guardan la expresión completa (null en filas anteriores a las
    operaciones compuestas: ahí son A y B con [operation]).
    """

    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    operation: Mapped[str] = mapped_column(String(10))  # add | subtract | compound
    matrix_a: Mapped[list] = mapped_column(Json)
    matrix_b: Mapped[list] = mapped_column(Json)
    matrices: Mapped[list | None] = mapped_column(Json)
    operators: Mapped[list | None] = mapped_column(Json)  # "+" | "-"
    result: Mapped[list] = mapped_column(Json)
    source: Mapped[str] = mapped_column(String(10), default="manual")  # manual | image
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def init_db() -> None:
    """Conecta y crea las tablas que falten (la base debe existir)."""
    global _engine, _SessionLocal
    _engine = create_engine(get_settings().sqlalchemy_url, pool_pre_ping=True, pool_size=5)
    _SessionLocal = sessionmaker(_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    _add_missing_columns(_engine)


def _add_missing_columns(engine) -> None:
    """create_all no altera tablas existentes: agrega las columnas nuevas."""
    existing = {c["name"] for c in inspect(engine).get_columns("operations")}
    json_type = "JSONB" if engine.dialect.name == "postgresql" else "JSON"
    with engine.begin() as conn:
        for column in ("matrices", "operators"):
            if column not in existing:
                conn.execute(text(f"ALTER TABLE operations ADD COLUMN {column} {json_type}"))


def get_db():
    assert _SessionLocal is not None, "init_db() no se llamó"
    with _SessionLocal() as session:
        yield session


def ping() -> bool:
    try:
        with _engine.connect() as conn:  # type: ignore[union-attr]
            conn.execute(text("select 1"))
        return True
    except Exception:
        return False
