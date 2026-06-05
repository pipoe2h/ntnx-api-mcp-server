# MCP Server — Developer & Tester Evaluation Guide

This document defines the test cases and scoring methodology for evaluating the Nutanix V4 MCP server's
end-to-end behaviour when connected to a real Cursor/Claude session and a live Prism Central cluster.

---

## Setup

**Prerequisites:**
- MCP server running: `nutanix-mcp serve-stdio` (auto-refresh will trigger on first run if artifacts are absent)
- Cursor connected to the server via `mcp.json`
- Live Prism Central with at least one AHV cluster
- At least one existing VM in the cluster (needed for read/update/delete tests)
- Note the extId of an existing VM for use in parametrised tests

**How to run a test case:**
1. Open a new Cursor chat (fresh context, no prior tool calls)
2. Type the prompt exactly as written
3. Record every tool call made (tool name + key arguments) from the Cursor tool call log
4. Record the final response given to the user
5. Score using the criteria in each test case

**How to record results:**

| Field | What to capture |
|---|---|
| Tool calls | Ordered list: `listOperations(search=X)`, `getOperationSchema(op=Y)`, `vmm_execute(op=Z)`, etc. |
| API endpoint hit | HTTP method + path from server logs |
| Turns to completion | Number of user messages before task was complete |
| User intervention | Did you have to re-prompt or correct the agent? |
| Final verdict | Pass / Partial / Fail |

---

## Scoring rubric

| Verdict | Criteria |
|---|---|
| **Pass** | Correct API endpoint called, correct result returned, no user intervention required |
| **Partial** | Correct result eventually, but required one retry, re-prompt, or clarification |
| **Fail** | Wrong endpoint called, wrong result, agent gave up, or user had to provide raw API details |

---

## Test Suite

---

### Category 1 — Discovery Accuracy

Tests whether the enriched index and ranked search surface the right operation at rank 1 for natural language queries.

---

#### TC-D1 — Basic list with natural language

**Prompt:**
```
show me all my virtual machines
```

**Expected tool call sequence:**
1. `listOperations(search="vm")` or `listOperations(search="list vms")` or `listOperations(search="virtual machine")`
2. `vmm_execute(operation="ahv_listVms")`

**Pass criteria:**
- `ahv_listVms` is called (not `esxi_listVms` and not a wrong namespace)
- Response contains a list of VMs or an empty list
- No user intervention

**What to watch for:** Does the agent default to AHV without being told? Does it skip `listOperations` and guess the operation directly?

---

#### TC-D2 — Vocabulary mismatch (backup / recovery)

**Prompt:**
```
list all recovery points
```

**Expected tool call sequence:**
1. `listOperations(search="recovery point")` or `listOperations(search="recovery")`
2. `dataprotection_execute(operation="listRecoveryPoints")`

**Pass criteria:**
- `dataprotection` namespace is used, not `vmm` or `prism`
- `listRecoveryPoints` or equivalent is called

**What to watch for:** Does the agent end up in the wrong namespace? How many `listOperations` calls does it take?

---

#### TC-D3 — Ambiguous query requiring namespace disambiguation

**Prompt:**
```
list all alerts
```

**Expected tool call sequence:**
1. `listOperations(search="alert")` or `listOperations(search="list alerts")`
2. `monitoring_execute(operation="listAlerts")`

**Pass criteria:**
- `monitoring` namespace used
- `listAlerts` called

---

#### TC-D4 — Operation that requires variant selection

**Prompt:**
```
list all ESXi virtual machines
```

**Expected tool call sequence:**
1. `listOperations(search="esxi vm")` or `listOperations(search="list vms")`
2. `vmm_execute(operation="esxi_listVms")`

**Pass criteria:**
- `esxi_listVms` is called (not `ahv_listVms`)

**What to watch for:** Does the agent correctly pick the ESXi variant when the user specifies ESXi?

---

### Category 2 — Write Operations

Tests whether schema resolution and server-side validation make write operations deterministic.

---

#### TC-W1 — Create VM with minimal params

**Prompt:**
```
create a VM named test-mcp-vm with 2 vCPUs and 4GB RAM
```

