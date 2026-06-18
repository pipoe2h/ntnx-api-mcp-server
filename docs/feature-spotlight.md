# Feature spotlight: Nutanix V4 API MCP Server

> **New here?** See the [README](../README.md) for an overview of what this server does, how to install it, and the full list of supported namespaces.

Jump to the section for your workload. This spotlight profiles all 19 supported namespaces. The first five — Discovery, Data protection, Lifecycle, Networking, and Prism — include detailed coverage with example interactions. The remaining fourteen are summarised in the [Additional namespaces](#additional-namespaces) section that follows.

Tool counts reflect the current default artifact set. When connected to a fully-upgraded Prism Central, up to 19 namespace tools register automatically for a total of 23 tools.

> **Note:** Some namespaces listed here are only available when the corresponding optional service is deployed and licensed on the Prism Central instance. If a namespace is absent after running `nutanix-mcp init`, the service is either not deployed or not exposed by your PC version — this is expected behavior, not an error.

---

## Discovery

### What it covers

4 always-on, read-only tools that expose the server's own operation index. No Nutanix API call is made; they query an in-memory index built from the downloaded OpenAPI specs at startup.

### What you can do

- Search all available operations by keyword, namespace, or path fragment
- Retrieve the full request schema — parameters, body shape, OData options — for any operation before executing it
- Fetch ready-to-run code samples (Python, curl, etc.) for a specific operation
- Look up the exact Nutanix RBAC roles required for an operation before you attempt it
- Paginate up to 500 results per query when exploring broad namespaces
- Combine namespace filter and keyword to narrow to a single domain (e.g., `namespace=dataprotection`, `search=recovery`)

### Example interaction

> **User:** What data-protection operations are available, and which roles do they require?
>
> **Server:** Returns a paginated list of all 31 `dataprotection` operations. Each entry includes the HTTP method, API path, one-line summary, and the `required_roles` array extracted from the OpenAPI `x-permissions` block — so you can see before calling that `createRecoveryPoint` requires a Backup Admin role.

### Who benefits most

Platform engineers and AI agent developers who need to explore API coverage or wire up automated workflows without reading raw OpenAPI specs.

### Required Nutanix role

No Nutanix API call is made. Any valid credential (used to start the server) is sufficient.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Data protection

### What it covers

The Nutanix V4 Data Protection API: recovery points, consistency groups, recovery plans, and cross-cluster replication. Covers both VM-level and volume-group-level protection primitives.

31 operations across GET, POST, PUT, and DELETE. Several operations are destructive — including `deleteRecoveryPointById`, `unplannedFailoverRecoveryPlan`, and `plannedFailoverRecoveryPlan`.

### What you can do

- List, create, and delete consistency groups across a cluster
- Create on-demand recovery points for VMs or volume groups
- Restore a VM from any listed recovery point in-place
- Replicate a recovery point to a remote cluster
- Validate a recovery plan before committing to a failover
- Execute planned or unplanned failover of a recovery plan
- Run a non-destructive test failover and retrieve execution step results
- Set or update expiration times on recovery points to manage retention

### Example interaction

> **User:** Run a planned failover for recovery plan `rp-prod-east` and show me the job status.
>
> **Server:** Invokes `plannedFailoverRecoveryPlan` with the plan ID. Returns the recovery plan job object — including `extId`, `status` (QUEUED / RUNNING / SUCCEEDED / FAILED), start time, and a list of execution step IDs you can query for granular progress via `listExecutionStepsByRecoveryPlanJobId`.

### Who benefits most

Backup administrators and DR engineers who need to automate or audit failover workflows across Nutanix clusters.

### Required Nutanix role

Backup Admin — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Lifecycle

### What it covers

The Nutanix LCM (Lifecycle Manager) and Foundation Central APIs: cluster provisioning, node imaging, software upgrades, image management, and automated deployment workflows.

110 operations — the largest namespace in the current artifact set. Includes destructive operations: `deleteClusterById`, `deleteNodeById`, `deleteBundleById`, `imageNode`, `performUpgrade`.

### What you can do

- List clusters registered with Foundation Central and create new ones
- Query LCM entity inventory and available component versions across a cluster
- Trigger a software upgrade after computing LCM recommendations
- Upload, publish, and delete OS/hypervisor images
- Image and configure individual nodes (bare-metal provisioning)
- Create and manage claim tokens for secure node onboarding
- Run pre-checks before an upgrade to surface blockers without executing the upgrade
- Build, list, and delete deployment workflows; track workflow status end-to-end

### Example interaction

> **User:** Are there any LCM updates available for my cluster, and what are the recommended upgrade selections?
>
> **Server:** Calls `listEntities` to retrieve the current inventory, then `computeRecommendations` to return a ranked list of upgrade candidates — each with component name, current version, target version, and any blocking pre-check conditions. You can then call `performPrechecks` against a specific selection before committing.

### Who benefits most

Infrastructure admins and SREs responsible for cluster lifecycle, patching cadence, and bare-metal provisioning at scale.

### Required Nutanix role

Cluster Admin or Super Admin for LCM upgrade operations; Infrastructure Admin for Foundation Central node operations — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Networking

### What it covers

A focused slice of the Nutanix V4 Networking API covering capability discovery and AWS cloud integration. With 3 GET-only operations this namespace is intentionally narrow — all operations are read-only and non-destructive.

### What you can do

- Retrieve the networking capabilities advertised by the connected Prism Central instance
- List AWS VPCs visible to Prism Central for hybrid-cloud network planning
- List AWS subnets within a specific VPC for VM placement decisions

### Example interaction

> **User:** What AWS VPCs is my Prism Central currently aware of?
>
> **Server:** Calls `getAwsVpcs` and returns each VPC's ID, CIDR block, region, and availability zones — giving you the raw inventory needed to plan subnet assignments before provisioning workloads in a hybrid Nutanix/AWS environment.

### Who benefits most

Network architects and cloud platform teams evaluating Nutanix hybrid-cloud connectivity or automating infrastructure discovery across on-prem and AWS.

### Required Nutanix role

Network Admin or Viewer — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Prism

### What it covers

The Nutanix V4 Prism Central management API: Prism Central (domain manager) lifecycle, categories, task management, backup and restore of the PC itself, cluster registration, and witness/quorum relationships.

73 operations across the full administrative surface of Prism Central. Includes destructive operations: `deleteBackupTargetById`, `deleteDomainManagerProtectionPlanById`, `removeRootCertificate`, `unregister`, `unconfigureConnection`.

### What you can do

- Create, list, update, and delete categories (and share/unshare them across domain managers)
- Register and unregister clusters with Prism Central
- List, inspect, and cancel tasks running on Prism Central
- Configure and manage PC backup targets and initiate a PC restore
- Scale up a domain manager or update its credentials and RPO configuration
- Manage witness relationships for stretched clusters
- Add or remove trust relationships between Prism Central instances
- Run and monitor multi-step batch operations via the batch submission API

### Example interaction

> **User:** Show me all tasks that failed in the last hour on Prism Central.
>
> **Server:** Calls `listTasks` with an OData `_filter` expression scoped to `status eq 'FAILED'` and a time-range predicate. Returns each task's `extId`, `operationType`, `errorMessages`, `startTime`, and `completionTime` — giving you a structured audit trail without logging into the Prism Central UI.

### Who benefits most

Prism Central administrators and SREs who manage PC health, cluster onboarding, category governance, or need programmatic access to task audit logs.

### Required Nutanix role

Prism Admin or Super Admin for full access; Viewer role sufficient for read-only list/get operations — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Additional namespaces

The following 14 namespaces are available when your Prism Central version supports them. Run `nutanix-mcp init` with `PC_HOST` configured to download the applicable artifacts, then call `listOperations(namespace="<name>")` after setup to see all available operations and their parameters.

---

## AIOps

### What it covers

The Nutanix V4 AIOps API covers intelligent operations including workload analysis, capacity planning, VM rightsizing recommendations, and automation playbook management.

### What you can do

- Retrieve capacity planning analysis and VM rightsizing recommendations
- Query workload performance data and historical trends
- Manage automation playbooks for routine operations
- Access AI-driven insights for infrastructure optimisation

### Required Nutanix role

Viewer for read-only analysis; Operator or Prism Central Admin for playbook management — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Cluster management

### What it covers

The Nutanix V4 Cluster Management API covers host and cluster inventory, cluster configuration, and Nutanix infrastructure management.

### What you can do

- List and inspect clusters, hosts, and nodes registered with Prism Central
- Retrieve cluster configuration and health state
- Manage cluster-level settings and disk operations
- Query storage pool and container assignments

### Required Nutanix role

Viewer for read-only access; Cluster Admin or Prism Central Admin for write operations — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Data policies

### What it covers

The Nutanix V4 Data Policies API covers disaster recovery and storage policies that govern how data is protected and retained across clusters.

### What you can do

- Create and manage DR policies governing cross-cluster replication schedules
- Define storage policies for volume groups and containers
- Query existing data protection policy assignments

### Required Nutanix role

Backup Admin or Prism Central Admin — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Files

### What it covers

The Nutanix V4 Files API covers virtual file server lifecycle, NFS/SMB share management, storage provisioning, and security controls for Nutanix Files deployments.

### What you can do

- Create, update, and delete virtual file servers and shares
- Manage NFS exports and SMB configurations
- Configure file-server-level security and access controls
- Monitor file server health and capacity usage

### Required Nutanix role

Files Admin or Prism Central Admin — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## IAM

### What it covers

The Nutanix V4 IAM API covers user management, role assignments, and access policies for Prism Central.

### What you can do

- List and manage Prism Central users and service accounts
- Create and modify RBAC roles and permission sets
- Assign roles to users and query current assignments

### Required Nutanix role

Prism Central Admin for write operations; Viewer for read-only queries — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Licensing

### What it covers

The Nutanix V4 Licensing API covers license management, compliance status, and feature entitlement queries for Nutanix clusters.

### What you can do

- Retrieve license inventory and entitlement status per cluster
- Query compliance state and feature availability
- Manage license assignments across clusters

### Required Nutanix role

Prism Central Admin — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Microsegmentation

### What it covers

The Nutanix V4 Microsegmentation API covers network security policies, service groups, and address groups for Nutanix Flow Network Security.

### What you can do

- Create and manage microsegmentation security policies between VMs
- Define service groups (port/protocol sets) and address groups (IP ranges)
- Query existing policy state and evaluate policy coverage

### Required Nutanix role

Network Admin or Prism Central Admin — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Monitoring

### What it covers

The Nutanix V4 Monitoring API covers alerts, alert policies, events, and audit logs for Prism Central.

### What you can do

- List active and resolved alerts with filtering by severity and entity type
- Create and manage alert policies and notification rules
- Query the Prism Central event and audit log

### Required Nutanix role

Viewer for read-only access; Operator or Prism Central Admin for alert policy management — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Multi-domain

### What it covers

The Nutanix V4 Multi-domain API covers cross-domain services across on-premises Prism Central, Nutanix Cloud Clusters (NC2), and edge deployments.

### What you can do

- Query cross-domain resource inventory and topology
- Manage service configurations spanning multiple Prism Central domains
- Support workload placement decisions across hybrid and edge environments

### Required Nutanix role

Prism Central Admin — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Objects

### What it covers

The Nutanix V4 Objects API covers the Nutanix Object Store service for S3-compatible object storage on Nutanix clusters.

### What you can do

- Create and manage object store instances on Nutanix clusters
- Query object store capacity and configuration
- Manage access policies for object store buckets

### Required Nutanix role

Objects Admin or Prism Central Admin — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Operations management

### What it covers

The Nutanix V4 Operations Management API provides shared platform functionality that underpins AIOps, DevOps, SecOps, and FinOps workflows across the Nutanix platform.

### What you can do

- Access shared operational data and platform-level metrics
- Manage platform-level settings shared across Nutanix operational domains

### Required Nutanix role

Varies by operation; Prism Central Admin recommended for full access — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Security

### What it covers

The Nutanix V4 Security API covers encryption management, certificate lifecycle, and platform security hardening for Nutanix clusters.

### What you can do

- Manage cluster-level encryption settings and key management
- Create, renew, and delete SSL/TLS certificates used by Prism Central services
- Query security hardening state and compliance configuration

### Required Nutanix role

Prism Central Admin — security operations require elevated privileges — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Storage

### What it covers

The Nutanix V4 Storage API covers volume groups and storage containers on Nutanix clusters.

### What you can do

- Create, update, and delete volume groups and storage containers
- Manage volume group attachments and iSCSI configuration
- Query storage capacity, performance, and configuration

### Required Nutanix role

Storage Admin or Prism Central Admin — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## VMM

### What it covers

The Nutanix V4 VMM API covers the full virtual machine lifecycle on AHV (Nutanix's built-in hypervisor).

### What you can do

- Create, clone, update, power-cycle, and delete virtual machines
- Manage VM disk, NIC, and GPU configurations
- Query VM inventory, power state, and performance metrics

### Required Nutanix role

VM Admin or Prism Central Admin for write operations; Viewer for read-only access — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Volumes

### What it covers

The Nutanix V4 Volumes API covers volume group management for iSCSI block storage provisioning on Nutanix clusters.

### What you can do

- Create and manage volume groups for iSCSI block storage
- Attach and detach volume groups to VMs or external hosts
- Query volume group configuration and connection state

### Required Nutanix role

Storage Admin or Prism Central Admin — verify against your Nutanix RBAC documentation before deploying.

For role setup: [authentication and security guide](authentication.md). Get started: [quickstart guide](quickstart.md).

---

## Summary table

| Namespace | Tool | Key operations | Primary persona | Destructive ops? |
|---|---|---|---|---|
| Discovery | 4 tools (always-on) | Search operations, get schemas, fetch code samples, check permissions | Platform engineer / AI agent developer | No |
| Data protection | `dataprotection_execute` / 31 ops | Recovery points, consistency groups, planned and unplanned failover, replication | Backup admin / DR engineer | Yes — delete recovery points, execute failover |
| Lifecycle | `lifecycle_execute` / 110 ops | Cluster provisioning, LCM upgrades, node imaging, image management, workflows | Infra admin / SRE | Yes — delete clusters, nodes, images, trigger upgrades |
| Networking | `networking_execute` / 3 ops | Networking capabilities, AWS VPCs, AWS subnets | Network architect / cloud platform team | No |
| Prism | `prism_execute` / 73 ops | Categories, tasks, PC backup/restore, cluster registration, witness relationships | Prism Central admin / SRE | Yes — delete categories, cancel tasks, unregister clusters |
| AIOps | `aiops_execute` | Capacity analysis, VM rightsizing, automation playbooks | Platform SRE / Infra manager | Minimal |
| Cluster management | `clustermgmt_execute` | Cluster and host inventory, cluster configuration | Infra admin | Yes — cluster config changes |
| Data policies | `datapolicies_execute` | DR policies, storage policy management | Backup admin | Yes — policy deletion |
| Files | `files_execute` | File server lifecycle, NFS/SMB shares, security controls | Storage admin | Yes — file server deletion |
| IAM | `iam_execute` | User management, role assignments, access policies | Prism Central admin | Yes — user and role deletion |
| Licensing | `licensing_execute` | License inventory, compliance status, feature entitlements | Prism Central admin | Minimal |
| Microsegmentation | `microseg_execute` | Network security policies, service and address groups | Network admin | Yes — policy deletion |
| Monitoring | `monitoring_execute` | Alerts, alert policies, events, audit logs | SRE / operator | Minimal |
| Multi-domain | `multidomain_execute` | Cross-domain resource management, NC2 and edge services | Cloud platform team | Yes |
| Objects | `objects_execute` | Object Store lifecycle, bucket management | Storage admin | Yes — store deletion |
| Operations management | `opsmgmt_execute` | Shared platform operational data and settings | Platform SRE | Varies |
| Security | `security_execute` | Encryption management, certificate lifecycle, hardening | Security admin | Yes — cert deletion |
| Storage | `storage_execute` | Volume groups, storage containers | Storage admin | Yes — container deletion |
| VMM | `vmm_execute` | VM lifecycle, disk/NIC/GPU configuration | VM admin / SRE | Yes — VM deletion |
| Volumes | `volumes_execute` | iSCSI volume groups, attachments | Storage admin | Yes — volume deletion |

---

## Call to action

- **Try it now:** [quickstart guide](quickstart.md) — install, configure, and run your first tool call in under 15 minutes.
- **Full parameter reference:** Use `getOperationSchema(operation="<operationId>")` from within your AI client to retrieve the full schema, parameters, and response shape for any operation at runtime.
