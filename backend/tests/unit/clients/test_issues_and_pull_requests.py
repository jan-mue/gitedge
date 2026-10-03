"""Unit tests for the issue and pull request repositories."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.clients.issues import SQLIssueRepository
from app.clients.pull_requests import SQLPullRequestRepository
from app.entities.base import Base
from app.entities.issues import Issue
from app.entities.pull_requests import PullRequest
from app.entities.repositories import Repository
from app.entities.users import User


def _session() -> Session:
    """Create an in-memory SQLite session with the schema applied.

    Returns:
        SQLAlchemy session.
    """
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_repository(session: Session) -> Repository:
    """Create a user and repository for the given session.

    Args:
        session: SQLAlchemy session.

    Returns:
        The created repository.
    """
    user = User(email="owner@example.com", hashed_password="x")
    session.add(user)
    session.commit()

    repository = Repository(name="repo", path="owner/repo.git", owner_id=user.id)
    session.add(repository)
    session.commit()
    return repository


def _make_pull_request(repository: Repository, number: int) -> PullRequest:
    """Build a pull request entity for a repository.

    Args:
        repository: The repository.
        number: Pull request number.

    Returns:
        The pull request entity.
    """
    return PullRequest(
        repo_id=repository.id,
        number=number,
        title="pull request",
        state="open",
        head_repo_id=repository.id,
        base_repo_id=repository.id,
        head_branch="feature",
        base_branch="main",
    )


def test_issue_and_pull_request_repositories_are_separate() -> None:
    """Issues and pull requests are queried independently."""
    with _session() as session:
        repository = _seed_repository(session)
        session.add(Issue(repo_id=repository.id, number=1, title="issue", state="open"))
        session.add(_make_pull_request(repository, 2))
        session.commit()

        issue_repository = SQLIssueRepository(session)
        pull_request_repository = SQLPullRequestRepository(session)

        assert [issue.number for issue in issue_repository.list_by_repo(repository.id)] == [1]
        assert [pr.number for pr in pull_request_repository.list_by_repo(repository.id)] == [2]
        assert issue_repository.count_by_state(repository.id, "open") == 1
        assert pull_request_repository.count_by_state(repository.id, "open") == 1
        assert issue_repository.get_by_number(repository.id, 2) is None
        assert pull_request_repository.get_by_number(repository.id, 1) is None


def test_issues_and_pull_requests_share_numbering() -> None:
    """Issues and pull requests draw from a shared number sequence."""
    with _session() as session:
        repository = _seed_repository(session)
        issue_repository = SQLIssueRepository(session)
        pull_request_repository = SQLPullRequestRepository(session)

        assert issue_repository.next_number(repository.id) == 1

        issue_repository.add(Issue(repo_id=repository.id, number=1, title="issue", state="open"))
        assert pull_request_repository.next_number(repository.id) == 2

        pull_request_repository.add(_make_pull_request(repository, 2))
        assert issue_repository.next_number(repository.id) == 3
