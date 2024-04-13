import pytest_asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.util import greenlet_spawn
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.routes import app as app_, User, Folowers, Tweets, Likes, Base, engine, session

# DATABASE_URL_TEST = "postgresql+asyncpg://admin:admin@localhost/db"

'''
@pytest_asyncio.fixture()
def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        yield
        await conn.run_sync(Base.metadata.drop_all)
'''


@pytest_asyncio.fixture(scope="session")
async def app():
    '''
    DATABASE_URL_TEST = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5431/db"
    engine = create_async_engine(DATABASE_URL_TEST, echo=True, pool_pre_ping=True)
    async_session = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    session = async_session()'''
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    user = User(api_key='123a',
                name="name")
    user_2 = User(api_key='124a',
                  name="name2")
    session.add_all([user, user_2])
    await session.commit()
    tweets = Tweets(content='content',
                    author_id=2)
    session.add(tweets)
    await session.commit()
    followers = Folowers(followers_id=1,
                         following_id=2)
    likes = Likes(tweet_id=1,
                  likers_id=1)
    session.add_all([followers, likes])
    await session.commit()
    yield app_
    await session.close()


@pytest_asyncio.fixture(scope="session")
async def async_app_client():
    async with AsyncClient(app=app_, base_url="http://test") as client:
        yield client
