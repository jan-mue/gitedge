"""Repository activity statistics derived from Git history and tracker events."""

from datetime import date, datetime

from pydantic import ConfigDict, Field

from app.schemas.activity import ActivityPublic
from app.schemas.base import GitEdgeBaseModel
from app.schemas.repositories import CommitListItem


class ActivityStatisticsModel(GitEdgeBaseModel):
    """Expose defaulted statistics as required fields in API responses."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class ActivitySeriesPoint(ActivityStatisticsModel):
    """A daily or weekly bucket of non-merge commits and line changes."""

    date: date
    commits: int = 0
    additions: int = 0
    deletions: int = 0


class ContributorActivity(ActivityStatisticsModel):
    """An author's all-time contribution totals and weekly series."""

    name: str
    commits: int = 0
    additions: int = 0
    deletions: int = 0
    series: list[ActivitySeriesPoint] = Field(default_factory=list)


class GitActivityCommit(CommitListItem):
    """Cached statistics for a unique commit reachable from a branch."""

    is_default: bool
    is_merge: bool
    additions: int = 0
    deletions: int = 0
    files: list[str] = Field(default_factory=list)


class GitActivityHistory(GitEdgeBaseModel):
    """Cached history, independently of the selected pulse period."""

    default_branch: str
    commits: list[GitActivityCommit] = Field(default_factory=list)


class ActivityOverview(ActivityStatisticsModel):
    """Pulse totals for the selected period."""

    active_prs: int = 0
    active_issues: int = 0
    merged_prs: int = 0
    proposed_prs: int = 0
    closed_issues: int = 0
    new_issues: int = 0
    merge_authors: int = 0
    authors: int = 0
    commits: int = 0
    branch_commits: int = 0
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0


class RepositoryActivityStatistics(GitEdgeBaseModel):
    """Data for pulse, contributors, code frequency, and recent commits."""

    start: datetime
    end: datetime
    default_branch: str
    overview: ActivityOverview
    daily_commits: list[ActivitySeriesPoint]
    merged_prs: list[ActivityPublic]
    contributors: list[ContributorActivity]
    code_frequency: list[ActivitySeriesPoint]
    recent_commits: list[ActivitySeriesPoint]
