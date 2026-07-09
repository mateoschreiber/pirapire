from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    from . import (  # noqa: F401
        models,
        models_football,
        models_history,
        models_imports,
        models_lol,
        models_markets,
        models_sources,
    )

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