**Expected tool call sequence:**
1. `listOperations(search="create vm")`
2. `getOperationSchema(operation="createVm")`
3. `vmm_execute(operation="createVm", request_body={name, numSockets, memorySizeBytes, ...})`
4. `prism_execute(operation="getTaskById", ...)` — polls async task

**Pass criteria:**
- `request_body_schema` is used by agent to construct payload (check: does `getOperationSchema` response contain it?)
- POST fires to `/vmm/v4.3/ahv/config/vms`
- Task polling happens — agent does not stop at the task reference
- VM is created (verify in PC UI)

**What to watch for:** Does the agent call `getOperationSchema` before execute? Does it pass `memorySizeBytes` as integer (not string like `"4GB"`)?

---

#### TC-W2 — Create category

**Prompt:**
```
create a category with key Environment and value Production
```

**Expected tool call sequence:**
1. `listOperations(search="create category")`
2. `getOperationSchema(operation="createCategory")`
3. `prism_execute(operation="createCategory", request_body={key, value})`

**Pass criteria:**
- Correct namespace (`prism`)
- Category created in PC

---

#### TC-W3 — Update VM name (tests ETag auto-fetch)

**Prompt:**
```
rename VM with extId <use a real extId> to renamed-by-mcp
```

**Expected tool call sequence:**
1. `listOperations(search="update vm")`
2. `getOperationSchema(operation="ahv_updateVmById")`
3. `vmm_execute(operation="ahv_updateVmById", extId=<id>, request_body={name: "renamed-by-mcp"})`

**Pass criteria:**
- PUT fires to `/vmm/v4.3/ahv/config/vms/<extId>`
- Server auto-fetched ETag (no 428 error in logs)
- VM name updated in PC

**What to watch for:** Does a 428 Precondition Required error appear? If it does, ETag auto-fetch is not working for this operation.

---

#### TC-W4 — Server-side validation catches wrong type

**Prompt:**
```
create a VM named type-test-vm with memory size "four gigabytes"
```

**Expected tool call sequence:**
1. `listOperations`, `getOperationSchema`
2. `vmm_execute(operation="createVm", request_body={memorySizeBytes: "four gigabytes"})`
3. Server returns `invalid_request_body` error with field_errors
4. Agent corrects and retries with integer value

**Pass criteria:**
- Server returns `invalid_request_body` (not a Nutanix 400 error)
- `field_errors` contains `memorySizeBytes` with `expected_type: integer`
- Agent retries with correct value without re-running `listOperations`

---

### Category 3 — Action Operations

Tests operations that trigger async actions (power on/off, reboot).

---

#### TC-A1 — Power on a VM

**Prompt:**
```
power on the VM with extId <use a real extId of a powered-off VM>
```

**Expected tool call sequence:**
1. `listOperations(search="power on")`
2. `vmm_execute(operation="ahv_powerOnVm", extId=<id>)`
3. `prism_execute(operation="getTaskById", ...)` — task poll

**Pass criteria:**
- `ahv_powerOnVm` called (not ESXi variant)
- No ETag fetch attempted (action endpoint — `/$actions/power-on`)
- Task polled to completion
- VM powered on in PC

**What to watch for:** Does the server correctly skip ETag fetch for `/$actions/` paths?

---

#### TC-A2 — Shutdown a VM

**Prompt:**
```
gracefully shut down VM named <known VM name>
```

**Expected tool call sequence:**
1. `listOperations(search="list vms")` — find the VM first
2. `vmm_execute(operation="ahv_listVms", _filter="name eq '<name>'")`
3. `listOperations(search="shutdown")`
4. `vmm_execute(operation="ahv_shutdownGuestVm", extId=<found extId>)`

**Pass criteria:**
- Agent correctly resolves name → extId before calling shutdown
- Graceful shutdown called (not power-off)

---

### Category 4 — Multi-Step Flows

Tests whether the agent chains multiple tool calls correctly across a single user request.

---

#### TC-M1 — List then act

**Prompt:**
```
find all VMs that are powered off and tell me their names
```

**Expected tool call sequence:**
1. `listOperations(search="list vms")`
2. `vmm_execute(operation="ahv_listVms")`
3. Agent filters and reports powered-off VMs from response

**Pass criteria:**
- Single `listVms` call with filter or post-filtering in agent reasoning
- Correct VM names reported

