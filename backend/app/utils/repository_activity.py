"""Pure aggregation of repository Git history for activity views."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.schemas.repository_activity import (
    ActivitySeriesPoint,
    ContributorActivity,
    GitActivityHistory,
)


def _week(timestamp: int) -> date:
    """Return the UTC Monday containing a commit timestamp."""
    day = datetime.fromtimestamp(timestamp, UTC).date()
    return day - timedelta(days=day.weekday())


def aggregate_recent_commits(history: GitActivityHistory, end: datetime) -> list[ActivitySeriesPoint]:
    """Count default-branch commits, including merges, by week over the past year."""
    start = end - timedelta(days=365)
    first = _week(int(start.timestamp()))
    last = _week(int(end.timestamp()))
    weeks = {
        first + timedelta(weeks=index): ActivitySeriesPoint(date=first + timedelta(weeks=index))
        for index in range((last - first).days // 7 + 1)
    }
    for commit in history.commits:
        if commit.is_default and start.timestamp() <= commit.timestamp <= end.timestamp():
            weeks[_week(commit.timestamp)].commits += 1
    return list(weeks.values())


def aggregate_contributors(history: GitActivityHistory) -> tuple[list[ContributorActivity], list[ActivitySeriesPoint]]:
    """Aggregate default-branch non-merge commits into zero-filled weekly series."""
    commits = [commit for commit in history.commits if commit.is_default and not commit.is_merge]
    if not commits:
        return [], []
    first = min(_week(commit.timestamp) for commit in commits)
    last = max(_week(commit.timestamp) for commit in commits)
    weeks = [first + timedelta(weeks=index) for index in range((last - first).days // 7 + 1)]
    totals = {week: ActivitySeriesPoint(date=week) for week in weeks}
    authors: dict[str, ContributorActivity] = {}
    buckets: dict[str, dict[date, ActivitySeriesPoint]] = {}
    for commit in commits:
        # Email identifies an author even when their display name changes.
        key = commit.author_email.casefold() or commit.author
        if key not in authors:
            authors[key] = ContributorActivity(name=commit.author)
            buckets[key] = {}
        author = authors[key]
        author.commits += 1
        author.additions += commit.additions
        author.deletions += commit.deletions
        week = _week(commit.timestamp)
        point = buckets[key].setdefault(week, ActivitySeriesPoint(date=week))
        for target in (point, totals[week]):
            target.commits += 1
            target.additions += commit.additions
            target.deletions += commit.deletions
    for key, author in authors.items():
        author.series = [buckets[key].get(week, ActivitySeriesPoint(date=week)) for week in weeks]
    return sorted(authors.values(), key=lambda author: (-author.commits, author.name)), list(totals.values())
