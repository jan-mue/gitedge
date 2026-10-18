import pytest

from app.exceptions import WorkflowError
from app.schemas.workflow_events import PullRequestContext, PullRequestEvent, PullRequestRef, PushEvent, ScheduleEvent
from app.services.actions.workflows import expand_matrix, matches_event, parse_workflow, plan_jobs


def test_yaml_actions_on_key_and_boolean_inputs() -> None:
    workflow = parse_workflow(
        "on: [push, workflow_dispatch]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo yes\n        continue-on-error: false\n"
    )
    assert matches_event(workflow, PushEvent())
    assert workflow["jobs"]["test"]["steps"][0]["continue-on-error"] is False


def test_matrix_include_does_not_replace_axes_and_exclude_matches_subsets() -> None:
    matrix = {
        "os": ["linux", "windows"],
        "node": [20, 24],
        "exclude": [{"os": "windows", "node": 20}],
        "include": [{"os": "linux", "extra": True}, {"os": "mac", "node": 24}],
    }
    assert expand_matrix({"matrix": matrix}) == [
        {"os": "linux", "node": 20, "extra": True},
        {"os": "linux", "node": 24, "extra": True},
        {"os": "windows", "node": 24},
        {"os": "mac", "node": 24},
    ]


def test_matrix_include_can_reintroduce_an_excluded_combination() -> None:
    assert expand_matrix(
        {"matrix": {"node": [20, 24], "exclude": [{"node": 20}], "include": [{"node": 20, "extra": True}]}}
    ) == [{"node": 24}, {"node": 20, "extra": True}]


@pytest.mark.parametrize(
    ("ref", "paths", "expected"),
    [
        ("refs/heads/main", ["src/a.py"], True),
        ("refs/heads/main", ["docs/a.md"], False),
        ("refs/heads/release/test", ["src/a.py"], False),
        ("refs/heads/release/v1", ["src/a.py"], True),
        ("refs/tags/v1", ["src/a.py"], False),
    ],
)
def test_event_branch_and_path_filters(ref: str, paths: list[str], expected: bool) -> None:
    definition = {"on": {"push": {"branches": ["main", "release/**", "!release/test"], "paths": ["src/**/*.py"]}}}
    assert matches_event(definition, PushEvent(ref=ref, changed_paths=paths)) is expected


@pytest.mark.parametrize(
    "jobs",
    [
        {"a": {"needs": "a", "steps": [{"run": "true"}]}},
        {"a": {"needs": "absent", "steps": [{"run": "true"}]}},
        {"a": {"services": {"db": {"image": "postgres"}}, "steps": [{"run": "true"}]}},
        {"a": {"strategy": {"matrix": {"x": list(range(257))}}, "steps": [{"run": "true"}]}},
    ],
)
def test_invalid_graphs_and_unsupported_capabilities_fail_explicitly(jobs: dict) -> None:
    with pytest.raises(WorkflowError):
        plan_jobs({"jobs": jobs}, 1200)


def test_each_matrix_job_has_its_own_identity() -> None:
    jobs = plan_jobs(
        {
            "jobs": {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "strategy": {"matrix": {"node": [20, 24]}},
                    "steps": [{"run": "true"}],
                }
            }
        },
        1200,
    )
    assert len({job.id for job in jobs}) == 2
    assert [job.matrix for job in jobs] == [{"node": 20}, {"node": 24}]


@pytest.mark.parametrize("duration", [-1, 0, "not a number", float("inf")])
def test_invalid_job_timeouts_are_reported_as_workflow_errors(duration: float | str) -> None:
    with pytest.raises(WorkflowError, match="timeout-minutes"):
        plan_jobs({"jobs": {"test": {"timeout-minutes": duration, "steps": [{"run": "echo test"}]}}}, 1200)


def test_schedules_select_the_cron_that_was_delivered() -> None:
    definition = {"on": {"schedule": [{"cron": "0 4 * * 1"}]}}
    assert matches_event(definition, ScheduleEvent(schedule="0 4 * * 1"))
    assert not matches_event(definition, ScheduleEvent(schedule="0 5 * * 1"))


def test_pr_filters_use_base_branch_and_activity_with_typed_event() -> None:
    event = PullRequestEvent(
        action="synchronize",
        ref="refs/heads/feature",
        changed_paths=["src/test.py"],
        pull_request=PullRequestContext(number=7, base=PullRequestRef(ref="main")),
    )
    definition = {"on": {"pull_request": {"types": ["synchronize"], "branches": ["main"], "paths": ["src/**"]}}}
    assert matches_event(definition, event)
    assert not matches_event(definition, event.model_copy(update={"action": "closed"}))
    assert "event_name" not in event.model_dump(mode="json")
