from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from routellm.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_session() -> Session:
    return SessionLocal()
