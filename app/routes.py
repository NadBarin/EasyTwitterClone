import os
from contextlib import asynccontextmanager
from datetime import datetime

import aiofiles
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import and_, any_, or_

from .models import (
    Base,
    Followers,
    Likes,
    Media,
    Tweets,
    User,
    engine,
    get_db_session,
)
from .shemas import TweetCreate

static = os.path.abspath("static")

DOWNLOADS: str | None = os.getenv("DOWNLOADS")


@asynccontextmanager
async def lifespan(
        app: FastAPI, session: AsyncSession = Depends(get_db_session)
):  # pragma: no cover
    """Создаёт таблицу если её небыло,
    открывает и закрывает session и engine"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await session.close()
    await engine.dispose()


app = FastAPI(lifespan=lifespan, title="main")
app_api = FastAPI(title="api")

app.mount("/api", app_api, name="api")
app.mount("/static", StaticFiles(directory=static, html=True), name="static")
templates = Jinja2Templates(directory=static)
load_dotenv()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):  # pragma: no cover
    return templates.TemplateResponse("index.html", {"request": request})


async def catch_exceptions_middleware(request: Request, call_next):
    # pragma: no cover
    """отлавливает ошибки оформляет по нужному формату"""
    try:
        return await call_next(request)
    except Exception as e:
        return JSONResponse(
            content={
                "result": False,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            status_code=getattr(e, "status_code", 400),
        )


app_api.middleware("http")(catch_exceptions_middleware)


async def check_api_key(
        api_key: str | None = Header("api-key"),
        session: AsyncSession = Depends(get_db_session),
):
    """
    Проверяет существует ли api-key.

    ### Parameters:
        - **api_key**: `str | None` - API-ключ текущего пользователя.
        - **session**: `AsyncSession` - Сессия с текущей базой данных.
        ### Returns:
        - `id текущего пользователя или сообщение об ошибке.

    """
    if api_key:
        check_api_k = await session.execute(
            select(User.id).where(User.api_key == api_key)
        )
        res = check_api_k.scalars().first()
        if res:
            return res
        raise Exception("Wrong api-key. Please check your data.")
    raise Exception("Wrong api-key. Please check your data.")


@app_api.post("/tweets")
async def add_new_tweet(
        data: TweetCreate,
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """
    Добавить новый твит. Может содержать картинку.

    ### Parameters:

    - **data**: `TweetCreate` - содержание твита и список с
    ID вложенных файлов.
    - **session**: `AsyncSession` - Сессия с текущей
    базой данных.
    - **user_id**: `int` - id текущего пользователя, возвращёный
    из check_api_key

    ### Returns:
    - `Response` объект с успешным статусом или неуспешным
    и сообщением об ошибке.
    """
    if data.tweet_media_ids:
        media_ids_query = select(Media.id).where(
            (Media.id.in_(data.tweet_media_ids))
            & (Media.uploader_id == user_id)
        )
        media_ids_result = await session.execute(media_ids_query)
        media_ids = media_ids_result.scalars().all()

        if len(media_ids) != len(data.tweet_media_ids):
            raise Exception("Can't add new tweet. Please check your data.")

    tweet_insert = (
        insert(Tweets)
        .values(
            content=data.tweet_data,
            attachments=data.tweet_media_ids if data.tweet_media_ids else [],
            author_id=user_id,
        )
        .returning(Tweets.id)
    )

    result = await session.execute(tweet_insert)
    await session.commit()

    return {"result": True, "tweet_id": result.scalars().first()}


@app_api.post("/medias")
async def add_new_media(
        file: UploadFile = File(...),
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """
    Загрузить картинку для твита.

    ### Parameters:
    - **file**: `UploadFile` - Загружаемый файл.
    - **session**: `AsyncSession` - Сессия с текущей
    базой данных.
    - **user_id**: `int` - id текущего пользователя, возвращёный
    из check_api_key

    ### Returns:
    - `Response` объект с успешным статусом и id загруженной картинки
    или неуспешным и сообщением об ошибке.
    """
    if DOWNLOADS is not None:
        if not os.path.exists(DOWNLOADS):
            os.makedirs(DOWNLOADS)
        if file:
            # Используем временную метку для создания уникального имени файла
            timestamp = datetime.now()
            file_name = (
                f"{file.filename.rsplit('.', 1)[0]}_{timestamp}."
                f"{file.filename.rsplit('.', 1)[-1]}"
            )
            file_path = os.path.join(DOWNLOADS, file_name)
            contents = await file.read()
            await file.close()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(contents)
            new_media = Media(file=file_name, uploader_id=user_id)
            session.add(new_media)
            await session.commit()
            return {"result": True, "media_id": new_media.id}
    raise Exception("Can't add new media. Please check your data.")


@app_api.delete("/tweets/{id}")
async def delete_tweet(
        id: int,
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """
    Удалить свой твит вместе с вложенными файлами.

    ### Parameters:
    - **id**: `int` - ID твита, который нужно удалить.
    - **session**: `AsyncSession` - Сессия с текущей базой данных.
    - **user_id**: `int` - id текущего пользователя, возвращёный
    из check_api_key

    ### Returns:
    - `Response` объект с успешным статусом
    или неуспешным и сообщением об ошибке.
    """
    '''tweet_to_delete = await session.get(Tweets, id)
    if tweet_to_delete and tweet_to_delete.author_id == user_id:
        attachments = tweet_to_delete.attachments
        await session.execute(
            delete(tweet_to_delete).where(
                (tweet_to_delete.author_id == user_id) & (id == tweet_to_delete.id)
            )
        )'''

    attachments_ = await session.execute(
        delete(Tweets)
        .where((Tweets.author_id == user_id) & (id == Tweets.id))
        .returning(Tweets.id, Tweets.attachments)
    )
    attachments = attachments_.all()
    await session.commit()
    if attachments[0][0]:
        if attachments[0][1]:
            names = await session.execute(
                select(Media.file).where(Media.id.in_(attachments[0][1]))
            )
            await session.execute(
                delete(Media).where(Media.id.in_(attachments[0][1]))
            )
            await session.commit()
            for name in names.scalars():
                if DOWNLOADS is not None:
                    os.remove(os.path.join(DOWNLOADS, name))
            return {"result": True}
    else:
        raise Exception("Can't delete tweet. " "It's not yours or it's not exist.")


@app_api.post("/users/{id}/follow")
async def follow(
        id: int,
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """
     Зафоловить другого пользователя.

    ### Parameters:
        - **id**: `int` - ID пользователя, на которого текущий
        пользователь подписывается.
        - **session**: `AsyncSession` - Сессия с текущей базой данных.
        - **user_id**: `int` - id текущего пользователя, возвращёный
        из check_api_key

    ### Returns:
        - `Response` объект с успешным статусом
        или неуспешным и сообщением об ошибке.
    """
    check_id = await session.execute(select(User).where(User.id == id))
    if check_id.fetchall() and id != user_id:
        insert_into_followers = insert(Followers).values(
            followers_id=user_id, following_id=id
        )
        await session.execute(insert_into_followers)
        await session.commit()
        return {"result": True}
    raise Exception("Can't add new follow. Please check your data.")


@app_api.delete("/users/{id}/follow")
async def unfollow(
        id: int,
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """
    Отписаться от другого пользователя.

    ### Parameters:
    - **id**: `int` - ID пользователя, от которого
    отписывается текущий пользователь.
    - **session**: `AsyncSession` - Сессия с текущей базой данных.
    - **user_id**: `int` - id текущего пользователя,
    возвращёный из check_api_key

    ### Returns:
    - `Response` объект с успешным статусом
    или неуспешным и сообщением об ошибке.

    """
    await session.execute(
        delete(Followers).where(
            (Followers.followers_id == user_id)
            & (Followers.following_id == id)
        )
    )
    await session.commit()
    return {"result": True}


@app_api.post("/tweets/{id}/likes")
async def like(
        id: int,
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """
    Отметить твит как понравившийся.

    ### Parameters:
        - **id**: `int` - ID твита, который лайкает текущий пльзователь.
        - **session**: `AsyncSession` - Сессия с текущей базой данных.
        - **user_id**: `int` - id текущего пользователя,
        возвращёный из check_api_key

    ### Returns:
        - `Response` объект с успешным статусом
        или неуспешным и сообщением об ошибке.
    """
    result = await session.execute(
        select(Tweets, Likes)
        .outerjoin(
            Likes,
            and_(Likes.tweet_id == Tweets.id, Likes.likers_id == user_id),
        )
        .where(Tweets.id == id)
    )
    tweet, likes = result.first() or (None, None)

    if tweet is None:
        raise Exception("Can't add like. Please check your data.")
    if likes is not None:
        raise Exception("Can't add like. You're already liked this tweet.")

    insert_into_likes = insert(Likes).values(tweet_id=id, likers_id=user_id)
    await session.execute(insert_into_likes)
    await session.commit()
    return {"result": True}


@app_api.delete("/tweets/{id}/likes")
async def delete_like(
        id: int,
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """Убрать отметку «Нравится».

    ### Parameters:
        - **id**: `int` - ID твита, который дизлайкает текущий пльзователь.
        - **session**: `AsyncSession` - Сессия с текущей базой данных.
        - **user_id**: `int` - id текущего пользователя,
        возвращёный из check_api_key

    ### Returns:
        - `Response` объект с успешным статусом
        или неуспешным и сообщением об ошибке.
    """
    await session.execute(
        delete(Likes).where(
            (Likes.likers_id == user_id) & (Likes.tweet_id == id)
        )
    )
    await session.commit()
    return {"result": True}


@app_api.get("/tweets")
async def feed(
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """
    Получить ленту из твитов отсортированных в
    порядке убывания по популярности от пользователей, которых он
    фоловит.


    ### Parameters:
        - **session**: `AsyncSession` - Сессия с текущей базой данных.
        - **user_id**: `int` - id текущего пользователя,
        возвращёный из check_api_key

    ### Returns:
        - `Response` объект с успешным статусом и
        json со списком твитов для ленты этого пользователя,
        или неуспешным и сообщением об ошибке.
    """
    author = aliased(User, name="user_1")
    liker = aliased(User, name="user_2")

    followers_count = func.count(Followers.followers_id).over(
        partition_by=Tweets.author_id
    )
    is_author_subscriber = and_(
        Tweets.author_id == Followers.following_id,
        user_id == Followers.followers_id,
    )
    sort_condition = case([(is_author_subscriber, followers_count)], else_=0)

    secondary_sort_condition = case(
        [(is_author_subscriber, Tweets.id)], else_=0
    )

    third_sort_condition = case(
        [(is_author_subscriber, 0)], else_=Tweets.id
    )

    complex_query = await session.execute(
        select(
            Tweets.id,
            Tweets.content,
            Tweets.attachments,
            Tweets.author_id,
            author.name.label("author_name"),
            Media.file,
            Likes.likers_id,
            liker.name.label("liker_name"),
            followers_count,
        )
        .outerjoin(Media, Media.id == any_(Tweets.attachments))
        .outerjoin(Likes, Likes.tweet_id == Tweets.id)
        .outerjoin(author, author.id == Tweets.author_id)
        .outerjoin(liker, liker.id == Likes.likers_id)
        .outerjoin(Followers, Followers.following_id == Tweets.author_id)
        .group_by(
            Tweets.id,
            author.name,
            Media.file,
            Likes.likers_id,
            liker.name,
            Followers.followers_id,
            Followers.following_id,
            Media.id,
        )
        .order_by(
            sort_condition.desc(),
            secondary_sort_condition.desc(),
            third_sort_condition.desc(),
            Media.id.asc(),
        )
    )
    complex_data = complex_query.fetchall()

    tweets_result = {}
    for data in complex_data:
        tweet_id = data[0]
        if tweet_id not in tweets_result:
            tweets_result[tweet_id] = {
                "id": tweet_id,
                "content": data[1],
                "attachments": set(),
                "author": {"id": data[3], "name": data[4]},
                "likes": set(),
            }
        if DOWNLOADS is not None:
            if data[5]:
                tweets_result[tweet_id]["attachments"].add(
                    os.path.join(DOWNLOADS, data[5])
                )
        else:
            raise Exception('Check DOWNLOADS in .env')
        if data[6]:
            tweets_result[tweet_id]["likes"].add((data[6], data[7]))
    for tweet_id, tweet_data in tweets_result.items():
        tweet_data["attachments"] = list(tweet_data["attachments"])
        tweet_data["likes"] = [
            {"user_id": user_id, "name": name}
            for user_id, name in tweet_data["likes"]
        ]

    result = {"result": True, "tweets": list(tweets_result.values())}
    return result


async def info_user(user_id: int, session: AsyncSession):
    """
    т.к /users/me и /users/{id} запрашивают примерно одни и те же данные,
    просто /me запрашивает по id текущего пользователя, а  /{id} по id
    другого пльзователя, то можно использовать одну функцию
    для обработки таких запросов.
    """
    User_ = aliased(User, name="user_3")
    Follower = aliased(User, name="user_4")
    Following = aliased(User, name="user_5")
    result = await session.execute(
        select(
            User_.name.label("user_name"),
            Followers.following_id,
            Follower.name.label("following_name"),
            Followers.followers_id,
            Following.name.label("followers_name"),
        )
        .select_from(User_)
        .outerjoin(
            Followers,
            or_(
                User_.id == Followers.followers_id,
                User_.id == Followers.following_id,
            ),
        )
        .outerjoin(Follower, Followers.following_id == Follower.id)
        .outerjoin(Following, Followers.followers_id == Following.id)
        .where(User_.id == user_id)
    )
    rows = result.fetchall()
    if rows:
        user_info_def: dict = {
            "result": True,
            "user": {
                "id": user_id,
                "name": rows[0]["user_name"],
                "followers": [],
                "following": [],
            },
        }
        for row in rows:
            if row["following_id"] and row["following_id"] != user_id:
                user_info_def["user"]["following"].append(
                    {"id": row["following_id"], "name": row["following_name"]}
                )
            if row["followers_id"] and row["followers_id"] != user_id:
                user_info_def["user"]["followers"].append(
                    {"id": row["followers_id"], "name": row["followers_name"]}
                )
        return user_info_def
    return False


@app_api.get("/users/me")
async def user_info(
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """
    Получить информацию о своём профиле.


    ### Parameters:
        - **session**: `AsyncSession` - Сессия с текущей базой данных.
        - **user_id**: `int` - id текущего пользователя,
        возвращёный из check_api_key

    ### Returns:
        - `Response` объект с успешным статусом и
        json с информацией о текущем пользователе,
        или неуспешным и сообщением об ошибке.
    """
    return await info_user(user_id, session)


@app_api.get("/users/{id}")
async def other_user_info(
        id: int,
        session: AsyncSession = Depends(get_db_session),
        user_id: int = Depends(check_api_key),
):
    """
    получить информацию о произвольном профиле по его
    id.

    ### Parameters:
         - **id**: `int` - ID пользователя, информацию о котором
         текущий пользователь хочет просмотреть.
        - **session**: `AsyncSession` - Сессия с текущей базой данных.
        - **user_id**: `int` - id текущего пользователя,
        возвращёный из check_api_key

    ### Returns:
        - `Response` объект с успешным статусом и
        json с информацией о другом пользователе,
        или неуспешным и сообщением об ошибке.
    """
    res = await info_user(id, session)
    if res:
        return res
    raise Exception("Can't show users info. Please check your data.")
