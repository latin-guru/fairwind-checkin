"""Database engine and session helpers (SQLite through SQLAlchemy)."""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_Session = None


def init(database_url: str) -> None:
    """Create the engine and tables. Called once at app startup (and by each test)."""
    global _engine, _Session
    args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _engine = create_engine(database_url, connect_args=args)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    from app import models  # noqa: F401  (registers the tables)

    Base.metadata.create_all(_engine)


def reset() -> None:
    """Drop and recreate every table (demo reseed)."""
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)


@contextmanager
def session():
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
