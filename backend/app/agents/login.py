"""Authorize ChatGPT plan usage on the user's local loopback, as required by OpenAI.

Run `uv run python -m app.agents.login --output chatgpt-connection.json` locally,
then import the file under Agents > AI credentials. The backend never opens a
callback listener on the cloud machine on behalf of a remote browser.
"""

import argparse
import asyncio
import os
import webbrowser
from pathlib import Path

from pydantic import TypeAdapter
from pydantic_ai.providers.openai_chatgpt import OpenAIChatGPTCredentials, OpenAIChatGPTOAuthFlow


async def login(output: Path) -> None:
    """Complete SDK-managed PKCE and save a private connection file for import."""
    flow = OpenAIChatGPTOAuthFlow(app_name="GitEdge Agents")
    url = flow.authorization_url()
    print(f"Open this URL to connect ChatGPT:\n{url}")
    webbrowser.open(url)
    credentials = await flow.exchange_code_from_callback()
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(TypeAdapter(OpenAIChatGPTCredentials).dump_json(credentials))
    print(f"Import {output.name} in GitEdge AI credentials, then delete the local file.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("chatgpt-connection.json"))
    asyncio.run(login(parser.parse_args().output))
