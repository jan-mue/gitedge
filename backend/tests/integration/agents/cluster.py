"""Install the upstream controller, router and runtime into a real K3S testcontainer."""

import io
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx2
import yaml
from k8s_agent_sandbox import SandboxClient
from k8s_agent_sandbox.models import SandboxDirectConnectionConfig
from kubernetes import config

from app.constants import BACKEND_DIR
from tests.integration.agents.containers import AGENT_SANDBOX_REVISION, AGENT_SANDBOX_VERSION, AgentK3SContainer

if TYPE_CHECKING:
    from docker.models.images import Image

ROUTER_FILES = ("serviceaccount.yaml", "rbac.yaml", "deployment.yaml", "service.yaml")


def command(cluster: AgentK3SContainer, arguments: list[str]) -> str:
    """Execute kubectl in the cluster container and surface the actual failure."""
    result = cluster.exec(["kubectl", *arguments])
    if result.exit_code:
        raise RuntimeError(result.output.decode())
    return result.output.decode()


def apply(cluster: AgentK3SContainer, documents: list[dict]) -> None:
    """Transfer manifests without shell interpolation or host kubectl requirements."""
    content = yaml.safe_dump_all(documents).encode()
    target = io.BytesIO()
    with tarfile.open(fileobj=target, mode="w") as archive:
        member = tarfile.TarInfo("gitedge-resources.yaml")
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))
    target.seek(0)
    cluster.get_wrapped_container().put_archive("/tmp", target)
    command(cluster, ["apply", "-f", "/tmp/gitedge-resources.yaml"])


def load_image(cluster: AgentK3SContainer, image: Image) -> None:
    """Import pinned host images into containerd; avoid nested registry credentials."""
    with tempfile.TemporaryDirectory(prefix="gitedge-agent-image-") as directory:
        source = Path(directory) / "image.tar"
        with source.open("wb") as target:
            for chunk in image.save(named=True):
                target.write(chunk)
        archive_path = Path(directory) / "transfer.tar"
        with tarfile.open(archive_path, "w") as archive:
            archive.add(source, arcname="gitedge-image.tar")
        with archive_path.open("rb") as archive:
            cluster.get_wrapped_container().put_archive("/tmp", archive)
        result = cluster.exec(
            [
                "ctr",
                "--address",
                "/run/k3s/containerd/containerd.sock",
                "--namespace",
                "k8s.io",
                "images",
                "import",
                "/tmp/gitedge-image.tar",
            ]
        )
        if result.exit_code:
            raise RuntimeError(result.output.decode())
        cluster.exec(["rm", "/tmp/gitedge-image.tar"])


def install(cluster: AgentK3SContainer) -> SandboxClient:
    """Install real upstream resources and return the official Python SDK client."""
    docker = cluster.get_docker_client().client
    context = BACKEND_DIR.parent / "dev" / "agents"
    build = ["docker", "build", "-t", "gitedge-agent-runtime:dev"]
    certificate = os.environ.get("CODEX_PROXY_CERT") or os.environ.get("SSL_CERT_FILE")
    if certificate and Path(certificate).is_file():
        build.extend(["--secret", f"id=proxy_ca,src={certificate}"])
    subprocess.run([*build, str(context)], check=True)
    load_image(cluster, docker.images.get("gitedge-agent-runtime:dev"))
    with httpx2.Client(follow_redirects=True, timeout=60) as http:
        response = http.get(
            f"https://github.com/kubernetes-sigs/agent-sandbox/releases/download/{AGENT_SANDBOX_VERSION}/sandbox-with-extensions.yaml"
        )
        response.raise_for_status()
        controller = [item for item in yaml.safe_load_all(response.text) if item]
        router = []
        for file in ROUTER_FILES:
            response = http.get(
                f"https://raw.githubusercontent.com/kubernetes-sigs/agent-sandbox/{AGENT_SANDBOX_REVISION}/sandbox-router/deploy/{file}"
            )
            response.raise_for_status()
            router.extend(item for item in yaml.safe_load_all(response.text) if item)
    for item in router:
        if item["kind"] == "Deployment":
            item["spec"]["replicas"] = 1
            item["spec"]["template"]["spec"]["containers"][0]["image"] = (
                f"registry.k8s.io/agent-sandbox/sandbox-router-go:{AGENT_SANDBOX_VERSION}"
            )
        if item["kind"] == "Service":
            item["spec"]["type"] = "NodePort"
            item["spec"]["ports"][0]["nodePort"] = 30080
    for item in [*controller, *router]:
        if item.get("kind") in {"Deployment", "StatefulSet"}:
            for container in item["spec"]["template"]["spec"]["containers"]:
                load_image(cluster, docker.images.pull(container["image"]))
    apply(cluster, controller)
    command(cluster, ["wait", "--for=condition=Established", "--timeout=120s", "crd", "--all"])
    command(
        cluster,
        ["rollout", "status", "deployment/agent-sandbox-controller", "-n", "agent-sandbox-system", "--timeout=180s"],
    )
    apply(cluster, router)
    command(cluster, ["rollout", "status", "deployment/sandbox-router", "-n", "agent-sandbox-system", "--timeout=180s"])
    apply(cluster, list(yaml.safe_load_all((context / "sandboxes.yaml").read_text())))
    api = config.new_client_from_config_dict(yaml.safe_load(cluster.config_yaml()))
    endpoint = f"http://{cluster.get_container_host_ip()}:{cluster.get_exposed_port(30080)}"
    return SandboxClient(
        connection_config=SandboxDirectConnectionConfig(api_url=endpoint), api_client=api, cleanup=False
    )
