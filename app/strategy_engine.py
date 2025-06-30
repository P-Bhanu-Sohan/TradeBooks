# File: app/strategy_engine.py

from kafka_base_consumer import KafkaConsumerBase
from confluent_kafka import Producer
import json
import logging
from collections import defaultdict, deque # Import deque for efficient history storage
import statistics # For mean calculation (SMA)

logger = logging.getLogger(__name__)

class StrategyEngine(KafkaConsumerBase):
    """
    StrategyEngine consumes order book snapshots, applies a Simple Moving Average (SMA)
    crossover strategy, and publishes trade signals (BUY/SELL/BUY_TO_COVER/SELL_SHORT)
    to a Kafka topic.
    """
    def __init__(self, brokers: str):
        # Initialize the base consumer, subscribing to the order book snapshot topic
        super().__init__(brokers, "strategy_group", "order_book_snapshot")
        
        # Create a producer instance using the helper from the base class
        self.producer = self._create_producer() 
        
        # --- Strategy Parameters ---
        self.SHORT_SMA_PERIOD = 10 # Period for the short-term Moving Average (e.g., 10 minutes)
        self.LONG_SMA_PERIOD = 30  # Period for the long-term Moving Average (e.g., 30 minutes)
        
        # --- State Variables per Symbol ---
        # Stores price history for SMA calculation. Using 'ask' price for consistency.
        # deque with maxlen automatically discards oldest entries when new ones are added.
        self.price_history = defaultdict(lambda: deque(maxlen=self.LONG_SMA_PERIOD))
        
        # Tracks the current simulated position for each symbol: 'FLAT', 'LONG', 'SHORT'
        self.current_position = defaultdict(lambda: 'FLAT') 

        # Stores previous SMA values to detect crossovers (needed for proper signal generation)
        self.previous_short_sma = defaultdict(float)
        self.previous_long_sma = defaultdict(float)

    def process_message(self, key: str, payload: dict):
        """
        Processes an incoming order book snapshot message.
        Applies an SMA crossover strategy and emits trade signals.
        """
        symbol = key # The Kafka message key is the stock symbol

        # Safely get data from the payload
        bid = payload.get("bid")
        ask = payload.get("ask")
        spread = payload.get("spread")
        timestamp = payload.get("timestamp")

        # Validate essential data points
        if bid is None or ask is None or spread is None or timestamp is None:
            logger.warning(f"Received malformed snapshot data for {symbol}: Missing essential fields. Payload: {payload}")
            return

        # Add the current ask price to the history for this symbol
        # We use 'ask' for SMA calculation as we typically buy at ask and sell at bid.
        self.price_history[symbol].append(ask)

        # Ensure we have enough data points to calculate both SMAs
        if len(self.price_history[symbol]) < self.LONG_SMA_PERIOD:
            logger.debug(f"[{symbol}] Not enough data for SMA calculation ({len(self.price_history[symbol])}/{self.LONG_SMA_PERIOD})")
            return # Not enough data yet, wait for more snapshots

        # Calculate current SMAs using the collected price history
        # Convert deque to list for statistics.mean() and slice for short SMA
        current_short_sma = statistics.mean(list(self.price_history[symbol])[-self.SHORT_SMA_PERIOD:])
        current_long_sma = statistics.mean(list(self.price_history[symbol])) # deque.maxlen handles the long period

        logger.info(f"[STRATEGY] {symbol} @ {timestamp}: Ask={ask:.2f}, ShortSMA={current_short_sma:.2f}, LongSMA={current_long_sma:.2f}, Position={self.current_position[symbol]}")

        # --- SMA Crossover Strategy Logic ---
        # Only proceed if previous SMA values are initialized (i.e., not their default 0.0)
        # This prevents signals on the very first few data points before a proper trend can be established.
        if self.previous_short_sma[symbol] != 0.0 and self.previous_long_sma[symbol] != 0.0:
            # BUY Signal: Short SMA crosses above Long SMA
            # Condition: Current short SMA is above long SMA AND previous short SMA was at or below long SMA
            if current_short_sma > current_long_sma and self.previous_short_sma[symbol] <= self.previous_long_sma[symbol]:
                if self.current_position[symbol] == 'FLAT':
                    # Open a new LONG position
                    signal = {
                        "symbol": symbol,
                        "action": "BUY", # Standard BUY to open a long position
                        "price": ask # Buy at current ask price
                    }
                    self._send_trade_signal(symbol, signal)
                    self.current_position[symbol] = 'LONG'
                    logger.info(f"[STRATEGY] {symbol} - BUY Signal (SMA Crossover Up): {signal}")
                elif self.current_position[symbol] == 'SHORT':
                    # Close existing SHORT position (Buy to Cover)
                    signal = {
                        "symbol": symbol,
                        "action": "BUY_TO_COVER", # Action to close a short position
                        "price": ask # Buy at current ask price
                    }
                    self._send_trade_signal(symbol, signal)
                    self.current_position[symbol] = 'FLAT' # Position becomes flat after covering
                    logger.info(f"[STRATEGY] {symbol} - BUY_TO_COVER Signal (SMA Crossover Up): {signal}")

            # SELL Signal: Short SMA crosses below Long SMA
            # Condition: Current short SMA is below long SMA AND previous short SMA was at or above long SMA
            elif current_short_sma < current_long_sma and self.previous_short_sma[symbol] >= self.previous_long_sma[symbol]:
                if self.current_position[symbol] == 'LONG':
                    # Close existing LONG position (Sell to Close)
                    signal = {
                        "symbol": symbol,
                        "action": "SELL", # Standard SELL to close a long position
                        "price": bid # Sell at current bid price
                    }
                    self._send_trade_signal(symbol, signal)
                    self.current_position[symbol] = 'FLAT' # Position becomes flat after selling
                    logger.info(f"[STRATEGY] {symbol} - SELL Signal (SMA Crossover Down): {signal}")
                elif self.current_position[symbol] == 'FLAT':
                    # Open a new SHORT position
                    signal = {
                        "symbol": symbol,
                        "action": "SELL_SHORT", # Action to open a short position
                        "price": bid # Sell at current bid price
                    }
                    self._send_trade_signal(symbol, signal)
                    self.current_position[symbol] = 'SHORT'
                    logger.info(f"[STRATEGY] {symbol} - SELL_SHORT Signal (SMA Crossover Down): {signal}")

        # Update previous SMA values for the next iteration's crossover detection
        self.previous_short_sma[symbol] = current_short_sma
        self.previous_long_sma[symbol] = current_long_sma

    def _send_trade_signal(self, symbol: str, signal: dict):
        """
        Helper method to send a trade signal message to the 'trade_signal' Kafka topic.
        """
        signal_payload = json.dumps(signal).encode('utf-8')
        self.producer.produce("trade_signal", key=symbol.encode('utf-8'), value=signal_payload)
        self.producer.poll(0) # Poll the producer to ensure messages are sent

    def stop(self):
        """
        Overrides the base stop method to also flush the producer when the engine stops.
        """
        super().stop() # Call the base class's stop method first
        if self.producer:
            logger.info("Flushing producer for StrategyEngine...")
            self.producer.flush(timeout=5) # Ensure any buffered messages are sent
            logger.info("StrategyEngine producer flushed.")

# This block allows you to run the StrategyEngine directly for testing purposes.
# In the full system, it will be started by main_orchestrator.py.
if __name__ == "__main__":
    brokers = "localhost:9092"
    engine = StrategyEngine(brokers)
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("StrategyEngine stopping due to KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"StrategyEngine encountered a critical error: {e}", exc_info=True)
    finally:
        engine.stop()

