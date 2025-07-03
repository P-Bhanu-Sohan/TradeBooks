import json
import logging
import os
import sys
import time
from collections import deque
from confluent_kafka import Consumer

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend import config  # Import the entire config module
from backend.strategy import handle_tick

# Initialize state
config.init_state()  # This loads the state automatically

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize strategy components
from backend.strategy import price_windows, bar_windows
for stock in config.POSITIONS:
    price_windows[stock] = deque(maxlen=config.VOLUME_WINDOW)
    bar_windows[stock] = deque(maxlen=config.VOLUME_WINDOW)

# Create Kafka consumer
consumer = Consumer({
    **config.KAFKA_CONFIG,
    'group.id': 'lss_strategy',
    'auto.offset.reset': 'earliest'
})
consumer.subscribe(list(config.TOPICS.values()))

logger.info("Starting strategy consumer...")
logger.info(f"Initial cash: ${config.CASH:,.2f}")
logger.info(f"Initial positions: {config.POSITIONS}")
logger.info(f"Initial equity: ${config.get_equity():,.2f}")

try:
    while True:
        msg = consumer.poll(600000)  # Process messages quickly
        if msg is None:
            continue
        if msg.error():
            logger.error(f"Consumer error: {msg.error()}")
            continue
        
        topic = msg.topic()
        stock = next(k for k, v in config.TOPICS.items() if v == topic)
        try:
            tick = msg.value().decode('utf-8')
            logger.info(f"Received {stock} data")
            handle_tick(stock, tick)
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
        time.sleep(0.1)  # Small delay to prevent CPU overload
finally:
    consumer.close()
    logger.info("Consumer closed. Final portfolio state:")
    logger.info(f"Cash: ${config.CASH:,.2f}")
    logger.info(f"Holdings value: ${config.HOLDINGS_VALUE:,.2f}")
    logger.info(f"Total equity: ${config.get_equity():,.2f}")
    config.save_state()