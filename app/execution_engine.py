from kafka_base_consumer import KafkaConsumerBase
import json
import csv
import logging
import os # For checking file existence

logger = logging.getLogger(__name__)

class ExecutionEngine(KafkaConsumerBase):
    def __init__(self, brokers: str):
        super().__init__(brokers, "execution_group", "trade_signal")
        self.profit_book_file = "profit_book.csv"
        self.profit_book_writer = None
        self._initialize_profit_book()

    def _initialize_profit_book(self):
        file_exists = os.path.exists(self.profit_book_file)
        self.profit_book_writer = open(self.profit_book_file, 'a', newline='')
        self.csv_writer = csv.writer(self.profit_book_writer)

        if not file_exists or os.stat(self.profit_book_file).st_size == 0:
            # Write header only if file didn't exist or was empty
            self.csv_writer.writerow(["symbol", "action", "filled_price", "qty", "notional"])
            logger.info(f"Profit book '{self.profit_book_file}' initialized with header.")
        else:
            logger.info(f"Appending to existing profit book '{self.profit_book_file}'.")

    def process_message(self, key: str, payload: dict):
        """
        Processes an incoming trade signal.
        Simulates a fill and logs it to the profit book.
        """
        symbol = key # Kafka key is the symbol

        action = payload.get("action")
        price = payload.get("price")
        
        # Hardcoded quantity, as per original C++ logic
        qty = 100 
        notional = price * qty

        fill_record = {
            "symbol": symbol,
            "action": action,
            "filled_price": price,
            "qty": qty,
            "notional": notional
        }
        
        logger.info(f"[EXECUTION] FILL: {fill_record}")

        # Write to profit book CSV
        try:
            self.csv_writer.writerow([symbol, action, price, qty, notional])
            self.profit_book_writer.flush() # Ensure data is written to disk immediately
        except Exception as e:
            logger.error(f"Error writing to profit book for {symbol}: {e}", exc_info=True)

    def stop(self):
        super().stop()
        if self.profit_book_writer:
            logger.info(f"Closing profit book file '{self.profit_book_file}'.")
            self.profit_book_writer.close()

if __name__ == "__main__":
    # Example usage if running this file directly (for testing)
    brokers = "localhost:9092"
    engine = ExecutionEngine(brokers)
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("ExecutionEngine stopping...")
    finally:
        engine.stop()