from routellm.db.base import Base
from routellm.db.session import engine


def create_database() -> None:
    Base.metadata.create_all(bind=engine)
