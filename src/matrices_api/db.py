from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, String, create_engine
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
    """Una suma o resta guardada en el historial del usuario."""

    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    operation: Mapped[str] = mapped_column(String(10))  # add | subtract
    matrix_a: Mapped[list] = mapped_column(Json)
    matrix_b: Mapped[list] = mapped_column(Json)
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


def get_db():
    assert _SessionLocal is not None, "init_db() no se llamó"
    with _SessionLocal() as session:
        yield session


def ping() -> bool:
    from sqlalchemy import text

    try:
        with _engine.connect() as conn:  # type: ignore[union-attr]
            conn.execute(text("select 1"))
        return True
    except Exception:
        return False
