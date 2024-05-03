import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.routes import Base, Folowers, Likes, Tweets, User
from app.routes import app as app_
from app.routes import get_db_session

DATABASE_URL_TEST = (
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5431/test_db"
)
engine = create_async_engine(DATABASE_URL_TEST, echo=True, poolclass=NullPool)
test_async_session = sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


@pytest_asyncio.fixture(autouse=True)
async def session_test():
    session = test_async_session()
    try:
        yield session
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
    finally:
        await session.close()


@pytest_asyncio.fixture
async def app(session_test: AsyncSession):
    app_.dependency_overrides[get_db_session] = lambda: session_test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with test_async_session() as session:
        user = User(api_key="123a", name="name")
        user_2 = User(api_key="124a", name="name2")
        session.add_all([user, user_2])
        await session.commit()
        tweets = Tweets(content="content", author_id=2)
        session.add(tweets)
        await session.commit()
        followers = Folowers(followers_id=1, following_id=2)
        likes = Likes(tweet_id=1, likers_id=1)
        session.add_all([followers, likes])
        await session.commit()
        try:
            yield app_
        finally:
            await session.close()


@pytest_asyncio.fixture(autouse=True)
async def async_app_client(app):
    transport = ASGITransport(app=app_)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client
