import os
from contextlib import asynccontextmanager
from typing import Annotated

import aiofiles
from fastapi import Depends, FastAPI, File, Header, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, delete, func, insert, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    Base,
    Folowers,
    Likes,
    Media,
    Tweets,
    User,
    engine,
    get_db_session,
)
from .shemas import TweetCreate

static = os.path.abspath("static")

DOWNLOADS: str = os.path.join("static", "images")


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

origins = ["http://127.0.0.1:8000", "http://0.0.0.0:8080"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def index(
        request: Request
):  # pragma: no cover
    return templates.TemplateResponse("index.html", {"request": request})


async def check_api_key(
    header_value: Annotated[str | None, Header()], session: AsyncSession
):
    if header_value:
        check_api_k = await session.execute(
            select(User.id).where(User.api_key == header_value)
        )
        res = check_api_k.scalars().first()
        if res:
            return res
    return False


# требования регистрации пользователя нет: это корпоративная
# сеть и пользователи будут создаваться не нами. Но нам нужно уметь отличать
# одного пользователя от другого.
@app_api.post("/tweets")
async def add_new_tweet(
    data: TweetCreate,
    api_key: str | None = Header("api-key"),
    session: AsyncSession = Depends(get_db_session),
):
    """Добавить новый твит. может содержать картинку."""
    user_id = await check_api_key(api_key, session)
    if user_id:
        if data.tweet_media_ids:
            check_tweet_media = await session.execute(
                select(Media.id).where(
                    (Media.id.in_(data.tweet_media_ids))
                    & (Media.uploader_id == user_id)
                )
            )
            check_tweet_media_ = check_tweet_media.fetchall()
            if check_tweet_media_:
                if len(check_tweet_media_) == len(data.tweet_media_ids):
                    insert_into_tweets = (
                        insert(Tweets)
                        .values(
                            content=data.tweet_data,
                            attachments=data.tweet_media_ids,
                            author_id=user_id,
                        )
                        .returning(Tweets.id)
                    )
                else:
                    return JSONResponse(
                        content={
                            "message": "Can't add new tweet. "
                            "Please check your data."
                        },
                        status_code=404,
                    )
            else:
                return JSONResponse(
                    content={
                        "message": "Can't add new tweet. "
                        "Please check your data."
                    },
                    status_code=404,
                )
        else:
            insert_into_tweets = (
                insert(Tweets)
                .values(content=data.tweet_data, author_id=user_id)
                .returning(Tweets.id)
            )
        result = await session.execute(insert_into_tweets)
        await session.commit()
        return {"result": True, "tweet_id": result.scalars().first()}
    else:
        return JSONResponse(
            content={
                "message": "Can't add new tweet. Please check your data."
            },
            status_code=404,
        )


@app_api.post("/medias")
async def add_new_media(
    api_key: str = Header("api-key"),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
):
    """Endpoint для загрузки файлов из твита. Загрузка происходит через
    отправку формы."""
    user_id = await check_api_key(api_key, session)
    if not os.path.exists(DOWNLOADS):
        os.makedirs(DOWNLOADS)
    if file and user_id:
        check_file_id = await session.execute(
            select(Media.id).order_by(Media.id.desc()).limit(1)
        )
        res = check_file_id.scalars().first()
        if file.filename:
            extension: list[str] = file.filename.split(".")
            if res is not None:
                file_name = f"{extension[:-1]}_{res + 1}.{extension[-1]}"
            else:
                file_name = f"{extension[:-1]}_{1}.{extension[-1]}"
            file_path = os.path.join(DOWNLOADS, file_name)
            contents = file.file.read()
            file.file.close()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(contents)
            insert_into_medias = (
                insert(Media)
                .values(file=file_name, uploader_id=user_id)
                .returning(Media.id)
            )
            media_id = await session.execute(insert_into_medias)
            await session.commit()
            return {"result": True, "media_id": list(media_id)[0][0]}
    else:
        return JSONResponse(
            content={
                "message": "Can't add new media. Please check your data."
            },
            status_code=404,
        )


@app_api.delete("/tweets/{id}")
async def delete_tweet(
    id: int,
    api_key: str = Header("api-key"),
    session: AsyncSession = Depends(get_db_session),
):
    """удалить свой твит вместе с вложенными файлами"""
    user_id = await check_api_key(api_key, session)
    if user_id:
        is_your_post = await session.execute(
            select(Tweets).where(Tweets.author_id == user_id)
        )
        if is_your_post.scalars().first():
            attachments_ = await session.execute(
                delete(Tweets)
                .where((Tweets.author_id == user_id) & (id == Tweets.id))
                .returning(Tweets.attachments)
            )
            attachments = attachments_.scalars().first()
            await session.commit()
            if attachments:
                names_ = await session.execute(
                    delete(Media)
                    .where(Media.id.in_(attachments))
                    .returning(Media.file)
                )
                names: list[Row] = names_.fetchall()
                await session.commit()
                for i in names:
                    os.remove(os.path.join(DOWNLOADS, f"{i[0]}"))
            return {"result": True}
        return JSONResponse(
            content={
                "message": "Can't delete tweet. "
                "It's not yours or it's not exist."
            },
            status_code=404,
        )
    return JSONResponse(
        content={"message": "Can't delete tweet. Please check your data."},
        status_code=404,
    )


@app_api.post("/users/{id}/follow")
async def follow(
    id: int,
    api_key: str = Header("api-key"),
    session: AsyncSession = Depends(get_db_session),
):
    """зафоловить другого пользователя"""
    user_id = await check_api_key(api_key, session)
    check_id = await session.execute(select(User).where(User.id == id))
    if check_id.fetchall() and user_id and id != user_id:
        res = await session.execute(
            select(Folowers).where(
                (Folowers.following_id == id)
                & (Folowers.followers_id == user_id)
            )
        )
        if not res.fetchall():
            insert_into_folowers = insert(Folowers).values(
                followers_id=user_id, following_id=id
            )
            await session.execute(insert_into_folowers)
            await session.commit()
            return {"result": True}
        return JSONResponse(
            content={
                "message": "Can't add new follow. "
                "You're already following this user."
            },
            status_code=404,
        )
    return JSONResponse(
        content={"message": "Can't add new follow. Please check your data."},
        status_code=404,
    )


@app_api.delete("/users/{id}/follow")
async def unfollow(
    id: int,
    api_key: str = Header("api-key"),
    session: AsyncSession = Depends(get_db_session),
):
    """отписаться от другого пользователя"""
    user_id = await check_api_key(api_key, session)
    if user_id:
        await session.execute(
            delete(Folowers).where(
                (Folowers.followers_id == user_id)
                & (Folowers.following_id == id)
            )
        )
        await session.commit()
        return {"result": True}
    return JSONResponse(
        content={"message": "Can't delete following. Please check your data."},
        status_code=404,
    )


@app_api.post("/tweets/{id}/likes")
async def like(
    id: int,
    api_key: str = Header("api-key"),
    session: AsyncSession = Depends(get_db_session),
):
    """отмечать твит как понравившийся"""
    user_id = await check_api_key(api_key, session)
    check_id = await session.execute(select(Tweets.id).where(Tweets.id == id))
    if check_id.fetchall() and user_id:
        res = await session.execute(
            select(Likes.id, Likes.tweet_id, Likes.likers_id).where(
                (Likes.tweet_id == id) & (Likes.likers_id == user_id)
            )
        )
        if not res.fetchall():
            insert_into_likes = insert(Likes).values(
                tweet_id=id, likers_id=user_id
            )
            await session.execute(insert_into_likes)
            await session.commit()
            return {"result": True}
        return JSONResponse(
            content={
                "message": "Can't add like. You're already liked this tweet."
            },
            status_code=404,
        )
    return JSONResponse(
        content={"message": "Can't add like. Please check your data."},
        status_code=404,
    )


@app_api.delete("/tweets/{id}/likes")
async def delete_like(
    id: int,
    api_key: str = Header("api-key"),
    session: AsyncSession = Depends(get_db_session),
):
    """убрать отметку «Нравится»"""
    user_id = await check_api_key(api_key, session)
    if user_id:
        await session.execute(
            delete(Likes).where(
                (Likes.likers_id == user_id) & (Likes.tweet_id == id)
            )
        )
        await session.commit()
        return {"result": True}
    return JSONResponse(
        content={"message": "Can't delete like. Please check your data."},
        status_code=404,
    )


@app_api.get("/tweets")
async def feed(
    api_key: str = Header("api-key"),
    session: AsyncSession = Depends(get_db_session),
):
    """получить ленту из твитов отсортированных в
    порядке убывания по популярности от пользователей, которых он
    фоловит"""

    user_id = await check_api_key(api_key, session)
    if user_id:
        subquery = (
            select(Folowers.following_id)
            .where(Folowers.followers_id == user_id)
            .group_by(Folowers.following_id)
            .order_by(func.count(Folowers.following_id).desc())
            .scalar_subquery()
        )
        folowing_ = await session.execute(
            select(
                Tweets.id,
                Tweets.content,
                Tweets.attachments,
                Tweets.author_id,
                User.name,
            )
            .join(User, User.id == Tweets.author_id)
            .order_by(
                case([(Tweets.author_id.in_(subquery), 0)], else_=1),
                Tweets.id.desc(),
            )
        )
        folowing: list[Row] = folowing_.fetchall()
        result: dict = {"result": True, "tweets": []}
        for i in folowing:
            list_ = []
            if i[2]:
                medias_ = await session.execute(
                    select(Media.file).where(Media.id.in_(i[2]))
                )
                medias = medias_
                print("medias1:", medias)
                if medias:
                    for j in medias:
                        list_.append(os.path.join(DOWNLOADS, j[0]))
            str = {
                "id": i[0],
                "content": i[1],
                "attachments": list_,
                "author": {"id": i[3], "name": i[4]},
                "likes": [],
            }
            likes_ = await session.execute(
                select(Likes.likers_id, User.name)
                .join(User, User.id == Likes.likers_id)
                .join(Tweets, Tweets.id == Likes.tweet_id)
                .where(Tweets.id == i[0])
            )
            likes: list[Row] = likes_.fetchall()
            if likes:
                str["likes"].append(
                    {"user_id": likes[0][0], "name": likes[0][1]}
                )
            result["tweets"].append(str)
        return result
    return JSONResponse(
        content={"message": "Can't show tweets. Please check your data."},
        status_code=404,
    )


async def info_user(user_id: int, session: AsyncSession):
    user_ = await session.execute(select(User.name).where(User.id == user_id))
    user: list[Row] = user_.fetchall()
    if user:
        following_ = await session.execute(
            select(Folowers.following_id, User.name)
            .join(User, User.id == Folowers.following_id)
            .where(Folowers.followers_id == user_id)
        )
        following: list[Row] = following_.fetchall()
        follows_ = await session.execute(
            select(Folowers.followers_id, User.name)
            .join(User, User.id == Folowers.followers_id)
            .where(Folowers.following_id == user_id)
        )
        follows: list[Row] = follows_.fetchall()
        result: dict = {
            "result": True,
            "user": {
                "id": user_id,
                "name": user[0][0],
                "followers": [],
                "following": [],
            },
        }
        for i in following:
            if i[0] != user_id:
                result["user"]["following"].append({"id": i[0], "name": i[1]})
        for i in follows:
            if i[0] != user_id:
                result["user"]["followers"].append({"id": i[0], "name": i[1]})
        return result
    return False


@app_api.get("/users/me")
async def user_info(
    api_key: str = Header("api-key"),
    session: AsyncSession = Depends(get_db_session),
):
    """получить информацию о своём профиле"""
    user_id = await check_api_key(api_key, session)
    if user_id:
        return await info_user(user_id, session)
    return JSONResponse(
        content={"message": "Can't show users info. Please check your data."},
        status_code=404,
    )


@app_api.get("/users/{id}")
async def other_user_info(
    id: int,
    api_key: str = Header("api-key"),
    session: AsyncSession = Depends(get_db_session),
):
    """получить информацию о произвольном профиле по его
    id"""
    user_id = await check_api_key(api_key, session)
    if user_id:
        res = await info_user(id, session)
        if res:
            return res
        return JSONResponse(
            content={
                "message": "Can't show users info. Please check your data."
            },
            status_code=404,
        )
    return JSONResponse(
        content={"message": "Can't show users info. Please check your data."},
        status_code=404,
    )
