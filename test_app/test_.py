import io
import aiofiles
import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize('api_key', [
    '123a',
    '124a'
])
async def test_add_new_tweet_without_files(async_app_client, api_key) -> None:
    '''Тест добавления твита без картинки.'''
    data = {"tweet_data": "data"}
    resp = await async_app_client.post("/api/tweets", json=data,
                                       headers={"api-key": api_key})
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True, "tweet_id": 2}


async def test_add_new_tweet_without_files_with_fail_api_key(async_app_client) -> None:
    '''Тест добавления твита при несуществующем api-key.'''
    data = {"tweet_data": "data2"}
    resp = await async_app_client.post("/api/tweets", json=data,
                                       headers={"api-key": "1234a"})
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't add new tweet. Please check your data."}


async def test_add_new_tweet_without_files_with_fail_tweet_data(async_app_client) -> None:
    '''Тест добавления твита при неправильном формате данных.'''
    data = {"tweet_data": 123}
    resp = await async_app_client.post("/api/tweets", json=data,
                                       headers={"api-key": "123a"})
    assert resp.status_code == 422


async def test_add_new_tweet_without_files_with_fail_file_data(async_app_client) -> None:
    '''Тест добавления твита при отсуствующих media в таблице media.'''
    data = {"tweet_data": '123', 'tweet_media_ids': [1, 2]}
    resp = await async_app_client.post("/api/tweets", json=data,
                                       headers={"api-key": "123a"})
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't add new tweet. Please check your data."}


async def test_add_new_media_without_files(async_app_client) -> None:
    '''Тест добавления картинки без отправки картинки.'''
    resp = await async_app_client.post("/api/medias",
                                       headers={"api-key": "123a"})
    assert resp.status_code == 422


async def add_media(async_app_client):
    f = await aiofiles.open('test_app/image.jpg', 'rb')
    image_data = await f.read()
    files = {"file": ("image.jpg", image_data, "image/jpeg")}
    resp = await async_app_client.post("/api/medias", files=files,
                                       headers={"api-key": "123a"})
    await f.close()
    return resp


async def test_add_new_media_with_file(async_app_client) -> None:
    '''Тест добавления картинки.'''
    resp = await add_media(async_app_client)
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True, "media_id": 1}


async def test_add_new_tweet_with_file(async_app_client) -> None:
    '''Тест добавления твита с картинкой.'''
    await add_media(async_app_client)
    data = {"tweet_data": '123', 'tweet_media_ids': [1, ]}
    resp = await async_app_client.post("/api/tweets", json=data,
                                       headers={"api-key": "123a"})
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True, "tweet_id": 2}
