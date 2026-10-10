from datetime import UTC, date, datetime

from app.schemas.repository_activity import GitActivityCommit, GitActivityHistory
from app.services.repository_activity import aggregate_contributors


def test_contributors_group_email_fill_empty_weeks_and_exclude_merges() -> None:
    def commit(day: int, name: str, email: str, **kwargs: bool) -> GitActivityCommit:
        return GitActivityCommit(
            sha=str(day),
            message="Change",
            author=name,
            author_email=email,
            timestamp=int(datetime(2026, 1, day, tzinfo=UTC).timestamp()),
            is_default=kwargs.get("is_default", True),
            is_merge=kwargs.get("is_merge", False),
            additions=3,
            deletions=2,
        )

    history = GitActivityHistory(
        default_branch="main",
        commits=[
            commit(19, "New Name", "AUTHOR@example.com"),
            commit(5, "Old Name", "author@example.com"),
            commit(12, "Merge Author", "merge@example.com", is_merge=True),
            commit(13, "Branch Author", "branch@example.com", is_default=False),
        ],
    )
    contributors, series = aggregate_contributors(history)
    assert len(contributors) == 1
    author = contributors[0]
    assert author.name == "New Name"
    assert (author.commits, author.additions, author.deletions) == (2, 6, 4)
    assert [point.date for point in series] == [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19)]
    assert [point.commits for point in series] == [1, 0, 1]
    assert author.series == series


def test_empty_git_activity() -> None:
    assert aggregate_contributors(GitActivityHistory(default_branch="main")) == ([], [])
