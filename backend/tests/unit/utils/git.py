"""Real Git graphs backed by in-memory storage."""

import json
from typing import TYPE_CHECKING

from dulwich.objects import Blob, Commit, ObjectID, Tree
from dulwich.refs import Ref

from app.clients.git.blob_repository import BlobRepository
from app.clients.git.repositories import GitClient
from app.clients.git.storage import RepositoryStorage
from app.services.repositories import RepositoryService

if TYPE_CHECKING:
    from app.clients.blob_storage import BlobStorageClient
    from app.clients.cache import AbstractCacheClient
    from app.clients.git.blob_backend import BlobBackend
    from app.clients.redis import AbstractRedisClient
    from app.clients.repositories import RepositoryStore
    from app.clients.stars import StarStore
    from tests.unit.utils.fakes import FakeStores


def seed_merge_repository(
    stores: FakeStores,
    owner: str,
    name: str,
    head_branch: str = "feature",
    *,
    conflict: bool = False,
    revert_first: bool = False,
) -> tuple[str, str, str]:
    """Persist a diverged base and two PR commits without external services."""
    repo = BlobRepository.init_bare()

    def commit(files: dict[str, bytes], parents: list[ObjectID], message: bytes) -> Commit:
        tree = Tree()
        for path, content in files.items():
            blob = Blob.from_string(content)
            repo.object_store.add_objects([(blob, None)])
            tree.add(path.encode(), 0o100644, blob.id)
        repo.object_store.add_objects([(tree, None)])
        obj = Commit()
        obj.tree, obj.parents, obj.message = tree.id, parents, message
        obj.author = obj.committer = b"Original Author <original@example.com>"
        obj.author_time = obj.commit_time = 1700000000 + len(parents)
        obj.author_timezone = obj.commit_timezone = 0
        repo.object_store.add_objects([(obj, None)])
        return obj

    ancestor = commit({"code.txt": b"first\nsecond\nthird\n"}, [], b"Initial")
    first = commit({"code.txt": b"feature\nsecond\nthird\n"}, [ancestor.id], b"Feature one\n\nFirst details")
    head = commit(
        {
            "code.txt": b"first\nsecond\nthird\n" if revert_first else b"feature\nsecond\nthird\n",
            "feature.txt": b"PR file\n",
        },
        [first.id],
        b"Feature two",
    )
    base = commit(
        {"code.txt": b"conflict\nsecond\nthird\n" if conflict else b"first\nsecond\nthird updated\n"},
        [ancestor.id],
        b"Base advanced",
    )
    repo.refs[Ref(b"refs/heads/main")] = base.id
    repo.refs[Ref(f"refs/heads/{head_branch}".encode())] = head.id
    key = f"{owner}/{name}.git"
    changes = repo.get_pending_changes()
    for basename, contents in changes["pack_uploads"].items():
        stores.blob.objects[f"{key}/packs/{basename}.pack"] = contents.pack
        stores.blob.objects[f"{key}/packs/{basename}.idx"] = contents.index
    for ref, value in changes["ref_puts"].items():
        stores.redis.values[f"{key}/refs/{ref.decode()}"] = value
    stores.redis.values[f"{key}/pack-catalog:v1"] = json.dumps(sorted(changes["pack_uploads"])).encode()
    repo.object_store.close()
    return base.id.decode(), first.id.decode(), head.id.decode()


def build_repository_service(
    backend: BlobBackend,
    blob: BlobStorageClient,
    redis: AbstractRedisClient,
    cache: AbstractCacheClient,
    repository_store: RepositoryStore,
    star_store: StarStore,
) -> RepositoryService:
    """Wire the actual Git adapter to in-memory persistence for unit tests."""

    async def exists(owner: str, name: str) -> bool:
        return await repository_store.find_by_owner_and_name(owner, name) is not None

    git = GitClient(backend, RepositoryStorage(blob, redis), cache, exists)
    return RepositoryService(git, cache, repository_store, star_store)