---

#### TC-M2 — Cross-namespace flow

**Prompt:**
```
show me the current tasks running on the cluster
```

**Expected tool call sequence:**
1. `listOperations(search="list tasks")`
2. `prism_execute(operation="listTasks")`

**Pass criteria:**
- `prism` namespace used (not `vmm` or `monitoring`)
- Task list returned

---

### Category 5 — Error Recovery

Tests whether the agent recovers cleanly from expected failure modes.

---

#### TC-E1 — Discovery zero results → retry

**Prompt:**
```
show me all hypervisor nodes
```

**Expected behaviour:**
1. `listOperations(search="hypervisor nodes")` → 0 results
2. Agent retries: `listOperations(search="host")` or `listOperations(search="clustermgmt")`
3. `clustermgmt_execute(operation="listHosts")`

**Pass criteria:**
- Agent retries with different keyword on zero results
- Correct operation eventually called

---

#### TC-E2 — Unknown extId

**Prompt:**
```
get VM with extId 00000000-0000-0000-0000-000000000000
```

**Expected behaviour:**
1. `vmm_execute(operation="ahv_getVmById", extId="00000000-0000-0000-0000-000000000000")`
2. Nutanix returns 404
3. Agent reports resource not found clearly

**Pass criteria:**
- Agent does not retry with guessed IDs
- Clear "not found" message to user

---

---

## Category 6 — Real-World Scenarios

These are end-to-end natural language scenarios that mirror actual operator intent. They test the full pipeline:
intent understanding → multi-step discovery → schema resolution → execution → result interpretation.
A pass means the agent completed the task correctly with no user correction.

---

#### TC-R1 — VM sizing recommendation with hardware check

**Prompt:**
```
I need to spin up a VM for my Oracle DB server. What would you recommend its config should be
and does my hardware have enough resources to get it up?
```

**Expected tool call sequence:**
1. `listOperations(search="list hosts")` or `listOperations(search="cluster")` → cluster capacity
2. `clustermgmt_execute(operation="listHosts")` or `clustermgmt_execute(operation="getClusterById")` → fetch available CPU/memory
3. `clustermgmt_execute(operation="listDisks")` or `getStorageStats` → available storage
4. Agent reasons over available resources and recommends config (vCPUs, memory, disk)
5. `listOperations(search="create vm")` → `getOperationSchema(operation="createVm")`
6. `vmm_execute(operation="createVm", request_body={...})`

**Pass criteria:**
- Agent fetches actual cluster capacity before recommending — does not invent numbers
- Recommendation is grounded in real available resources (e.g. "your cluster has 48 free vCPUs and 192GB free RAM, recommend 8 vCPUs and 32GB for Oracle")
- VM is created with the recommended config
- Agent flags if resources are insufficient rather than proceeding blindly

**What to watch for:** Does the agent recommend based on real data or training knowledge alone? Does it check both CPU and memory, not just one?

---

#### TC-R2 — Rename VM and verify the change

**Prompt:**
```
Rename the VM called test-vm to prod-oracle-01 and confirm the change went through
```

**Expected tool call sequence:**
1. `listOperations(search="list vms")` → `vmm_execute(operation="ahv_listVms", _filter="name eq 'test-vm'")`
2. Extract extId from result
3. `getOperationSchema(operation="updateVmById")` → note immutable_fields
4. `vmm_execute(operation="ahv_getVmById", extId=...)` → fetch full current body
5. `vmm_execute(operation="updateVmById", extId=..., request_body={...name: "prod-oracle-01"...})`
6. `vmm_execute(operation="ahv_getVmById", extId=...)` → verify name changed

**Pass criteria:**
- Agent correctly resolves name → extId before updating
- Full PUT body sent (not just `{name: "prod-oracle-01"}`)
- Agent verifies the rename by re-fetching rather than assuming success

---

#### TC-R3 — Find and power on all powered-off VMs

**Prompt:**
```
Find all VMs that are currently powered off and power them on
```

**Expected tool call sequence:**
1. `vmm_execute(operation="ahv_listVms", _filter="powerState eq 'OFF'")` or list + filter client-side
2. For each powered-off VM: `vmm_execute(operation="ahv_powerOnVm", extId=...)`
3. `prism_execute(operation="getTaskById", extId=...)` for each power-on task
4. Summary of how many VMs were powered on

