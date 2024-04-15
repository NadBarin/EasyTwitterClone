import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.routes import app as app_, User, Folowers, Tweets, Likes, Base, engine, get_db_session
import asyncio

# DATABASE_URL_TEST = "postgresql+asyncpg://admin:admin@localhost/db"

'''
@pytest_asyncio.fixture()
def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        yield
        await conn.run_sync(Base.metadata.drop_all)
'''

DATABASE_URL_TEST = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5431/test_db"
engine = create_async_engine(DATABASE_URL_TEST, echo=True, pool_pre_ping=True)
test_async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)
session = test_async_session()


async def test_session():
    async with test_async_session() as session_:
        yield session_


app_.dependency_overrides[get_db_session] = test_session


@pytest_asyncio.fixture
async def recreate_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        yield


@pytest_asyncio.fixture
async def app():
    async with test_async_session() as session:
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


@pytest_asyncio.fixture()
async def async_app_client(recreate_tables, app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
