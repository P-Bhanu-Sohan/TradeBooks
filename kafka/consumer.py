# consumer.py - Added debug logging
import json
import logging
import sys
import os
# consumer.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import backend.config as config
config.load_state()
# ... existing consumer code ...
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from confluent_kafka import Consumer
from backend.config import KAFKA_CONFIG, TOPICS
from backend.strategy import handle_tick

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

consumer = Consumer({**KAFKA_CONFIG, 'group.id': 'hft_sim'})
consumer.subscribe(list(TOPICS.values()))

try:
    while True:
        msg = consumer.poll(1.0)
        if msg and not msg.error():
            topic = msg.topic()
            stock = next(k for k,v in TOPICS.items() if v == topic)
            tick = msg.value().decode('utf-8')
            logging.info(f"Processing {stock} at {json.loads(tick)['datetime']}")
            handle_tick(stock, tick)
finally:
    consumer.close()