import platform
import sys
from typing import TYPE_CHECKING

from app.config import default_sandbox

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_intel_mac_defaults_to_docker(mocker: MockerFixture) -> None:
    mocker.patch.object(sys, "platform", "darwin")
    mocker.patch.object(platform, "machine", return_value="x86_64")
    assert default_sandbox() == "docker"


def test_apple_silicon_defaults_to_smol(mocker: MockerFixture) -> None:
    mocker.patch.object(sys, "platform", "darwin")
    mocker.patch.object(platform, "machine", return_value="arm64")
    assert default_sandbox() == "smol"
