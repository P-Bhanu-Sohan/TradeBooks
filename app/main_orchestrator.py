# File: app/main_orchestrator.py

import threading
import time
import logging
import sys

# Import your custom engine classes from the 'app' directory
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

    # Initialize all engine instances
    # Each engine will subscribe to its respective input topic and potentially publish to another.
    order_book_engine = OrderBookEngine(KAFKA_BROKERS)
    strategy_engine = StrategyEngine(KAFKA_BROKERS)
    execution_engine = ExecutionEngine(KAFKA_BROKERS)

    # Collect all engine instances into a list for easy iteration
    engines = [order_book_engine, strategy_engine, execution_engine]
    
    # Start each engine in a separate daemon thread.
    # Daemon threads run in the background and will automatically terminate
    # when the main program exits, which is suitable for long-running services.
    for engine in engines:
        try:
            engine.start_in_thread()
        except Exception as e:
            logger.error(f"Failed to start engine {engine.__class__.__name__}: {e}", exc_info=True)
            # If an engine fails to start, you might want to stop others or exit.
            # For now, we'll log and continue.

    logger.info("All trading system components started. Press Ctrl+C to stop.")

    try:
        # Keep the main thread alive indefinitely while the background daemon threads run.
        # This loop will continue until a KeyboardInterrupt (Ctrl+C) or another unhandled exception occurs.
        while True:
            time.sleep(1) # Sleep briefly to prevent busy-waiting
    except KeyboardInterrupt:
        logger.info("Ctrl+C detected. Initiating graceful shutdown of all trading system components...")
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred in the main orchestrator loop: {e}", exc_info=True)
    finally:
        # Ensure all engines are gracefully stopped in reverse order of their dependencies if possible
        # (e.g., execution engine first, then strategy, then order book, though Kafka decouples this somewhat)
        for engine in reversed(engines): # Stop in reverse order
            engine.stop()
        logger.info("All trading system components stopped successfully.")
        logger.info("Orchestrator exiting.")

if __name__ == "__main__":
    main()

