# File: app/order_book_engine.py

from kafka_base_consumer import KafkaConsumerBase
from confluent_kafka import Producer
import json
import logging
from collections import defaultdict # For per-symbol best bid/ask

logger = logging.getLogger(__name__)

class OrderBookEngine(KafkaConsumerBase):
    """
    OrderBookEngine consumes 1-minute bar data, calculates a simple
    best bid/ask (using high/low as proxies), and publishes snapshots
    to a Kafka topic.
    """
    def __init__(self, brokers: str):
        # Initialize the base consumer, subscribing to the market data topic
        super().__init__(brokers, "order_book_group", "market_data_daily_delayed_bars")
        
        # Create a producer instance using the helper from the base class
        self.producer = self._create_producer() 
        
        # Use defaultdict to store best bid and best ask for each symbol
        # best_bid defaults to 0.0 (lowest possible bid)
        self.best_bid = defaultdict(float)  
        # best_ask defaults to a very high number (highest possible ask)
        self.best_ask = defaultdict(lambda: 1e9) 

    def process_message(self, key: str, payload: dict):
        """
        Processes an incoming 1-minute bar message.
        Extracts high/low, updates per-symbol best bid/ask, and publishes a snapshot.
        """
        symbol = key # The Kafka message key is the stock symbol

        # Safely get data from the payload, with default None if key is missing
        current_low = payload.get("low")
        current_high = payload.get("high")
        timestamp = payload.get("timestamp")

        # Validate essential data points
        if current_low is None or current_high is None or timestamp is None:
            logger.warning(f"Received malformed bar data for {symbol}: Missing 'low', 'high', or 'timestamp'. Payload: {payload}")
            return

        # Update best bid for the specific symbol:
        # The best bid within the context of a bar is the highest 'low' price observed.
        self.best_bid[symbol] = max(self.best_bid[symbol], current_low)
        
        # Update best ask for the specific symbol:
        # The best ask within the context of a bar is the lowest 'high' price observed.
        self.best_ask[symbol] = min(self.best_ask[symbol], current_high)

        # Create the order book snapshot message
        snapshot = {
            "symbol": symbol,
            "bid": self.best_bid[symbol],
            "ask": self.best_ask[symbol],
            "spread": self.best_ask[symbol] - self.best_bid[symbol],
            "timestamp": timestamp # Pass the original timestamp from the bar
        }
        
        # Convert the snapshot dictionary to a JSON string and then to bytes
        snapshot_payload = json.dumps(snapshot).encode('utf-8')
        
        # Log the generated snapshot for monitoring
        logger.info(f"[ORDERBOOK] Snapshot for {symbol}: Bid={snapshot['bid']:.2f}, Ask={snapshot['ask']:.2f}, Spread={snapshot['spread']:.2f}, Time={snapshot['timestamp']}")

        # Produce the snapshot to the 'order_book_snapshot' topic
        # The key for the message is the symbol, ensuring messages for the same symbol
        # go to the same partition (if partitioning by key is enabled on Kafka).
        self.producer.produce("order_book_snapshot", key=symbol.encode('utf-8'), value=snapshot_payload)
        
        # Poll the producer to allow delivery reports to be processed and internal queues to be managed.
        # A timeout of 0ms means it won't block.
        self.producer.poll(0) 
    
    def stop(self):
        """
        Overrides the base stop method to also flush the producer.
        """
        super().stop() # Call the base class's stop method first
        if self.producer:
            logger.info("Flushing producer for OrderBookEngine...")
            # Flush any remaining messages in the producer's buffer with a timeout
            self.producer.flush(timeout=5)
            logger.info("OrderBookEngine producer flushed.")

# This block allows you to run the OrderBookEngine directly for testing purposes.
# In the full system, it will be started by main_orchestrator.py.
if __name__ == "__main__":
    brokers = "localhost:9092"
    engine = OrderBookEngine(brokers)
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("OrderBookEngine stopping due to KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"OrderBookEngine encountered a critical error: {e}", exc_info=True)
    finally:
        engine.stop()

