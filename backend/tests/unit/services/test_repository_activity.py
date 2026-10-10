from datetime import UTC, date, datetime, timedelta

from app.schemas.repository_activity import GitActivityCommit, GitActivityHistory
from app.services.repository_activity import aggregate_contributors, aggregate_recent_commits


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


def test_recent_commits_cover_past_year_with_merges_and_empty_weeks() -> None:
    end = datetime(2026, 10, 10, 12, tzinfo=UTC)
    start = end - timedelta(days=365)

    def commit(sha: str, timestamp: datetime, *, is_default: bool = True, is_merge: bool = False) -> GitActivityCommit:
        return GitActivityCommit(
            sha=sha,
            message="Change",
            author="Author",
            author_email="author@example.com",
            timestamp=int(timestamp.timestamp()),
            is_default=is_default,
            is_merge=is_merge,
        )

    history = GitActivityHistory(
        default_branch="main",
        commits=[
            commit("start", start),
            commit("old", start - timedelta(seconds=1)),
            commit("end", end),
            commit("merge", end - timedelta(hours=1), is_merge=True),
            commit("branch", end, is_default=False),
            commit("future", end + timedelta(seconds=1)),
        ],
    )
    series = aggregate_recent_commits(history, end)
    assert len(series) == 53
    assert series[0].date == date(2025, 10, 6)
    assert series[-1].date == date(2026, 10, 5)
    assert series[0].commits == 1
    assert series[-1].commits == 2
    assert all(point.commits == 0 for point in series[1:-1])
    assert all(point.commits == 0 for point in aggregate_recent_commits(GitActivityHistory(default_branch="main"), end))
