## 1. Environment & Scope
*   **Target Version:** Infoblox NIOS v9.7
*   **API Version:** WAPI v2.13.1+
*   **Cloud Focus:** AWS (Primary), Azure, AliCloud (Future)
*   **On-Prem Focus:** Core Datacenters, Campus Networks (DDNS & Static)
*   **Strategy:** Dual-Path Behavioral Scavenging.

---

## 2. Technical Architecture: The Hybrid Reaper

### Phase I: Cloud Path (Lifecycle Based)
- **Signal:** Cloud Instance Termination (API Event).
- **Verification:** vDiscovery polling.
- **Logic:** If Instance == Dead -> Purge.

### Phase II: On-Prem Path (Behavioral Based)
- **Signal 1 (Dynamic):** DHCP Lease Abstraction. If the lease is `free` or `abandoned` for X days, the linked A/PTR is scavenged.
- **Signal 2 (Static):** "Last Queried" Analytics. Leveraging the v9.7 query monitor to find "Ghost Servers."
- **Signal 3 (Discovery):** Cross-reference with v9.7 Asset Discovery (NetMRI/CNA). If a record exists but the MAC is not on the wire -> Mark Reclaimable.

---

## 3. Implementation Steps (AWS)

### Step 1: Infoblox Grid Preparation
1.  **Enable Query Monitoring:** 
    - Enable `monitor_queries` at the Grid level or specific DNS View level via WAPI.
    - *WAPI Call:* `PUT /wapi/v2.13.1/grid:dns?_return_fields=monitor_queries` -> `{"monitor_queries": true}`.
2.  **Define Multi-Cloud EAs:**
    - `Cloud_Provider`: (Enum: AWS, Azure, AliCloud)
    - `Cloud_Instance_ID`: (String)
    - `Lifecycle_Policy`: (Enum: Aggressive, Conservative, Protected)

### Step 2: AWS CNA Integration (v9.7 Patterns)
1.  **Credential Management:** Setup IAM Role for Infoblox with `Route53:ListHostedZones`, `Route53:ListResourceRecordSets`.
2.  **vDiscovery Configuration:**
    - Configure AWS vDiscovery job in NIOS 9.7.
    - Set **"Automatically Remove Records upon Instance Termination"** to `True` for non-critical zones.

### Step 3: Scavenging Policy Configuration (The Hybrid Rulebook)
Define the different risk profiles:

| Record Type | Scenario | Scavenge Rule | Verify Via |
| :--- | :--- | :--- | :--- |
| **Cloud Dynamic** | AWS/Azure | Sync on Termination | Cloud API |
| **On-Prem DDNS** | Campus/VPN | Lease End + 7 Days | DHCP DB |
| **On-Prem Static** | Data Center | No Query > 90 Days | Query Monitor |
| **Infrastructure** | Core Svcs | PROTECTED | Manual Only |

---

## 4. Scalability: Future Cloud Integration (Azure & AliCloud)

| Platform | Integration Method | NIOS 9.7 Capability |
| :--- | :--- | :--- |
| **Azure** | Native Azure Adapter | Uses Service Principal to sync with Azure Resource Graph. |
| **AliCloud** | Custom WAPI Bridge | Leverages WAPI `request` objects to proxy AliCloud API events to NIOS. |

### Designing for Portability:
The scavenging scripts (Python/Go) will use a **Provider Interface** pattern:
```python
# Conceptual Portability Layer
class CloudProvider:
    def get_stale_records(self): pass

class AWSProvider(CloudProvider): ...
class AzureProvider(CloudProvider): ...
class AliCloudProvider(CloudProvider): ...
```

---

## 5. Risk Mitigation & Rollout Plan

1.  **Dry-Run (Week 1):** Execute WAPI GET calls to find candidates without taking action. Output to a CSV for review.
2.  **Tag-First (Week 2):** Populate EAs for all 10,000+ records. No deletion logic active.
3.  **Scoped Pilot (Week 3):** Enable auto-scavenging for a single AWS Dev/Test VPC.
4.  **Global Toggle (Week 4):** Enable across all AWS Production zones with a 24-hour "Recycle Bin" retention policy.

---

## 6. Success Metrics (The Value)
- **Zombie Reduction:** Target > 25% record count reduction in AWS zones.
- **Sync Latency:** Target < 15 minutes between AWS Termination -> DNS Purge.
- **Efficiency:** Support ticket reduction for "Subdomain Takeover" false positives.
