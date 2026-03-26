import time
import requests
import random
from datetime import datetime

API_URL = "http://localhost:8000/api/v1/metrics"

SERVICES = ["payment-api", "auth-service", "worker-node", "database-primary"]
METRICS = ["cpu_usage", "memory_usage", "response_time_ms", "error_rate"]

print("🟢 Vigilinex Live Telemetry Streamer Started")
print("Press Ctrl+C to stop.\n")

anomalies_triggered = 0
metrics_sent = 0

# Initial warmup - pump 15 solid normal metrics for all combinations
# so the standard deviation window has data immediately.
print("🔥 Warming up 2-sigma baseline models...")
for i in range(15):
    for service in SERVICES:
        for metric in METRICS:
            base_value = {
                "cpu_usage": random.uniform(20.0, 45.0),
                "memory_usage": random.uniform(40.0, 60.0),
                "response_time_ms": random.uniform(10.0, 50.0),
                "error_rate": random.uniform(0.0, 0.05)
            }[metric]
            requests.post(API_URL, json=[{
                "service_name": service,
                "metric_type": metric,
                "value": base_value
            }])
print("✅ Models trained. Beginning continuous stream...")

while True:
    for service in SERVICES:
        for metric in METRICS:
            base_value = {
                "cpu_usage": random.uniform(20.0, 45.0),
                "memory_usage": random.uniform(40.0, 60.0),
                "response_time_ms": random.uniform(10.0, 50.0),
                "error_rate": random.uniform(0.0, 0.05)
            }[metric]
            
            # 0.5% chance to inject an extreme anomaly per metric per loop
            is_anomaly = False
            if random.random() < 0.005:
                is_anomaly = True
                if metric == "cpu_usage": base_value = random.uniform(95.0, 99.9)
                elif metric == "memory_usage": base_value = random.uniform(90.0, 100.0)
                elif metric == "response_time_ms": base_value = random.uniform(2000.0, 5000.0)
                elif metric == "error_rate": base_value = random.uniform(0.5, 0.9)
                
            payload = [{
                "service_name": service,
                "metric_type": metric,
                "value": base_value
            }]
            
            try:
                requests.post(API_URL, json=payload, timeout=2)
                metrics_sent += 1
                if is_anomaly:
                    anomalies_triggered += 1
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 ANOMALY INJECTED: {service} -> {metric} = {base_value:.2f}")
            except Exception:
                pass
                
    if metrics_sent % 80 == 0:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌊 Streaming... Successfully routed {metrics_sent} metrics. Anomalies: {anomalies_triggered}")
        
    time.sleep(2.5) # Throttle to simulate realistic traffic velocity
