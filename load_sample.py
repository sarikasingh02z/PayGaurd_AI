import csv
import requests
import time

CSV_FILE = "sample_complaint.csv"
API_URL = "http://127.0.0.1:5000/api/audit"

def load_samples():
    with open(CSV_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        success = 0
        failed = 0
        for row in reader:
            try:
                response = requests.post(API_URL, json={
                    "complaint": row['complaint'],
                    "payment_type": row['payment_type'],
                    "failure_date": row['failure_date']
                })
                if response.status_code == 200:
                    success += 1
                    print(f"✓ Loaded complaint {row['id']}")
                else:
                    failed += 1
                    print(f"✗ Failed complaint {row['id']}: {response.text}")
            except Exception as e:
                failed += 1
                print(f"✗ Error on complaint {row['id']}: {e}")
                time.sleep(2)
    
    print(f"\nDone. {success} loaded, {failed} failed.")

if __name__ == "__main__":
    load_samples()