import threading
import time
import logging
import sys

# Import your custom engine classes
from order_book_engine import OrderBookEngine
from strategy_engine import StrategyEngine
from execution_engine import ExecutionEngine

# Configure logging for the orchestrator
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("Orchestrator")

KAFKA_BROKERS = "localhost:9092"

def main():
    logger.info("Starting the Kafka-based Trading System Orchestrator...")

    # Initialize all engines
    order_book_engine = OrderBookEngine(KAFKA_BROKERS)
    strategy_engine = StrategyEngine(KAFKA_BROKERS)
    execution_engine = ExecutionEngine(KAFKA_BROKERS)

    engines = [order_book_engine, strategy_engine, execution_engine]
    
    # Start each engine in a separate daemon thread
    # Daemon threads will automatically exit when the main program exits.
    for engine in engines:
        engine.start_in_thread()
    
    logger.info("All trading system components started. Press Ctrl+C to stop.")

    try:
        # Keep the main thread alive indefinitely while background threads run
        while True:
            time.sleep(1) 
    except KeyboardInterrupt:
        logger.info("Ctrl+C detected. Stopping all trading system components...")
    except Exception as e:
        logger.error(f"An unexpected error occurred in orchestrator: {e}", exc_info=True)
    finally:
        # Gracefully stop all engines
        for engine in engines:
            engine.stop()
        logger.info("All trading system components stopped.")
        logger.info("Orchestrator exiting.")

if __name__ == "__main__":
    main()