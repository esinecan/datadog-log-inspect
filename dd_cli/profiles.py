"""Column profiles for different log analysis use cases."""

from typing import Dict, List


# Pre-defined column sets for different analysis tasks
PROFILES: Dict[str, List[Dict]] = {
    "list": [
        {"field": {"path": "timestamp"}},
        {"field": {"path": "service"}},
        {"field": {"path": "host"}},
        {"field": {"path": "status"}},
        {"field": {"path": "content"}},
        {"field": {"path": "trace_id"}},
    ],
    "trace": [
        {"field": {"path": "timestamp"}},
        {"field": {"path": "service"}},
        {"field": {"path": "span_id"}},
        {"field": {"path": "trace_id"}},
        {"field": {"path": "message"}},
    ],
    "k8s": [
        {"field": {"path": "timestamp"}},
        {"field": {"path": "kube_namespace"}},
        {"field": {"path": "pod_name"}},
        {"field": {"path": "container_id"}},
        {"field": {"path": "message"}},
    ],
    "minimal": [
        {"field": {"path": "timestamp"}},
        {"field": {"path": "service"}},
        {"field": {"path": "content"}},
    ],
    "full": [
        {"field": {"path": "status_line"}},
        {"field": {"path": "timestamp"}},
        {"field": {"path": "host"}},
        {"field": {"path": "service"}},
        {"field": {"path": "content"}},
        {"field": {"path": "trace_id"}},
        {"field": {"path": "span_id"}},
    ],
}


def get_profile(name: str) -> List[Dict]:
    """Get column profile by name, defaults to 'list' profile."""
    return PROFILES.get(name, PROFILES["list"])


def list_profiles() -> List[str]:
    """List available profile names."""
    return list(PROFILES.keys())
