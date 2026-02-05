# Architecture & Development Plan: Async DDI Scavenging Engine

## 1. High-Level Architecture
The engine is designed as a **high-concurrency pipeline** that decouples "Discovery" from "Mutation." It follows the **O(N) Hash-Map Synchronization** pattern to ensure it can handle 100k+ records without linear performance degradation.

### 1.1 Technical Stack
- **Language:** Python 3.10+
- **WAPI Client:** `httpx` (Async/HTTP2 support)
- **Concurrency:** `asyncio` with `asyncio.Semaphore` for rate limiting.
- **Data Modeling:** `Pydantic v2` for strict WAPI object validation.
- **Cloud Interface:** `aiobotocore` (Async Boto3) for AWS Route 53.

### 1.2 Core Components
- **`AsyncWAPIClient`**: Manages persistent sessions, connection pooling, and WAPI-specific error handling.
- **`DiscoveryProviders`**:
    - **`CloudProvider`**: Uses `aiobotocore` to fetch AWS/Azure state.
    - **`OnPremProvider`**: Uses WAPI `lease` and `search` objects to fetch DHCP lease historical state and NetMRI discovery data.
- **`ReconciliationEngine`**: The "Hybrid Brain" that performs cross-source verification (e.g., Record exists in DNS but Lease is 'Free' for > 15 days).
- **`BatchExecutor`**: Groups mutations into chunks for parallel execution.

---

## 2. The O(N) Performance Plan
| Phase | Operation | Complexity | Efficiency Goal |
| :--- | :--- | :--- | :--- |
| **Stream** | Async Paging from WAPI | O(N) | 500 records/sec |
| **Index** | Hash Map Construction | O(N) | O(1) Lookups |
| **Diff** | Set Intersection / Dict Compare | O(N) | Near-instantaneous |
| **Pulse** | Parallel Batch Mutation | O(Δ) | Concurrent WAPI Writes |

---

## 3. Development Roadmap (Stories)

### [SCAV-01] Async WAPI Client Infrastructure
**Description:** Build the plumbing for asynchronous communication with Infoblox NIOS 9.7 WAPI 2.13.1.
**Acceptance Criteria:**
- Implements `httpx.AsyncClient` with custom retry logic for 429/503 errors.
- Includes a `Semaphore` to limit concurrent connections (preventing WAPI exhaustion).
- Implements **WAPI Paging** (supports `next_page_id`).
- Verified with a `GET /record:a` call fetching 5,000+ records in < 10 seconds.

### [SCAV-02] High-Performance AWS Route 53 Data Streamer
**Description:** Implement asynchronous retrieval of AWS DNS records to feed the reconciliation engine.
**Acceptance Criteria:**
- Uses `aiobotocore` for non-blocking AWS API calls.
- Supports cross-account Role assumption.
- Normalizes AWS records into a standard internal schema (EA support).
- Handles Route 53 "Pagination Tokens" automatically.

### [SCAV-03] O(N) Reconciliation & Scavenging Logic
**Description:** The "Brain" of the operation. Diff engine that identifies zombies.
**Acceptance Criteria:**
- Loads 50,000 Infoblox records into a Python `dict` in < 2 seconds.
- Performs a full diff against AWS state.
- Filters candidates based on `last_queried` > 14 days and `Cloud_Instance_Status` == "terminated".
- Outputs a "Scavenging Manifest" (JSON) for audit.

### [SCAV-04] Parallel Mutation & Audit Engine
**Description:** Executes the cleanup while maintaining Grid integrity.
**Acceptance Criteria:**
- Groups deletions into batches.
- Executes batches concurrently (limited by semaphore).
- Captures Audit EAs (`Scavenged_By`, `Scavenge_Date`) on every deleted record.
- Verifies records are moved to the NIOS Recycle Bin.

### [SCAV-05] On-Prem Behavioral Analysis Module (DHCP & Query)
**Description:** Expand the engine to handle on-prem resources by cross-referencing DHCP leases and Query Monitor data.
**Acceptance Criteria:**
- Implements logic to fetch and map `lease` status for A/PTR records.
- Flags records where `lease_state` == "FREE" for > 30 days.
- Integrates `last_queried` attribute into the candidate filtering logic.
- Verified against on-prem zone exports (50k+ records).

---

## 4. Engineering Standards
1. **Type Safety:** Use Type Hints and Pydantic for all WAPI responses.
2. **Resource Hygiene:** Always use `async with` contexts for clients.
3. **Logging:** Standardized JSON logging for ingestion by Splunk/ELK.
4. **Observability:** Track `RequestsPerSecond` and `FailuresPerBatch` as key metrics.
