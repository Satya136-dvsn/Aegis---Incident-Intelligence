import time
import requests

API_URL = "http://localhost:8000/api/v1/metrics"

print("📡 Establishing baseline metrics for Anomaly Engine (needs 10 points minimum)...")

# 1. Send 10 normal metrics to build the rolling mean
for i in range(12):
    payload = [{
        "service_name": "payment-api",
        "metric_type": "cpu_usage",
        "value": 25.0 + (i * 0.5)  # Normal CPU around 25-30%
    }]
    requests.post(API_URL, json=payload)
    time.sleep(0.1)

print("🔥 Triggering Critical CPU Anomaly on Aegis API...")

# 2. Send the massive spike to trigger the Anomaly 2-sigma threshold
payload = [{
    "service_name": "payment-api",
    "metric_type": "cpu_usage",
    "value": 99.5
}]

response = requests.post(API_URL, json=payload)

if response.status_code == 201:
    print("✅ Metric successfully ingested.")
    print("🤖 The Aegis Celery Worker has detected an anomaly and is querying Gemini for RCA...")
    print("👀 Look at your dashboard at http://localhost:5173 ! An incident should appear in real-time.")
else:
    print(f"❌ Failed to ingest metric: {response.text}")