**Pass criteria:**
- Agent correctly filters for powered-off VMs, not all VMs
- Power-on called per VM (not a single bulk call)
- Tasks polled to confirm completion before reporting success

**What to watch for:** Does the agent handle 0 powered-off VMs gracefully ("all VMs are already running")?

---

#### TC-R4 — Create a category and tag a VM

**Prompt:**
```
Create a category called Environment with value Production, then tag my VM named web-server-01 with it
```

**Expected tool call sequence:**
1. `listOperations(search="create category")` → `prism_execute(operation="createCategory", request_body={key:"Environment", value:"Production"})`
2. `vmm_execute(operation="ahv_listVms", _filter="name eq 'web-server-01'")` → get extId
3. `listOperations(search="associate categories")` → `vmm_execute(operation="ahv_associateCategories", extId=..., request_body={categories:[...]})`

**Pass criteria:**
- Category created first, VM tagged second — correct ordering
- Category extId from step 1 used in step 3 — agent carries context between calls
- Both operations confirmed

---

#### TC-R5 — Storage health check before provisioning

**Prompt:**
```
I want to create a new volume group with 500GB. Before doing that, check if I have enough
free storage on the cluster and which storage container I should use
```

**Expected tool call sequence:**
1. `clustermgmt_execute(operation="listStorageContainers")` → list containers with free space
2. Agent identifies containers with ≥500GB free
3. Agent recommends the best container (most free space, or least contended)
4. `listOperations(search="create volume group")` → `getOperationSchema(operation="createVolumeGroup")`
5. `volumes_execute(operation="createVolumeGroup", request_body={..., diskSizeBytes: 536870912000})`

**Pass criteria:**
- Agent checks actual storage before proceeding — does not assume capacity
- Recommends a specific container by name/extId with reasoning
- Volume group created with correct byte conversion (500GB = 536,870,912,000 bytes)

**What to watch for:** Does the agent correctly convert GB → bytes? Does it pick a container or ask the user to choose?

---

#### TC-R6 — Investigate an alert and take action

**Prompt:**
```
Are there any critical alerts on the cluster right now? If yes, tell me what they are
and whether any of them require me to do something
```

**Expected tool call sequence:**
1. `listOperations(search="list alerts")` → `monitoring_execute(operation="listAlerts", _filter="severity eq 'CRITICAL'")`
2. Agent reads alert titles, messages, and affected entities
3. Agent summarises alerts with context: what is affected, what action (if any) is indicated

**Pass criteria:**
- Filters for CRITICAL severity, not all alerts
- Agent interprets alert content and explains it in plain language
- Agent distinguishes informational alerts from ones requiring action
- If no critical alerts: reports that clearly

---

#### TC-R7 — Decommission a VM safely

**Prompt:**
```
I need to decommission the VM named staging-db-01. Power it off first, wait for it to stop,
then delete it
```

**Expected tool call sequence:**
1. `vmm_execute(operation="ahv_listVms", _filter="name eq 'staging-db-01'")` → get extId
2. `vmm_execute(operation="ahv_powerOffVm", extId=...)` → task ref
3. `prism_execute(operation="getTaskById", extId=...)` → poll until SUCCEEDED
4. `vmm_execute(operation="deleteVmById", extId=...)`
5. Confirm deletion

**Pass criteria:**
- Power-off completed and confirmed before delete is attempted
- Agent does not skip the task-poll step
- Agent confirms VM is gone after deletion

**What to watch for:** Does the agent attempt to delete before power-off completes? Does it handle a VM that is already powered off?

---

#### TC-R8 — Cross-namespace infrastructure summary

**Prompt:**
```
Give me a quick health summary of my cluster: how many VMs are running, any active alerts,
and the current cluster CPU and memory utilisation
```

**Expected tool call sequence:**
1. `vmm_execute(operation="ahv_listVms")` → count VMs, filter by powerState
2. `monitoring_execute(operation="listAlerts", _filter="resolved eq false")` → open alerts
3. `clustermgmt_execute(operation="getClusterStats")` or `listHosts` → CPU/memory usage
4. Agent synthesises all three into a single coherent summary

