from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, File, UploadFile
from .models import engine, session, Base, User, Tweets, Folowers, Likes, Media
from sqlalchemy import select, insert, delete, func
from .shemas import TweetCreate
import os

DOWNLOADS = 'img'


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Создаёт таблицу если её небыло, открывает и закрывает session и engine"""
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except:
            pass
    yield
    await session.close()
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


async def check_api_key(request: Request):
    header_value = request.headers.get('api-key')
    if header_value:
        check_api_key = await session.execute(select(User.id).where(
            User.api_key == header_value))
        res = check_api_key.all()
        if res:
            return list(res)[0][0]
    return False


# требования регистрации пользователя нет: это корпоративная
# сеть и пользователи будут создаваться не нами. Но нам нужно уметь отличать
# одного пользователя от другого.
@app.post('/api/tweets')
async def add_new_tweet(data: TweetCreate, request: Request):
    """Добавить новый твит. может содержать картинку."""
    user_id = await check_api_key(request)
    if user_id:
        if data.tweet_media_ids:
            check_tweet_media = await session.execute(
                select(Media.id).where(
                    Media.id.in_(data['tweet_media_ids'])))
            insert_into_tweets = insert(Tweets).values(
                content=data.tweet_data,
                attachments=list(check_tweet_media)[0],
                author_id=user_id).returning(Tweets.id)
        else:
            insert_into_tweets = insert(Tweets).values(
                content=data.tweet_data,
                author_id=user_id).returning(Tweets.id)
        result = await session.execute(insert_into_tweets)
        await session.commit()
        return {"result": True, "tweet_id": list(result)[0][0]}
    else:
        return {"message": "Can't add new tweet. Please check your data."}


@app.post('/api/medias')
async def add_new_media(request: Request, file: UploadFile = File(...)):
    """Endpoint для загрузки файлов из твита. Загрузка происходит через
    отправку формы."""
    if file and check_api_key(request):
        try:
            if not os.path.isdir(DOWNLOADS):
                os.makedirs(DOWNLOADS)
            file_path = os.path.join(DOWNLOADS, file.filename)
            contents = file.file.read()
            with open(file_path, 'wb') as f:
                f.write(contents)
        except Exception:
            return {"message": "There was an error uploading the file"}
        finally:
            file.file.close()
        insert_into_medias = insert(Media).values(
            file=file.filename).returning(Media.id)
        media_id = await session.execute(insert_into_medias)
        await session.commit()
        return {"result": True, "media_id": list(media_id)[0][0]}
    else:
        return {"message": "Can't add new media. Please check your data."}


@app.delete('/api/tweets/<id>')
async def delete_tweet(id: int, request: Request):
    """удалить свой твит"""
    res = check_api_key(request)
    if res:
        if id == res:
            await session.execute(delete(Tweets).where(
                User.id == res and id == Tweets.id))
            await session.commit()
            return {"result": True}
        return {"message": "Can't delete tweet. It's not yours."}
    return {"message": "Can't delete tweet. Please check your data."}


@app.post('/api/users/<id>/follow')
async def follow(id: int, request: Request):
    """зафоловить другого пользователя"""
    user_id = check_api_key(request)
    check_id = await session.execute(select(User.id).where(
        User.id == id))
    if check_id and user_id:
        insert_into_folowers = insert(Folowers).values(followers_id=user_id,
                                                       following_id=id)
        await session.execute(insert_into_folowers)
        await session.commit()
        return {"result": True}
    return {"message": "Can't add new follow. Please check your data."}


@app.delete('/api/users/<id>/follow')
async def unfollow(id: int, request: Request):
    """отписаться от другого пользователя"""
    user_id = check_api_key(request)
    check_id = await session.execute(select(User.id).where(
        User.id == id))
    if check_id and user_id:
        await session.execute(delete(Folowers).where(
            Folowers.followers_id == user_id and Folowers.following_id == id))
        await session.commit()
        return {"result": True}
    return {"message": "Can't add delete following. Please check your data."}


@app.post('/api/tweets/<id>/likes')
async def like(id: int, request: Request):
    """отмечать твит как понравившийся"""
    user_id = check_api_key(request)
    check_id = await session.execute(select(Tweets.id).where(
        Tweets.id == id))
    if check_id and user_id:
        insert_into_likes = insert(Likes).values(tweet_id=id,
                                                 likers_id=user_id)
        await session.execute(insert_into_likes)
        await session.commit()
        return {"result": True}
    return {"message": "Can't add like tweet. Please check your data."}


@app.post('/api/tweets/<id>/likes')
async def del_like(post, request: Request):
    """убрать отметку «Нравится»"""
    user_id = check_api_key(request)
    check_id = await session.execute(select(Tweets.id).where(
        Tweets.id == id))
    if check_id and user_id:
        await session.execute(delete(Likes).where(
            Likes.likers_id == user_id and Likes.tweet_id == id))
        await session.commit()
        return {"result": True}
    return {"message": "Can't add delete like. Please check your data."}


@app.get('/api/tweets')
async def feed(request: Request):
    """получить ленту из твитов отсортированных в
    порядке убывания по популярности от пользователей, которых он
    фоловит"""

    user_id = check_api_key(request)
    if user_id:
        folowing = await session.execute(select(Tweets, User.name).join(
            User, User.id == Tweets.author_id).where(Tweets.author_id._in(
            select(Folowers.following_id).where(Folowers.followers_id == user_id
                                                ).order_by(
                func.count(Folowers.following_id)))))
        result = {"result": True, "tweets": []}
        for i in folowing:
            str = {"id": i[0], "content": i[1], "attachments": [i[2]],
                   "author": {"id": i[3], "name": i[4]}, "likes": []}
            for j in i[0]:
                likes = await session.execute(
                    select(Likes.likers_id, User.name).join(
                        User, User.id == Likes.likers_id).where(Tweets.id == j[0]))
                str["likes"].append({'user_id': likes[0], 'name': likes[1]})
            result["tweets"].append(str)
        return result
    return {"message": "Can't show tweets. Please check your data."}


async def info_user(user_id):
    user = await session.execute(select(User.name).where(User.id == user_id))
    following = await session.execute(
        select(Folowers.following_id, User.name).join(User, User.id == Folowers.following_id).where(
            Folowers.followers_id == user_id))
    follows = await session.execute(
        select(Folowers.followers_id, User.name).join(User, User.id == Folowers.followers_id).where(
            Folowers.following_id == user_id))
    result = {"result": True, "user": {"id": user_id, "name": user[0], "followers": [], "following": []}}
    for i in following:
        if i[0] != user_id:
            result["user"]['following'].append({"id": i[0], "name": i[1]})
    for i in follows:
        if i[0] != user_id:
            result["user"]['followers'].append({"id": i[0], "name": i[1]})
    return result


@app.get('/api/users/me')
async def user_info(request):
    """получить информацию о своём профиле"""
    user_id = check_api_key(request)
    if user_id:
        result = info_user(user_id)
        return result
    return {"message": "Can't show users info. Please check your data."}


@app.get('/api/users/<id>')
async def other_user_info(id: int, request: Request):
    """получить информацию о произвольном профиле по его
    id"""
    user_id = check_api_key(request)
    if user_id:
        result = info_user(id)
        return result
    return {"message": "Can't show users info. Please check your data."}
