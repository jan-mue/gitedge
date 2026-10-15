"""The comment preview uses the same safe Markdown rendering as saved comments."""

from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def test_preview_renders_markdown_and_escapes_embedded_html(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/utils/markdown-preview", json={"body": "**Review** <script>alert(1)</script>"}
    )
    assert response.status_code == 200
    assert "<strong>Review</strong>" in response.json()
    assert "<script>" not in response.json()
    assert client.post(f"{settings.API_V1_STR}/utils/markdown-preview", json={"body": "x" * 20001}).status_code == 422