**Pass criteria:**
- All three data sources queried (VMM + monitoring + clustermgmt)
- Numbers are real, not invented
- Summary is human-readable, not a raw JSON dump

**What to watch for:** Does the agent correctly cross namespaces? Does it present a clean summary or just paste API responses?

---

---

#### TC-R9 — Clone a VM for staging environment

**Prompt:**
```
Clone the VM named prod-web-01 to create a staging copy called staging-web-01.
The clone should be in the same network but I don't want it to auto-start.
```

**Expected tool call sequence:**
1. `vmm_execute(operation="ahv_listVms", _filter="name eq 'prod-web-01'")` → get extId
2. `getOperationSchema(operation="cloneVm")` → understand request body
3. `vmm_execute(operation="cloneVm", extId=..., request_body={name: "staging-web-01", powerState: "OFF"})`
4. `prism_execute(operation="getTaskById", extId=...)` → poll task
5. Confirm clone exists and is powered off

**Pass criteria:**
- Source VM correctly identified by name before cloning
- Clone created with correct name and powered-off state
- Task polled before reporting success

**What to watch for:** Does the agent pass the powerState constraint or assume default? Does it use the correct clone operation vs create?

---

#### TC-R10 — Pre-flight check before a cluster upgrade

**Prompt:**
```
I'm planning to upgrade my cluster software. Before I start, check: are all VMs powered on,
are there any unresolved alerts, and is there enough free memory to tolerate losing one host
during a rolling upgrade?
```

**Expected tool call sequence:**
1. `vmm_execute(operation="ahv_listVms")` → count VMs, check powerState
2. `monitoring_execute(operation="listAlerts", _filter="resolved eq false")` → open alerts
3. `clustermgmt_execute(operation="listHosts")` → per-host CPU/memory
4. Agent calculates: if one host is removed, is remaining memory enough for all running VMs?
5. Agent produces a go/no-go recommendation with evidence

**Pass criteria:**
- All three checks executed (not just one or two)
- Memory headroom calculation is based on real data, not assumptions
- Agent gives a clear go/no-go with specific numbers ("removing host X would leave 180GB free, your VMs need 140GB — safe to proceed")
- Unresolved alerts are surfaced as a risk even if not blocking

**What to watch for:** Does the agent understand the rolling upgrade constraint (N-1 host tolerance) or just report raw numbers?

---

#### TC-R11 — Assign a VM to a project and verify permissions

**Prompt:**
```
Assign the VM named dev-app-server to the project called DevTeam-Q2 and
verify that the correct ownership is reflected
```

**Expected tool call sequence:**
1. `vmm_execute(operation="ahv_listVms", _filter="name eq 'dev-app-server'")` → VM extId
2. `iam_execute(operation="listProjects")` or similar → find DevTeam-Q2 project extId
3. `getOperationSchema(operation="updateVmById")` → understand project field
4. `vmm_execute(operation="ahv_getVmById", extId=...)` → full current body
5. `vmm_execute(operation="updateVmById", extId=..., request_body={...project: {extId: "..."}})`
6. `vmm_execute(operation="ahv_getVmById", extId=...)` → confirm projectExtId updated

**Pass criteria:**
- Agent resolves both VM name → extId and project name → extId
- Full PUT body sent with only the project field changed
- Ownership verified by re-fetching, not assumed from the PUT response

---

#### TC-R12 — Diagnose why a VM is not reachable

**Prompt:**
```
My VM called api-gateway-01 is not responding to requests. Can you check its power state,
network configuration, and whether there are any related alerts?
```

**Expected tool call sequence:**
1. `vmm_execute(operation="ahv_listVms", _filter="name eq 'api-gateway-01'")` → extId + powerState
2. `vmm_execute(operation="ahv_getVmById", extId=...)` → NIC config, IP address
3. `monitoring_execute(operation="listAlerts", _filter="...")` → alerts related to this VM or host
4. Agent synthesises: is it powered off, has no IP, or is there a related alert?

**Pass criteria:**
- Agent checks power state, network config, and alerts independently
- Agent presents a diagnosis with the most likely cause first
- If VM is powered off: agent offers to power it on
- If network misconfigured: agent identifies the NIC issue

