from kafka_base_consumer import KafkaConsumerBase
from confluent_kafka import Producer
import json
import logging
from collections import defaultdict # For per-symbol latest bid/ask

logger = logging.getLogger(__name__)

class StrategyEngine(KafkaConsumerBase):
    def __init__(self, brokers: str):
        super().__init__(brokers, "strategy_group", "order_book_snapshot")
        self.producer = self._create_producer() # Use helper to create producer
        
        self.latest_bid = defaultdict(float)
        self.latest_ask = defaultdict(float)

    def process_message(self, key: str, payload: dict):
        """
        Processes an incoming order book snapshot.
        Applies a simple strategy and publishes trade signals.
        """
        symbol = key # Kafka key is the symbol

        bid = payload.get("bid")
        ask = payload.get("ask")
        spread = payload.get("spread")
        timestamp = payload.get("timestamp")

        if bid is None or ask is None or spread is None:
            logger.warning(f"Received malformed snapshot data for {symbol}: {payload}")
            return

        self.latest_bid[symbol] = bid
        self.latest_ask[symbol] = ask

        logger.info(f"[STRATEGY] Snapshot for {symbol}: Bid={bid:.2f}, Ask={ask:.2f}, Spread={spread:.2f}, Time={timestamp}")

        # Simple strategy logic (same as your C++ version):
        # Buy if spread is tight (e.g., < 0.05) and ask price is below a threshold (e.g., 150.0)
        if spread < 0.05 and ask < 150.0:
            signal = {
                "symbol": symbol,
                "action": "BUY",
                "price": ask # Signal to buy at the current ask price
            }
            signal_payload = json.dumps(signal).encode('utf-8')
            
            logger.info(f"[STRATEGY] Emitting BUY signal for {symbol}: {signal}")

            # Produce the trade signal to the 'trade_signal' topic
            self.producer.produce("trade_signal", key=symbol.encode('utf-8'), value=signal_payload)
            self.producer.poll(0) # Poll for delivery reports
    
    def stop(self):
        super().stop()
        if self.producer:
            logger.info("Flushing producer for StrategyEngine...")
            self.producer.flush(timeout=5)
            logger.info("StrategyEngine producer flushed.")

if __name__ == "__main__":
    # Example usage if running this file directly (for testing)
    brokers = "localhost:9092"
    engine = StrategyEngine(brokers)
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("StrategyEngine stopping...")
    finally:
        engine.stop()