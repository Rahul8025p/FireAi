"""
Download real NYC 311 Service Requests from calendar year 2023
directly from NYC Open Data (Socrata API).
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, "nyc_311_2023_real.json")

def download_nyc_311_2023(target_records=15000, batch_size=2000):
    print(f"Downloading {target_records} real NYC 311 service requests from 2023...")
    all_records = []
    offset = 0
    
    # We query across various months of 2023 to get a rich variety
    while len(all_records) < target_records:
        fetch_limit = min(batch_size, target_records - len(all_records))
        params = {
            "$where": "created_date between '2023-01-01T00:00:00' and '2023-12-31T23:59:59'",
            "$limit": str(fetch_limit),
            "$offset": str(offset),
            "$order": "created_date ASC"
        }
        url = "https://data.cityofnewyork.us/resource/erm2-nwe9.json?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "FireAI-DataQuality-Research/1.0"})
        
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                batch = json.loads(resp.read().decode("utf-8"))
                if not batch:
                    print("No more records returned from API.")
                    break
                all_records.extend(batch)
                offset += len(batch)
                print(f"  Fetched {len(batch)} records (total: {len(all_records)} / {target_records})...")
        except Exception as e:
            print(f"Error fetching batch at offset {offset}: {e}. Retrying after 2s...")
            time.sleep(2)
            try:
                with urllib.request.urlopen(req, timeout=40) as resp:
                    batch = json.loads(resp.read().decode("utf-8"))
                    all_records.extend(batch)
                    offset += len(batch)
            except Exception as e2:
                print(f"Failed retry: {e2}. Stopping with {len(all_records)} records.")
                break
                
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_records, f)
        
    print(f"Saved {len(all_records)} REAL 2023 NYC 311 records to {OUTPUT_FILE}")
    print(f"File size: {os.path.getsize(OUTPUT_FILE) / (1024*1024):.2f} MB")
    return OUTPUT_FILE

if __name__ == "__main__":
    records = 15000
    if len(sys.argv) > 1:
        records = int(sys.argv[1])
    download_nyc_311_2023(records)
