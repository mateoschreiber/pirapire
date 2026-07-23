from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    from . import models_football, models_lol  # noqa: F401
    SQLModel.metadata.create_all(engine)
    from .migrations import upgrade
    upgrade(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
