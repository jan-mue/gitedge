"""A small coverage and static-analysis fixture for the preview CI workflow."""


def greeting(name: str) -> str:
    """Return a greeting used to verify the prepared Python toolchain."""
    return f"Hello, {name}!"


assert greeting("GitEdge Actions") == "Hello, GitEdge Actions!"
print(greeting("GitEdge Actions"))