**What to watch for:** Does the agent stop after finding the first issue, or check all three dimensions before diagnosing?

---

#### TC-R13 — Set up a protection policy for critical VMs

**Prompt:**
```
I have three VMs: db-primary, db-replica, and db-arbiter. Set up a recovery point schedule
that takes hourly snapshots and keeps them for 7 days
```

**Expected tool call sequence:**
1. `vmm_execute(operation="ahv_listVms")` with filter for each VM name → collect extIds
2. `listOperations(search="protection policy")` → discover protection namespace
3. `getOperationSchema(operation="createProtectionPolicy")` → understand schedule schema
4. `datapolicies_execute(operation="createProtectionPolicy", request_body={schedules: [{rpoSecs: 3600, retentionPolicy: {...7 days...}}]})`
5. Associate VMs with the policy

**Pass criteria:**
- All three VMs resolved to extIds before policy creation
- Schedule correctly specifies 1-hour RPO (3600 seconds) and 7-day retention
- VMs associated with policy after creation

**What to watch for:** Does the agent understand RPO units (seconds, not hours)? Does it associate all three VMs or only the first?

---

#### TC-R14 — Capacity planning: can I add 5 more VMs?

**Prompt:**
```
I need to add 5 more VMs to the cluster, each needing 4 vCPUs and 16GB RAM.
Do I have enough capacity, and which host would be best to place them on?
```

**Expected tool call sequence:**
1. `clustermgmt_execute(operation="listHosts")` → per-host free CPU and memory
2. `vmm_execute(operation="ahv_listVms")` → current VM density per host
3. Agent calculates: total free = sum(host free capacity), required = 5 × (4 vCPUs + 16GB)
4. Agent identifies best-fit hosts (least loaded, or most free capacity)
5. Agent recommends placement and whether it's feasible

**Pass criteria:**
- Calculation based on real cluster data
- Agent accounts for all 5 VMs, not just one
- If capacity is insufficient: agent says so with specific numbers ("you need 80GB, cluster has 60GB free")
- If feasible: agent recommends specific hosts by name

---

#### TC-R15 — Audit all VMs not belonging to any project

**Prompt:**
```
Give me a list of all VMs that are not assigned to any project.
These are likely unmanaged — I want to review them.
```

**Expected tool call sequence:**
1. `vmm_execute(operation="ahv_listVms")` → full VM list with projectExtId field
2. Agent filters: VMs where projectExtId is null or absent
3. Agent presents list with VM name, power state, and creation time for each unmanaged VM

**Pass criteria:**
- Agent correctly identifies VMs with no project assignment
- Report includes enough context (name, state, age) to prioritise review
- If all VMs are assigned: reports "no unmanaged VMs found"

**What to watch for:** Does the agent handle the case where `projectExtId` field is absent vs explicitly null?

---

#### TC-R16 — Rolling VM restart with availability check

**Prompt:**
```
I need to restart all VMs in the web-tier category one at a time.
After each restart, wait for it to come back up before doing the next one.
```

**Expected tool call sequence:**
1. `prism_execute(operation="listCategories", _filter="key eq 'tier' and value eq 'web'")` → category extId
2. `vmm_execute(operation="ahv_listVms")` filtered by category → list of VMs
3. For each VM (sequentially):
   a. `vmm_execute(operation="ahv_rebootGuestVm", extId=...)`
   b. `prism_execute(operation="getTaskById", extId=...)` → poll until SUCCEEDED
   c. Brief confirmation before next VM
4. Final summary: all N VMs restarted

**Pass criteria:**
- VMs restarted one at a time, not in parallel
- Task poll confirms each restart before proceeding
- Agent does not restart next VM if previous task fails
- Correct use of guest reboot (not hard reset/power-cycle)

**What to watch for:** Does the agent parallelise when it should not? Does it distinguish between soft reboot and hard reset?

---

#### TC-R17 — Investigate storage usage and recommend cleanup

**Prompt:**
```
My cluster storage is getting full. Show me which VMs are using the most disk space
and whether any of them have snapshots I could clean up to free space.
```

