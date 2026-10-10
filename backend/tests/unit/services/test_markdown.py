import pytest

from app.services.markdown import render_markdown


def test_gfm_features() -> None:
    html = render_markdown(
        "| Feature | Status |\n| --- | --- |\n| Markdown | ~~pending~~ |\n\n"
        "- [x] Done\n\nhttps://example.com\n\n```python\nprint('hello')\n```"
    )
    assert "<table>" in html
    assert "<s>pending</s>" in html
    assert 'type="checkbox"' in html
    assert 'href="https://example.com"' in html
    assert 'class="language-python"' in html


@pytest.mark.parametrize("content", ["<script>alert(1)</script>", '<img src="x" onerror="alert(1)">'])
def test_raw_html_is_escaped(content: str) -> None:
    html = render_markdown(content)
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;" in html


@pytest.mark.parametrize("content", ["[click](javascript:alert(1))", "![image](data:text/html;base64,PHNjcmlwdD4=)"])
def test_unsafe_links_are_rejected(content: str) -> None:
    html = render_markdown(content)
    assert "<a " not in html
    assert "<img" not in html
