import aiofiles
import pytest

pytestmark = pytest.mark.asyncio


async def add_media(async_app_client):
    f = await aiofiles.open("test_app/image.jpg", "rb")
    image_data = await f.read()
    files = {"file": ("image.jpg", image_data, "image/jpeg")}
    resp = await async_app_client.post(
        "/api/medias", files=files, headers={"api-key": "123a"}
    )
    await f.close()
    return resp


async def test_add_new_media_twice(async_app_client) -> None:
    await add_media(async_app_client)
    resp = await add_media(async_app_client)
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True, "media_id": 2}


async def test_add_new_media_fail_api_key(async_app_client) -> None:
    f = await aiofiles.open("test_app/image.jpg", "rb")
    image_data = await f.read()
    files = {"file": ("image.jpg", image_data, "image/jpeg")}
    resp = await async_app_client.post(
        "/api/medias", files=files, headers={"api-key": "555"}
    )
    await f.close()
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't add new media. Please check your data."}


@pytest.mark.parametrize("api_key", ["123a", "124a"])
async def test_add_new_tweet_without_files(async_app_client, api_key) -> None:
    data = {"tweet_data": "data"}
    resp = await async_app_client.post(
        "/api/tweets", json=data, headers={"api-key": api_key}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True, "tweet_id": 2}


async def test_add_new_tweet_with_file(async_app_client) -> None:
    await add_media(async_app_client)
    data = {
        "tweet_data": "123",
        "tweet_media_ids": [
            1,
        ],
    }
    resp = await async_app_client.post(
        "/api/tweets", json=data, headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True, "tweet_id": 2}


async def test_add_new_tweet_with_files_not_exist(async_app_client) -> None:
    await add_media(async_app_client)
    data = {
        "tweet_data": "123",
        "tweet_media_ids": [1, 2, 3],
    }
    resp = await async_app_client.post(
        "/api/tweets", json=data, headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {
        "message": "Can't add new tweet. " "Please check your data."
    }


async def test_add_new_tweet_with_fail_file_id(async_app_client) -> None:
    await add_media(async_app_client)
    data = {
        "tweet_data": "123",
        "tweet_media_ids": [0],
    }
    resp = await async_app_client.post(
        "/api/tweets", json=data, headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {
        "message": "Can't add new tweet. " "Please check your data."
    }


async def test_add_new_tweet_without_files_with_fail_api_key(
    async_app_client,
) -> None:
    data = {"tweet_data": "data2"}
    resp = await async_app_client.post(
        "/api/tweets", json=data, headers={"api-key": "555"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't add new tweet. Please check your data."}


async def test_delete_tweet(async_app_client) -> None:
    resp = await async_app_client.delete(
        "/api/tweets/1", headers={"api-key": "124a"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True}


async def test_delete_tweet_fail_api_key(async_app_client) -> None:
    resp = await async_app_client.delete(
        "/api/tweets/1", headers={"api-key": "555"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't delete tweet. Please check your data."}


async def test_delete_tweet_with_fail_user(async_app_client) -> None:
    resp = await async_app_client.delete(
        "/api/tweets/1", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't delete tweet. It's not yours."}


async def test_follow(async_app_client) -> None:
    resp = await async_app_client.post(
        "/api/users/1/follow", headers={"api-key": "124a"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True}


async def test_follow_exists(async_app_client) -> None:
    resp = await async_app_client.post(
        "/api/users/2/follow", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {
        "message": "Can't add new follow. You're already following this user."
    }


async def test_follow_not_exists(async_app_client) -> None:
    resp = await async_app_client.post(
        "/api/users/3/follow", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't add new follow. Please check your data."}


async def test_unfollow(async_app_client) -> None:
    resp = await async_app_client.delete(
        "/api/users/2/follow", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True}


async def test_unfollow_fail_api_key(async_app_client) -> None:
    resp = await async_app_client.delete(
        "/api/users/2/follow", headers={"api-key": "555"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {
        "message": "Can't delete following. Please check your data."
    }


async def test_like(async_app_client) -> None:
    resp = await async_app_client.post(
        "/api/tweets/1/likes", headers={"api-key": "124a"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True}


async def test_like_exists(async_app_client) -> None:
    await async_app_client.post(
        "/api/tweets/1/likes", headers={"api-key": "124a"}
    )
    resp = await async_app_client.post(
        "/api/tweets/1/likes", headers={"api-key": "124a"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {
        "message": "Can't add like. You're already liked this tweet."
    }


async def test_like_not_exists(async_app_client) -> None:
    resp = await async_app_client.post(
        "/api/tweets/2/likes", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't add like. Please check your data."}


async def test_delete_like(async_app_client) -> None:
    resp = await async_app_client.delete(
        "/api/tweets/1/likes", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {"result": True}


async def test_delete_like_fail_api_key(async_app_client) -> None:
    resp = await async_app_client.delete(
        "/api/tweets/1/likes", headers={"api-key": "555"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't delete like. Please check your data."}


async def test_feed(async_app_client) -> None:
    resp = await async_app_client.get(
        "/api/tweets", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {
        "result": True,
        "tweets": [
            {
                "id": 1,
                "content": "content",
                "attachments": None,
                "author": {"id": 2, "name": "name2"},
                "likes": [{"user_id": 1, "name": "name"}],
            }
        ],
    }


async def test_feed_fail_api_key(async_app_client) -> None:
    resp = await async_app_client.get(
        "/api/tweets", headers={"api-key": "555"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {"message": "Can't show tweets. Please check your data."}


async def test_user_info_self(async_app_client) -> None:
    resp = await async_app_client.get(
        "/api/users/me", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {
        "result": True,
        "user": {
            "id": 1,
            "name": "name",
            "followers": [],
            "following": [{"id": 2, "name": "name2"}],
        },
    }


async def test_user_info_self_fail_api_key(async_app_client) -> None:
    resp = await async_app_client.get(
        "/api/users/me", headers={"api-key": "555"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {
        "message": "Can't show users info. Please check your data."
    }


async def test_user_info_others(async_app_client) -> None:
    resp = await async_app_client.get(
        "/api/users/2", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 200
    assert data == {
        "result": True,
        "user": {
            "id": 2,
            "name": "name2",
            "followers": [{"id": 1, "name": "name"}],
            "following": [],
        },
    }


async def test_user_info_others_fail_key(async_app_client) -> None:
    resp = await async_app_client.get(
        "/api/users/1", headers={"api-key": "555"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {
        "message": "Can't show users info. Please check your data."
    }


async def test_user_info_others_fail_id(async_app_client) -> None:
    resp = await async_app_client.get(
        "/api/users/3", headers={"api-key": "123a"}
    )
    data = resp.json()
    assert resp.status_code == 404
    assert data == {
        "message": "Can't show users info. Please check your data."
    }
