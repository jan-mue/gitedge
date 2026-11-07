from typing import TYPE_CHECKING

from kubernetes import client, config

if TYPE_CHECKING:
    from tests.integration.agents.containers import AgentK3SContainer


def test_k3s_control_plane(agent_k3s: AgentK3SContainer) -> None:
    """Verify the real testcluster is ready before deploying sandbox resources."""
    import yaml  # noqa: PLC0415 - only needed by the optional container test

    configuration = client.Configuration()
    config.load_kube_config_from_dict(yaml.safe_load(agent_k3s.config_yaml()), client_configuration=configuration)
    with client.ApiClient(configuration) as api:
        nodes = client.CoreV1Api(api).list_node().items
        assert nodes
        for node in nodes:
            status = node.status
            assert status is not None
            assert any(
                condition.type == "Ready" and condition.status == "True" for condition in status.conditions or []
            )
