import pytest


@pytest.fixture(autouse=True)
def _clean_repositories(clean_repositories: None) -> None:
    pass


@pytest.fixture(scope="session")
def app_url(backend_url: str) -> str:
    return backend_url
