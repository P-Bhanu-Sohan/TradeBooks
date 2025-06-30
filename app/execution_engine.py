# File: app/execution_engine.py

from kafka_base_consumer import KafkaConsumerBase
import json
import csv
import logging
import os # Import the os module for path manipulation
import sys # Import sys for exiting on critical errors

logger = logging.getLogger(__name__)

class ExecutionEngine(KafkaConsumerBase):
    """
    ExecutionEngine consumes trade signals, simulates a fill, and logs
    the filled trade details to a CSV file (profit_book.csv).
    """
    def __init__(self, brokers: str):
        # Initialize the base consumer, subscribing to the trade signal topic
        super().__init__(brokers, "execution_group", "trade_signal")
        
        # Construct the absolute path to profit_book.csv
        # This assumes profit_book.csv is in the parent directory of 'app'
        script_dir = os.path.dirname(__file__)
        self.profit_book_file = os.path.join(script_dir, "..", "profit_book.csv") # FIX: Corrected path
        
        self.profit_book_writer = None
        self.csv_writer = None
        self._initialize_profit_book()

    def _initialize_profit_book(self):
        """
        Initializes the profit book CSV file, creating it with a header if it doesn't exist.
        """
        file_exists = os.path.exists(self.profit_book_file)
        try:
            # Open the file in append mode ('a'), with newline='' to prevent extra blank rows
            self.profit_book_writer = open(self.profit_book_file, 'a', newline='', encoding='utf-8')
            self.csv_writer = csv.writer(self.profit_book_writer)

            # Check if the file is empty (or new) to write the header
            if not file_exists or os.stat(self.profit_book_file).st_size == 0:
                self.csv_writer.writerow(["symbol", "action", "filled_price", "qty", "notional"])
                logger.info(f"Profit book '{self.profit_book_file}' initialized with header.")
            else:
                logger.info(f"Appending to existing profit book '{self.profit_book_file}'.")
        except Exception as e:
            logger.critical(f"Error initializing profit book '{self.profit_book_file}': {e}", exc_info=True)
            # If we can't open the profit book, the engine cannot function correctly.
            # It's better to exit cleanly here.
            sys.exit(1) 

    def process_message(self, key: str, payload: dict):
        """
        Processes an incoming trade signal message.
        Simulates a trade fill and writes the details to the profit book CSV.
        """
        symbol = key # The Kafka message key is the stock symbol

        # Safely get data from the payload
        action = payload.get("action")
        price = payload.get("price")
        
        # Validate essential data points
        if action is None or price is None:
            logger.warning(f"Received malformed trade signal for {symbol}: Missing 'action' or 'price'. Payload: {payload}")
            return

        # Hardcoded quantity, as per your original C++ logic
        qty = 100 
        notional = price * qty # Calculate notional value

        fill_record = {
            "symbol": symbol,
            "action": action,
            "filled_price": price,
            "qty": qty,
            "notional": notional
        }
        
        logger.info(f"[EXECUTION] FILL: {fill_record}")

        # Write the simulated fill record to the profit book CSV
        try:
            self.csv_writer.writerow([symbol, action, price, qty, notional])
            self.profit_book_writer.flush() # Ensure data is written to disk immediately
        except Exception as e:
            logger.error(f"Error writing to profit book for {symbol}: {e}", exc_info=True)

    def stop(self):
        """
        Overrides the base stop method to also close the profit book file.
        """
        super().stop() # Call the base class's stop method first
        if self.profit_book_writer:
            logger.info(f"Closing profit book file '{self.profit_book_file}'.")
            self.profit_book_writer.close()

# This block allows you to run the ExecutionEngine directly for testing purposes.
# In the full system, it will be started by main_orchestrator.py.
if __name__ == "__main__":
    brokers = "localhost:9092"
    engine = ExecutionEngine(brokers)
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("ExecutionEngine stopping due to KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"ExecutionEngine encountered a critical error: {e}", exc_info=True)
    finally:
        engine.stop()

