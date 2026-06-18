"""Configuration defaults used during startup."""

# Maximum time (seconds) allowed for startup-time connectivity/auth probes.
DEFAULT_STARTUP_TIMEOUT_SECONDS = 30.0

# Number of retry attempts for startup-time probes before failing fast.
DEFAULT_STARTUP_RETRY_ATTEMPTS = 3

# Public namespace discovery endpoint.
DEVELOPERS_NAMESPACE_LIST_URL = "https://developers.nutanix.com/api/v1/namespaces"

# YAML download endpoint pattern.
DEVELOPERS_YAML_DOWNLOAD_TEMPLATE = (
    "https://developers.nutanix.com/api/v1/namespaces/"
    "{namespace}/versions/{version}/yaml"
)

# Namespace version listing endpoint used for latest-release artifact mode.
DEVELOPERS_NAMESPACE_VERSIONS_TEMPLATE = (
    "https://developers.nutanix.com/api/v1/namespaces/{namespace}/versions"
)

# Prism Central namespace version probe endpoint pattern.
PC_NAMESPACE_VERSION_PROBE_TEMPLATE = "https://{pc_host}:{pc_port}/api/{namespace}/unversioned/info"

# Artifact filename contract consumed by startup loaders.
ARTIFACT_FILENAME_SUFFIX = "-all-documentation.yaml"
