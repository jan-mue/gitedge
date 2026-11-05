"""Token settings constrain real API requests by repository and operation."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.usefixtures("logged_in_superuser")
def test_repository_and_operation_selection_survive_rotation(page: Page, app_url: str) -> None:
    """Issue and rotate a token through the UI, then enforce its limits in PostgreSQL-backed APIs."""
    session = {"Authorization": f"Bearer {page.evaluate('localStorage.getItem("access_token")')}"}
    api = f"{app_url}/api/v1"
    owner = page.request.get(f"{api}/users/me", headers=session).json()["name"]
    for name in ("token-selected", "token-other"):
        response = page.request.post(
            f"{api}/repositories/", headers=session, data={"owner": owner, "name": name, "is_private": True}
        )
        assert response.status == 201
    page.goto(f"{app_url}/settings")
    page.get_by_role("tab", name="Access tokens").click()
    page.get_by_label("Token name").fill("Issue automation")
    selected = page.get_by_role("checkbox", name=f"{owner}/token-selected", exact=True)
    other = page.get_by_role("checkbox", name=f"{owner}/token-other", exact=True)
    selected.check()
    page.get_by_role("checkbox", name="Create and update issues").check()
    page.get_by_role("button", name="Create token", exact=True).click()
    secret = page.get_by_label("New personal access token")
    expect(secret).to_be_visible()
    token = secret.input_value()
    auth = {"Authorization": f"Bearer {token}"}
    base = f"{api}/repositories/{owner}"
    assert page.request.get(f"{base}/token-selected", headers=auth).status == 200
    assert (
        page.request.post(f"{base}/token-selected/issues", headers=auth, data={"title": "From automation"}).status
        == 201
    )
    assert page.request.post(f"{base}/token-other/issues", headers=auth, data={"title": "Denied"}).status == 403
    assert page.request.patch(f"{base}/token-selected", headers=auth, data={"name": "denied"}).status == 403
    assert (
        page.request.get(f"{api}/{owner}/token-selected.git/info/refs?service=git-receive-pack", headers=auth).status
        == 403
    )
    page.get_by_role("button", name="I've saved my token").click()
    expect(secret).to_have_count(0)
    expect(page.locator("body")).not_to_contain_text(token)
    row = page.get_by_role("listitem").filter(has_text="Issue automation")
    row.get_by_role("button", name="Rotate", exact=True).click()
    expect(selected).to_be_checked()
    page.get_by_role("checkbox", name="Create and update issues").uncheck()
    selected.uncheck()
    other.check()
    page.get_by_role("button", name="Create replacement").click()
    expect(secret).to_be_visible()
    replacement = {"Authorization": f"Bearer {secret.input_value()}"}
    assert page.request.get(f"{base}/token-selected", headers=auth).status == 401
    assert page.request.get(f"{base}/token-selected", headers=replacement).status == 403
    assert page.request.get(f"{base}/token-other", headers=replacement).status == 200
    assert page.request.post(f"{base}/token-other/issues", headers=replacement, data={"title": "Denied"}).status == 403
    page.get_by_role("button", name="I've saved my token").click()
    row.get_by_role("button", name="Revoke", exact=True).click()
    expect(row.get_by_text("Revoked", exact=True)).to_have_count(2)
    assert page.request.get(f"{base}/token-other", headers=replacement).status == 401
