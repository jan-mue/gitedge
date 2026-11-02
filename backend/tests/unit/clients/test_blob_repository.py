from typing import TYPE_CHECKING

from dulwich.attrs import GitAttributes, Pattern
from dulwich.config import ConfigFile
from dulwich.objects import Blob

from app.clients.git.blob_repository import BlobRepository

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_blob_normalizer_uses_requested_tree_attributes(mocker: MockerFixture) -> None:
    repo = BlobRepository()
    config = ConfigFile()
    mocker.patch.object(repo, "get_config_stack", return_value=config)
    tree = b"a" * 40
    head_attributes = GitAttributes([(Pattern(b"*.txt"), {b"text": True, b"eol": b"lf"})])
    tree_attributes = GitAttributes([(Pattern(b"*.txt"), {b"text": True, b"eol": b"crlf"})])
    get_attributes = mocker.patch.object(
        repo,
        "get_gitattributes",
        side_effect=lambda requested_tree: tree_attributes if requested_tree else head_attributes,
    )
    blob = Blob.from_string(b"hello\n")

    assert repo.get_blob_normalizer().checkout_normalize(blob, b"file.txt").data == b"hello\n"
    assert repo.get_blob_normalizer(config, tree).checkout_normalize(blob, b"file.txt").data == b"hello\r\n"
    assert repo.get_blob_normalizer(tree=tree).checkout_normalize(blob, b"file.txt").data == b"hello\r\n"
    assert get_attributes.call_args_list == [mocker.call(None), mocker.call(tree), mocker.call(tree)]
