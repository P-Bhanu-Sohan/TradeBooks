from kafka_base_consumer import KafkaConsumerBase
from confluent_kafka import Producer
import json
import logging
from collections import defaultdict # For per-symbol best bid/ask

logger = logging.getLogger(__name__)

class OrderBookEngine(KafkaConsumerBase):
    def __init__(self, brokers: str):
        super().__init__(brokers, "order_book_group", "market_data_daily_delayed_bars")
        self.producer = self._create_producer() # Use helper to create producer
        
        # Track best bid/ask per symbol
        self.best_bid = defaultdict(float)  # Default to 0.0 for bid
        self.best_ask = defaultdict(lambda: 1e9) # Default to a very high number for ask

    def process_message(self, key: str, payload: dict):
        """
        Processes an incoming 1-minute bar message from market_data_daily_delayed_bars.
        Calculates and publishes an order book snapshot.
        """
        symbol = key # Kafka key is the symbol

        # Extract high and low from the 1-minute bar.
        # These are proxies for ask and bid within the bar's timeframe.
        current_low = payload.get("low")
        current_high = payload.get("high")
        timestamp = payload.get("timestamp")

        if current_low is None or current_high is None:
            logger.warning(f"Received malformed bar data for {symbol}: {payload}")
            return

        # Update best bid/ask for the specific symbol
        # Best bid is the highest 'low' price observed so far for this symbol
        self.best_bid[symbol] = max(self.best_bid[symbol], current_low)
        # Best ask is the lowest 'high' price observed so far for this symbol
        self.best_ask[symbol] = min(self.best_ask[symbol], current_high)

        # Create the order book snapshot
        snapshot = {
            "symbol": symbol,
            "bid": self.best_bid[symbol],
            "ask": self.best_ask[symbol],
            "spread": self.best_ask[symbol] - self.best_bid[symbol],
            "timestamp": timestamp # Pass original timestamp from the bar
        }
        
        snapshot_payload = json.dumps(snapshot).encode('utf-8')
        
        logger.info(f"[ORDERBOOK] Snapshot for {symbol}: Bid={snapshot['bid']:.2f}, Ask={snapshot['ask']:.2f}, Spread={snapshot['spread']:.2f}, Time={snapshot['timestamp']}")

        # Produce the snapshot to the 'order_book_snapshot' topic
        self.producer.produce("order_book_snapshot", key=symbol.encode('utf-8'), value=snapshot_payload)
        self.producer.poll(0) # Poll for delivery reports
    
    def stop(self):
        super().stop()
        if self.producer:
            logger.info("Flushing producer for OrderBookEngine...")
            self.producer.flush(timeout=5)
            logger.info("OrderBookEngine producer flushed.")

if __name__ == "__main__":
    # Example usage if running this file directly (for testing)
    # In a real setup, this will be run by a main orchestrator.
    brokers = "localhost:9092"
    engine = OrderBookEngine(brokers)
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("OrderBookEngine stopping...")
    finally:
        engine.stop()