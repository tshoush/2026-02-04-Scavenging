# Hybrid-Cloud DNS Scavenging Strategy (Infoblox)

## 1. Executive Summary
This document outlines the strategic implementation of DNS scavenging across a hybrid landscape consisting of a core Infoblox Grid and public cloud zones (AWS Route 53, Azure DNS, and Alibaba Cloud). The goal is to move from manual record management to an automated, behavioral-based lifecycle.

---

## 2. Use Cases & Problem Statement
- **Cloud Drift:** Temporary instances (EC2/VMs) created via CI/CD often leave "ghost" records if de-provisioning scripts fail.
- **Dynamic Churn:** DDNS updates from nomadic clients (VPN/Office) clutter zones with stale entries.
- **Security Visibility:** Stale A/CNAME records pose a "Subdomain Takeover" risk.
- **IPAM Accuracy:** Stale PTR records lead to "IP conflicts" in DHCP/IPAM management.

---

## 3. Implementation Approaches

### Approach A: Infoblox Cloud Network Automation (CNA)
*Recommended for AWS & Azure.*
- **Mechanism:** Leverages vDiscovery to poll cloud APIs and synchronize lifecycle events.
- **Pros:** Native integration; leverages Infoblox's "Reclaimable" logic; centralized audit.
- **Cons:** Requires CNA licenses; potential API rate-limiting on very large cloud accounts.

### Approach B: Tag-Based (EA) Scavenging
*Universal approach, best for AliCloud & Custom Integrations.*
- **Mechanism:** Automation (Terraform/Ansible) tags every record with an Extensible Attribute (EA) like `Lifecycle_Policy`. Infoblox runs scavenging rules based on these tags.
- **Pros:** Highly granular; safe (isolation of cloud records from core on-prem records).
- **Cons:** Requires strict adherence to tagging standards in all automation pipelines.

---

## 4. Implementation Plan (Phase-Based)

### Phase 1: Discovery & Assessment (Weeks 1-2)
- Enable "Last Queried Time" monitoring on target zones.
- Run vDiscovery to inventory AWS/Azure/AliCloud zones.
- Identify "Critical" records to be marked with "Protect from Scavenging".

### Phase 2: Policy & Environment Setup (Weeks 3-4)
- Define Scavenging Rules:
    - **Dynamic:** 14 days (No-Refresh) + 7 days (Refresh).
    - **Static:** 30 days of "No Queries" -> Mark Reclaimable.
- Configure permissions: Create IAM roles/Service Principals for Infoblox to access Cloud APIs.

### Phase 3: Pilot & Logging (Weeks 5-6)
- Enable scavenging in "Logging Mode" only.
- Review "Reclaimable" candidate report.
- Fine-tune rules to avoid false positives.

### Phase 4: Full Automation (Week 7+)
- Enable automated deletion to Recycle Bin.
- Establish monthly audit review of "Restored" records from Recycle Bin.

---

## 5. Needs & Requirements
- **NIOS Version:** 8.5+ (Required for AliCloud CNA support).
- **Licensing:** Cloud Network Automation (CNA) or Ecosystem Licensing.
- **Network:** Port 443 (HTTPS) access from Grid Master to Cloud API endpoints.
- **Permissions:** 
    - AWS: `Route53:ReadOnly`, `EC2:Describe`.
    - Azure: `Reader` role on DNS Zone resource.
    - AliCloud: `AliyunDNSFullAccess`.

---

## 6. Pro/Con Matrix

| Feature | NIOS Native | Cloud vDiscovery | Manual Scripting |
| :--- | :--- | :--- | :--- |
| **Audit Trail** | IntegratedNI OS Syslog | Centralized Reports | Fragmented Logs |
| **Safety** | High (Recycle Bin) | High (Sync State) | Low (Direct Delete) |
| **Effort** | Low (Set & Forget) | Medium (API Config) | High (Maintenance) |
| **DDNS Interaction** | Native Sync | Cloud-to-Grid Hub | None (Blind) |