**Expected tool call sequence:**
1. `clustermgmt_execute(operation="listStorageContainers")` → container usage stats
2. `vmm_execute(operation="ahv_listVms")` → VM list with disk info
3. `dataprotection_execute(operation="listRecoveryPoints")` → existing snapshots per VM
4. Agent sorts VMs by disk usage, identifies top consumers
5. Agent correlates snapshots with heavy-storage VMs, calculates recoverable space

**Pass criteria:**
- Storage data sourced from real API, not estimated
- Agent ranks VMs by actual disk usage
- Snapshot cleanup potential quantified with recoverable bytes
- Agent does not delete anything without explicit user confirmation

---

#### TC-R18 — Full VM lifecycle: create, configure, validate, tag

**Prompt:**
```
Create a new VM for our QA environment: 4 vCPUs, 8GB RAM, attached to the QA-Network subnet.
Once it's up, tag it with Environment=QA and Team=QA-Engineers, then verify it shows up
in the QA category filter.
```

**Expected tool call sequence:**
1. `networking_execute(operation="listSubnets", _filter="name eq 'QA-Network'")` → subnet extId
2. `getOperationSchema(operation="createVm")` → understand NIC and resource fields
3. `vmm_execute(operation="createVm", request_body={numSockets:4, memorySizeBytes:8589934592, nics:[{subnet:{extId:...}}]})`
4. `prism_execute(operation="getTaskById")` → poll until VM is created
5. `prism_execute(operation="createCategory", request_body={key:"Environment", value:"QA"})`
6. `prism_execute(operation="createCategory", request_body={key:"Team", value:"QA-Engineers"})`
7. `vmm_execute(operation="ahv_associateCategories", extId=..., request_body={categories:[...]})`
8. `vmm_execute(operation="ahv_listVms", _filter="categories/any(c:c/value eq 'QA')")` → verify VM appears

**Pass criteria:**
- Subnet resolved by name before VM creation
- Memory correct in bytes (8GB = 8,589,934,592)
- Both categories created and applied
- Verification query returns the new VM

**What to watch for:** Does the agent correctly pass NIC with subnet extId? Does it create categories before associating them?

---

## Real-World Scenario Tracking (Extended)

| Test | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| TC-R9 (Clone for staging) | | | | |
| TC-R10 (Pre-upgrade preflight) | | | | |
| TC-R11 (Assign VM to project) | | | | |
| TC-R12 (Diagnose unreachable VM) | | | | |
| TC-R13 (Protection policy for DB VMs) | | | | |
| TC-R14 (Capacity planning for 5 VMs) | | | | |
| TC-R15 (Audit unmanaged VMs) | | | | |
| TC-R16 (Rolling restart with availability) | | | | |
| TC-R17 (Storage audit and cleanup) | | | | |
| TC-R18 (Full VM lifecycle) | | | | |


## Real-World Scenario Tracking

| Test | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| TC-R1 (Oracle VM sizing) | | | | |
| TC-R2 (Rename + verify) | | | | |
| TC-R3 (Power on all OFF) | | | | |
| TC-R4 (Category + tag VM) | | | | |
| TC-R5 (Storage check + VG) | | | | |
| TC-R6 (Alert investigation) | | | | |
| TC-R7 (Decommission VM) | | | | |
| TC-R8 (Infrastructure summary) | | | | |


---

## Baseline Tracking

Run TC-D1 through TC-E2 before and after each improvement and record results here.

| Test | Pre-fix | Post-fix | Change |
|---|---|---|---|
| TC-D1 | | | |
| TC-D2 | | | |
| TC-D3 | | | |
| TC-D4 | | | |
| TC-W1 | | | |
| TC-W2 | | | |
| TC-W3 | | | |
| TC-W4 | | | |
| TC-A1 | | | |
| TC-A2 | | | |
| TC-M1 | | | |
| TC-M2 | | | |
| TC-E1 | | | |
| TC-E2 | | | |

**Pass rate:** X / 14

---

## Key Metrics to Track Per Run

| Metric | Target |
|---|---|
| Average tool calls per successful task | ≤ 4 |
| Tasks requiring user intervention | 0 |
| Tasks failing due to wrong operation | 0 |
| Write operations hitting Nutanix 400 errors | 0 |
| 428 Precondition Required errors | 0 |
