"""Operator-managed images for supported Linux environments."""

from typing import Literal

from pydantic import BaseModel, Field

type LinuxRunner = Literal["ubuntu-22.04", "ubuntu-24.04", "ubuntu-26.04"]


class RunnerImage(BaseModel):
    """A prebuilt image, optionally accelerated by a matching snapshot."""

    image: str = Field(min_length=1)
    snapshot_id: str | None = None
