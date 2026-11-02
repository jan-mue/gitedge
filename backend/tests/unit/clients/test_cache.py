"""Repository response caches must isolate identical keys between repositories."""

from typing import TYPE_CHECKING

from app.clients.cache import VercelCacheClient

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


async def test_vercel_cache_scopes_keys_and_keeps_invalidation_tags(mocker: MockerFixture) -> None:
    values: dict[str, str] = {}
    sdk = mocker.patch("app.clients.cache.AsyncRuntimeCache").return_value

    async def get(key: str) -> str | None:
        return values.get(key)

    async def put(key: str, value: str, _options: dict) -> None:
        values[key] = value

    sdk.get = mocker.AsyncMock(side_effect=get)
    sdk.set = mocker.AsyncMock(side_effect=put)
    sdk.expire_tag = mocker.AsyncMock()
    cache = VercelCacheClient("test")
    await cache.set("tree:main", "private", ttl=60, group="repo:owner/private")
    await cache.set("tree:main", "public", ttl=60, group="repo:owner/public")
    assert await cache.get("tree:main", group="repo:owner/private") == "private"
    assert await cache.get("tree:main", group="repo:owner/public") == "public"
    assert await cache.get("tree:main", group="repo:other/missing") is None
    assert sdk.set.await_args.args[2] == {"ttl": 60, "tags": ["repo:owner/public"]}
    await cache.invalidate("repo:owner/private")
    sdk.expire_tag.assert_awaited_once_with("repo:owner/private")
