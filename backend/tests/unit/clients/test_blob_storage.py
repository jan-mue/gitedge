"""Vercel Blob pagination and immutable object caching."""

from types import SimpleNamespace
from typing import TYPE_CHECKING

from app.clients.blob_storage import VercelBlobClient

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def test_vercel_lists_all_pages_with_maximum_page_size(mocker: MockerFixture) -> None:
    sdk = mocker.patch("app.clients.blob_storage.BlobClient").return_value
    sdk.list_objects = mocker.Mock(
        side_effect=[
            SimpleNamespace(blobs=[SimpleNamespace(pathname="repo/one.pack")], has_more=True, cursor="next"),
            SimpleNamespace(blobs=[SimpleNamespace(pathname="repo/one.idx")], has_more=False, cursor=None),
        ]
    )
    client = VercelBlobClient()
    assert client.list_keys("repo/") == ["repo/one.pack", "repo/one.idx"]
    assert sdk.list_objects.call_args_list == [
        mocker.call(prefix="repo/", cursor=None, limit=1000),
        mocker.call(prefix="repo/", cursor="next", limit=1000),
    ]


def test_vercel_pack_uploads_use_long_cache_lifetime_and_streamed_reads(mocker: MockerFixture, tmp_path: Path) -> None:
    sdk = mocker.patch("app.clients.blob_storage.BlobClient").return_value
    sdk.put = mocker.Mock()
    client = VercelBlobClient(access="private")
    client.put("repo/packs/hash.pack", b"pack")
    assert sdk.put.call_args.kwargs["cache_control_max_age"] == 31536000
    assert sdk.put.call_args.kwargs["access"] == "private"
    assert sdk.put.call_args.kwargs["add_random_suffix"] is False
    assert sdk.put.call_args.kwargs["overwrite"] is True
    client.download("repo/packs/hash.pack", tmp_path / "pack")
    sdk.download_file.assert_called_once_with("repo/packs/hash.pack", tmp_path / "pack", access="private")
