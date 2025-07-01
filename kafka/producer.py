import csv
import time
import json
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from confluent_kafka import Producer
from backend.config import KAFKA_CONFIG, TOPICS, DATA_PATHS

producer = Producer(KAFKA_CONFIG)

def delivery_report(err, msg):
    if err:
        print(f"Delivery failed: {err}")

if __name__ == '__main__':
    # Open CSV files
    files = {}
    for stock, path in DATA_PATHS.items():
        files[stock] = open(path)
    readers = {s: csv.DictReader(f) for s, f in files.items()}
    try:
        while True:
            for stock, reader in readers.items():
                try:
                    row = next(reader)
                except StopIteration:
                    continue
                tick = {
                    'datetime': row['datetime'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'pct_change': float(row.get('% change', 0))
                }
                producer.produce(TOPICS[stock], json.dumps(tick), callback=delivery_report)
            producer.flush()
            time.sleep(60)
    finally:
        for f in files.values():
            f.close()