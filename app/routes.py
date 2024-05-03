import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, insert, select
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

DOWNLOADS: str = "img"


@asynccontextmanager
async def lifespan(
    app: FastAPI, session: AsyncSession = Depends(get_db_session)
):
    """Создаёт таблицу если её небыло,
    открывает и закрывает session и engine"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await session.close()
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


async def check_api_key(request: Request, session: AsyncSession):
    header_value = request.headers.get("api-key")
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
@app.post("/api/tweets")
async def add_new_tweet(
    data: TweetCreate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Добавить новый твит. может содержать картинку."""
    user_id = await check_api_key(request, session)
    if user_id:
        if data.tweet_media_ids:
            check_tweet_media = await session.execute(
                select(Media.id).where(Media.id.in_(data.tweet_media_ids))
            )
            check_tweet_media_ = check_tweet_media.fetchall()
            if set(check_tweet_media_[0]).issubset(
                data.tweet_media_ids
            ) and len(check_tweet_media_[0]) == len(data.tweet_media_ids):
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


@app.post("/api/medias")
async def add_new_media(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
):
    """Endpoint для загрузки файлов из твита. Загрузка происходит через
    отправку формы."""
    user_id = await check_api_key(request, session)
    if file and user_id:
        try:
            if not os.path.isdir(DOWNLOADS):
                os.makedirs(DOWNLOADS)
            check_file_id = await session.execute(
                select(Media.id).order_by(Media.id.desc()).limit(1)
            )
            res = check_file_id.scalars().first()
            print("res: ", res)
            if file.filename:
                extension: list[str] = file.filename.split(".")
                if res is not None:
                    file_path: str = os.path.join(
                        DOWNLOADS, f"{res + 1}.{extension[-1]}"
                    )
                else:
                    file_path = os.path.join(DOWNLOADS, f"{1}.{extension[-1]}")
                contents = file.file.read()
                with open(file_path, "wb") as f:
                    f.write(contents)
        except FileNotFoundError:
            return JSONResponse(
                content={
                    "message": "Can't add new media. Please check your data."
                },
                status_code=404,
            )
        finally:
            file.file.close()
        insert_into_medias = (
            insert(Media).values(file=file.filename).returning(Media.id)
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


@app.delete("/api/tweets/{id}")
async def delete_tweet(
    id: int, request: Request, session: AsyncSession = Depends(get_db_session)
):
    """удалить свой твит"""
    res = await check_api_key(request, session)
    if res:
        is_your_post = await session.execute(
            select(Tweets).where(Tweets.author_id == res)
        )
        if is_your_post.scalars().first():
            await session.execute(
                delete(Tweets).where(
                    (Tweets.author_id == res) & (id == Tweets.id)
                )
            )
            await session.commit()
            return {"result": True}
        return JSONResponse(
            content={"message": "Can't delete tweet. It's not yours."},
            status_code=404,
        )
    return JSONResponse(
        content={"message": "Can't delete tweet. Please check your data."},
        status_code=404,
    )


@app.post("/api/users/{id}/follow")
async def follow(
    id: int, request: Request, session: AsyncSession = Depends(get_db_session)
):
    """зафоловить другого пользователя"""
    user_id = await check_api_key(request, session)
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


@app.delete("/api/users/{id}/follow")
async def unfollow(
    id: int, request: Request, session: AsyncSession = Depends(get_db_session)
):
    """отписаться от другого пользователя"""
    user_id = await check_api_key(request, session)
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
        content={
            "message": "Can't add delete following. Please check your data."
        },
        status_code=404,
    )


@app.post("/api/tweets/{id}/likes")
async def like(
    id: int, request: Request, session: AsyncSession = Depends(get_db_session)
):
    """отмечать твит как понравившийся"""
    user_id = await check_api_key(request, session)
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


@app.delete("/api/tweets/{id}/likes")
async def del_like(
    id, request: Request, session: AsyncSession = Depends(get_db_session)
):
    """убрать отметку «Нравится»"""
    user_id = await check_api_key(request, session)
    if user_id:
        await session.execute(
            delete(Likes).where(
                Likes.likers_id == user_id and Likes.tweet_id == id
            )
        )
        await session.commit()
        return {"result": True}
    return JSONResponse(
        content={"message": "Can't add delete like. Please check your data."},
        status_code=404,
    )


@app.get("/api/tweets")
async def feed(
    request: Request, session: AsyncSession = Depends(get_db_session)
):
    """получить ленту из твитов отсортированных в
    порядке убывания по популярности от пользователей, которых он
    фоловит"""

    user_id = await check_api_key(request, session)
    if user_id:
        folowing_ = await session.execute(
            select(
                Tweets.id,
                Tweets.content,
                Tweets.attachments,
                Tweets.author_id,
                User.name,
            )
            .join(User, User.id == Tweets.author_id)
            .where(
                Tweets.author_id.in_(
                    select(Folowers.following_id)
                    .where(Folowers.followers_id == user_id)
                    .group_by(Folowers.following_id)
                    .order_by(func.count(Folowers.following_id))
                )
            )
        )
        folowing: list[Row] = folowing_.fetchall()
        result: dict = {"result": True, "tweets": []}
        for i in folowing:
            str = {
                "id": i[0],
                "content": i[1],
                "attachments": [i[2]],
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
            str["likes"].append({"user_id": likes[0][0], "name": likes[0][1]})
            result["tweets"].append(str)
        return result
    return JSONResponse(
        content={"message": "Can't show tweets. Please check your data."},
        status_code=404,
    )


async def info_user(user_id: int, session: AsyncSession):
    user_ = await session.execute(select(User.name).where(User.id == user_id))
    user: list[Row] = user_.fetchall()
    print("user_check: ", user)
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
    if user:
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
    return JSONResponse(
        content={"message": "Can't show users info. Please check your data."},
        status_code=404,
    )


@app.get("/api/users/me")
async def user_info(
    request: Request, session: AsyncSession = Depends(get_db_session)
):
    """получить информацию о своём профиле"""
    user_id = await check_api_key(request, session)
    if user_id:
        return await info_user(user_id, session)
    return JSONResponse(
        content={"message": "Can't show users info. Please check your data."},
        status_code=404,
    )


@app.get("/api/users/{id}")
async def other_user_info(
    id: int, request: Request, session: AsyncSession = Depends(get_db_session)
):
    """получить информацию о произвольном профиле по его
    id"""
    user_id = await check_api_key(request, session)
    if user_id:
        return await info_user(id, session)
    return JSONResponse(
        content={"message": "Can't show users info. Please check your data."},
        status_code=404,
    )
