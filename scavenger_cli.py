import asyncio
import httpx
import getpass
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

class InfobloxScavenger:
    def __init__(self, grid_ip: str, user: str, password: str, wapi_version: str = "2.13.1"):
        self.base_url = f"https://{grid_ip}/wapi/v{wapi_version}"
        self.auth = (user, password)
        # Use a high-performance HTTP/2 client with connection pooling
        self.client = httpx.AsyncClient(
            auth=self.auth,
            verify=False,  # Set to True if using valid SSL certs
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50)
        )
        self.semaphore = asyncio.Semaphore(10)  # Rate limiting

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def fetch_records(self, record_type: str = "record:a") -> List[Dict[str, Any]]:
        """Fetch records using WAPI paging for large datasets."""
        records = []
        # Request essential fields including last_queried and extensible attributes
        params = {
            "_return_fields": "name,ipv4addr,last_queried,extattrs",
            "_paging": "1",
            "_max_results": "1000"
        }
        
        url = f"{self.base_url}/{record_type}"
        print(f"[*] Fetching {record_type} records...")

        while url:
            async with self.semaphore:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                records.extend(data.get("result", []))
                
                # Handle Paging
                next_page_id = data.get("next_page_id")
                if next_page_id:
                    params["_page_id"] = next_page_id
                else:
                    break
        
        print(f"[+] Total records retrieved: {len(records)}")
        return records

    def is_candidate(self, record: Dict[str, Any], cloud_days: int, onprem_days: int) -> bool:
        """Logic to determine if a record is a scavenging candidate based on its source."""
        # Determine if this is a cloud record based on the 'Cloud_Provider' Extensible Attribute
        extattrs = record.get("extattrs", {})
        cloud_provider = extattrs.get("Cloud_Provider", {}).get("value")
        
        # Select the appropriate threshold
        threshold_days = cloud_days if cloud_provider else onprem_days
        
        last_queried = record.get("last_queried")
        if not last_queried:
            # If no query recorded, we consider it a candidate (Infoblox v9.7 query monitor behavior)
            return True
        
        last_dt = datetime.fromtimestamp(last_queried)
        threshold_dt = datetime.now() - timedelta(days=threshold_days)
        
        return last_dt < threshold_dt

    async def run(self, cloud_days: int, onprem_days: int, dry_run: bool = True):
        """Main execution loop with hybrid threshold logic."""
        print(f"\n[!] Starting analysis...")
        print(f"    - Cloud Threshold: {cloud_days} days")
        print(f"    - On-Prem Threshold: {onprem_days} days")
        
        # Step 1: Ingest
        records = await self.fetch_records("record:a")
        
        # Step 2: Analyze
        candidates = [r for r in records if self.is_candidate(r, cloud_days, onprem_days)]
        
        # Statistical breakdown
        cloud_count = sum(1 for r in candidates if r.get("extattrs", {}).get("Cloud_Provider"))
        onprem_count = len(candidates) - cloud_count

        print(f"\n[+] Analysis Results:")
        print(f"    - Cloud Candidates Identified: {cloud_count}")
        print(f"    - On-Prem Candidates Identified: {onprem_count}")
        print(f"    - Total Records Safe: {len(records) - len(candidates)}")

        if dry_run and candidates:
            # Generate JSON for technical audit
            json_filename = f"scavenging_manifest_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            with open(json_filename, "w") as f:
                json.dump(candidates, f, indent=4)
            
            # Generate CSV for business/human review
            csv_filename = f"affected_records_review_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            import csv
            
            # Identify all unique EA keys across all candidates to build consistent headers
            all_ea_keys = set()
            for r in candidates:
                all_ea_keys.update(r.get("extattrs", {}).keys())
            sorted_ea_keys = sorted(list(all_ea_keys))

            with open(csv_filename, "w", newline="") as f:
                writer = csv.writer(f)
                header = ["FQDN", "IP Address", "Source", "Last Queried", "Days Since Last Query"] + [f"EA:{k}" for k in sorted_ea_keys]
                writer.writerow(header)
                
                for r in candidates:
                    lq = r.get("last_queried")
                    lq_str = datetime.fromtimestamp(lq).strftime('%Y-%m-%d') if lq else "Never"
                    days_since = (datetime.now() - datetime.fromtimestamp(lq)).days if lq else "N/A"
                    cp = r.get("extattrs", {}).get("Cloud_Provider", {}).get("value", "On-Prem")
                    
                    # Prepare the row with base data
                    row = [
                        r.get("name"), 
                        r.get("ipv4addr"), 
                        cp,
                        lq_str,
                        days_since
                    ]
                    
                    # Add EA values dynamically
                    eas = r.get("extattrs", {})
                    for key in sorted_ea_keys:
                        val = eas.get(key, {}).get("value", "")
                        row.append(val)
                        
                    writer.writerow(row)

            print(f"\n[!] Dry Run Complete.")
            print(f"    - Technical Manifest (JSON): {json_filename}")
            print(f"    - Review File for Business (CSV): {csv_filename}")
            
            # Export Live Summary for Presentation
            summary_data = {
                "total_records": len(records),
                "total_candidates": len(candidates),
                "cloud_candidates": cloud_count,
                "onprem_candidates": onprem_count,
                "health_percentage": round(((len(records) - len(candidates)) / len(records)) * 100, 1) if records else 100,
                "last_run": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            with open("live_scavenging_summary.json", "w") as f:
                json.dump(summary_data, f, indent=4)
            print(f"    - Live Presentation Data: live_scavenging_summary.json")

async def main():
    print("=== Infoblox Hybrid Scavenger CLI (v9.7) ===")
    grid_ip = input("Grid Master IP/FQDN: ")
    username = input("Admin Username: ")
    password = getpass.getpass("Admin Password: ")
    
    print("\n--- Scavenging Configuration (in Days) ---")
    try:
        cloud_t = int(input("AWS/Cloud Records Threshold (e.g. 7): "))
        onprem_t = int(input("On-Prem/Static Records Threshold (e.g. 90): "))
    except ValueError:
        print("Invalid input. Defaulting to Cloud: 14, On-Prem: 30.")
        cloud_t, onprem_t = 14, 30

    async with InfobloxScavenger(grid_ip, username, password) as scavenger:
        await scavenger.run(cloud_days=cloud_t, onprem_days=onprem_t, dry_run=True)

if __name__ == "__main__":
    # Suppress insecure request warnings for self-signed certs
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Operation cancelled by user.")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")

