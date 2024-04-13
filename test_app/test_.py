import json

import pytest


@pytest.mark.asyncio
async def test_add_new_tweet_without_files(async_app_client) -> None:
    '''Тест добавления твита без картинки.'''
    data = {"tweet_data": "data"}
    resp = await async_app_client.post("/api/tweets", json=data,
                                   headers={"api-key": "123a"})
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True, "tweet_id": 2}
