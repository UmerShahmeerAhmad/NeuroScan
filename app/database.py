"""Database connection (PostgreSQL through SQLAlchemy)."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# SQLite (only used for quick local tests) needs one extra option.
_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping quietly replaces connections that PostgreSQL has closed.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db():
    """FastAPI dependency: gives each request its own database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first release. create_all() builds new tables but never changes
# existing ones, so these are added here when they are missing (safe to run on every start).
_NEW_COLUMNS = {
    "users": {"password_changed_at": "TIMESTAMP WITH TIME ZONE"},
    "predictions": {
        "feedback": "VARCHAR(10)",
        "feedback_note": "TEXT",
        "feedback_at": "TIMESTAMP WITH TIME ZONE",
    },
}


def upgrade_schema() -> list:
    """Adds any missing columns to existing tables. Returns what it added."""
    added = []
    inspector = inspect(engine)
    for table, columns in _NEW_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name not in existing:
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                added.append(f"{table}.{name}")
    return added
