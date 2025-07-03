# producer.py
import csv
import time
import json
import os
import sys
from confluent_kafka import Producer

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.config import KAFKA_CONFIG, TOPICS, DATA_PATHS  # Fixed import

producer = Producer(KAFKA_CONFIG)

def delivery_report(err, msg):
    if err:
        print(f"Message delivery failed: {err}")

def stream_data():
    files = {stock: open(path, 'r') for stock, path in DATA_PATHS.items()}
    readers = {stock: csv.DictReader(f) for stock, f in files.items()}
    
    try:
        while any(reader for reader in readers.values()):
            for stock, reader in readers.items():
                try:
                    row = next(reader)
                except StopIteration:
                    continue
                
                # Create tick data
                tick = {
                    'datetime': row['datetime'],
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    '% change': row.get('% change', '0')
                }
                
                producer.produce(
                    TOPICS[stock],
                    json.dumps(tick).encode('utf-8'),
                    callback=delivery_report
                )
            
            producer.flush()
            time.sleep(60) 
    
    finally:
        for f in files.values():
            f.close()

if __name__ == '__main__':
    stream_data()