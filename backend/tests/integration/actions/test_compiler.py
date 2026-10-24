import httpx2 as httpx

from app.constants import BACKEND_DIR
from app.schemas.workflows import CompiledWorkflow


def test_real_bun_compiler_http_contract(actions_compiler_url: str, infrastructure: dict[str, str]) -> None:
    fixtures = BACKEND_DIR.parent / "packages/actions-runner/src/compiler/fixtures"
    request = {
        "version": 1,
        "filename": ".gitedge/workflow/basic.yaml",
        "source": (fixtures / "basic.yaml").read_text(),
        "event": {"name": "push", "ref": "refs/heads/main"},
    }
    with httpx.Client(timeout=15) as client:
        assert client.post(actions_compiler_url, json=request).status_code == 401
        response = client.post(
            actions_compiler_url,
            json=request,
            headers={"Authorization": f"Bearer {infrastructure['ACTIONS_COMPILER_TOKEN']}"},
        )
        response.raise_for_status()
        assert CompiledWorkflow.model_validate(response.json()) == CompiledWorkflow.model_validate_json(
            (fixtures / "basic.json").read_text()
        )
        rejected = client.post(
            actions_compiler_url,
            json={**request, "source": "on: [push\n"},
            headers={"Authorization": f"Bearer {infrastructure['ACTIONS_COMPILER_TOKEN']}"},
        )
        assert rejected.status_code == 422
        assert rejected.json()["issues"][0]["filename"] == request["filename"]
        assert rejected.json()["issues"][0]["line"] > 0
