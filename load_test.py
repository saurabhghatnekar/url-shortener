import subprocess
import json
import matplotlib.pyplot as plt
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define concurrency levels
concurrency_levels = [50, 100, 200, 500, 1000]
# 5000, 10000, 20000, 50000, 100000] 

# Store results
results = {}
server_url = 'https://url-shortener-py-xvre5sskvq-de.a.run.app'
# Run tests for each concurrency level
for concurrency in concurrency_levels:
    logging.info(f"Running test with concurrency: {concurrency}")
    # Run oha command
    command = [
        "oha",
        "-n", str(concurrency),
        "-c", str(concurrency),
        "-m", "POST",
        "-H", "Content-Type: application/json",
        "-d", '{"url": "https://example.com"}',
        f"{server_url}/shorten"
    ]
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        output = process.stdout

        # Extract metrics
        lines = output.splitlines()
        p50 = p90 = p95 = p99 = None
        for line in lines:
            if "50.00% in" in line:
                p50 = float(line.split()[2])
            elif "90.00% in" in line:
                p90 = float(line.split()[2])
            elif "95.00% in" in line:
                p95 = float(line.split()[2])
            elif "99.00% in" in line:
                p99 = float(line.split()[2])

        # Log results
        if None in (p50, p90, p95, p99):
            logging.warning(f"Incomplete data for concurrency {concurrency}")
        else:
            logging.info(f"Concurrency: {concurrency}, p50: {p50}s, p90: {p90}s, p95: {p95}s, p99: {p99}s")

        # Store results
        results[concurrency] = {
            "p50": p50,
            "p90": p90,
            "p95": p95,
            "p99": p99
        }
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running oha command for concurrency {concurrency}: {e}")

# Plot results
concurrency = list(results.keys())
p50 = [results[c]["p50"] for c in concurrency]
p90 = [results[c]["p90"] for c in concurrency]
p95 = [results[c]["p95"] for c in concurrency]
p99 = [results[c]["p99"] for c in concurrency]

plt.figure(figsize=(10, 6))
plt.plot(concurrency, p50, label='p50')
plt.plot(concurrency, p90, label='p90')
plt.plot(concurrency, p95, label='p95')
plt.plot(concurrency, p99, label='p99')
plt.xlabel('Concurrency Level')
plt.ylabel('Response Time (seconds)')
plt.title('Latency Graph (with neon postgres) -' + server_url)
plt.legend()
plt.grid(True)
plt.show()
