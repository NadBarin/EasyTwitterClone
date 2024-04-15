import json
import asyncio
import pytest

pytestmark = pytest.mark.asyncio(scope="function")


async def test_add_new_tweet_without_files(app, async_app_client) -> None:
    '''Тест добавления твита без картинки.'''
    data = {"tweet_data": "data"}
    resp = await async_app_client.post("/api/tweets", json=data,
                                       headers={"api-key": "123a"})
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True, "tweet_id": 2}


async def test_add_new_tweet_without_files_with_fail_api_key(app, async_app_client) -> None:
    '''Тест добавления твита при несуществующем api-key.'''
    data = {"tweet_data": "data2"}
    resp = await async_app_client.post("/api/tweets", json=data,
                                       headers={"api-key": "1234a"})
    data = resp.json()
    assert data == {"message": "Can't add new tweet. Please check your data."}
