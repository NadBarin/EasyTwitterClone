import os

from dotenv import load_dotenv
from sqlalchemy import (
    ARRAY,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

load_dotenv()

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")
db_port = os.getenv("DB_PORT")

DATABASE_URL = (
    f"postgresql+asyncpg://{db_user}:{db_password}@db:{db_port}/{db_name}"
)
engine = create_async_engine(DATABASE_URL, echo=True, pool_pre_ping=True)

async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)
Base = declarative_base()


async def get_db_session():  # pragma: no cover
    session = async_session()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    finally:
        await session.close()


class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    api_key = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    # Отношения
    media = relationship("Media", back_populates="user")
    tweets = relationship("Tweets", back_populates="user")
    likes = relationship("Likes", back_populates="user")


class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True)
    file = Column(String, nullable=False)
    uploader_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    # Отношения
    user = relationship("User", back_populates="media")


class Followers(Base):
    __tablename__ = "followers"
    id = Column(Integer, primary_key=True)
    followers_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    following_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    # Уникальный составной индекс для предотвращения дублирования подписок
    __table_args__ = (
        UniqueConstraint("followers_id", "following_id", name="uix_1"),
    )


class Tweets(Base):
    __tablename__ = "tweets"
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    attachments = Column(ARRAY(Integer))
    author_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    # Отношения
    user = relationship("User", back_populates="tweets")
    likes = relationship("Likes", back_populates="tweets")


class Likes(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True)
    tweet_id = Column(
        Integer, ForeignKey("tweets.id", ondelete="CASCADE"), nullable=False
    )
    likers_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    # Отношения
    user = relationship("User", back_populates="likes")
    tweets = relationship("Tweets", back_populates="likes")
