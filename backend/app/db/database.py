from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

from app.core.config import settings

os.makedirs(os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()


def _migrate_add_columns():
    """Light-touch SQLite migration: hängt fehlende Spalten an, ohne dass
    Alembic gebraucht wird.  Idempotent — fügt nur hinzu was fehlt."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "matches" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("matches")}
    with engine.begin() as conn:
        if "context" not in cols:
            conn.execute(text("ALTER TABLE matches ADD COLUMN context JSON"))
