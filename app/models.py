from sqlalchemy import Column, String, Integer, ForeignKey, ARRAY
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/db"
engine = create_async_engine(DATABASE_URL, echo=True)
# expire_on_commit=False will prevent attributes from being expired
# after commit.
async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)
session = async_session()
Base = declarative_base()


class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)


class Media(Base):
    __tablename__ = 'media'
    id = Column(Integer, primary_key=True, index=True)
    file = Column(String, nullable=False)


class Folowers(Base):
    __tablename__ = 'folowers'
    id = Column(Integer, primary_key=True, index=True)
    followers_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    following_id = Column(Integer, ForeignKey('user.id'), nullable=False)


class Tweets(Base):
    __tablename__ = 'tweets'
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    attachments = Column(ARRAY(Integer))
    author_id = Column(Integer, ForeignKey('user.id'), nullable=False)


class Likes(Base):
    __tablename__ = 'likes'
    id = Column(Integer, primary_key=True, index=True)
    tweet_id = Column(Integer, ForeignKey('tweets.id'), nullable=False)
    likers_id = Column(Integer, ForeignKey('user.id'), nullable=False)
