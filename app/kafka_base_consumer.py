# File: app/kafka_base_consumer.py

from confluent_kafka import Consumer, Producer, KafkaException
import json
import logging
import threading
import sys

# Configure logging for the base consumer
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KafkaConsumerBase:
    """
    A base class for Kafka consumers, providing common setup and message polling logic.
    Subclasses must implement the `process_message` method.
    """
    def __init__(self, brokers: str, group_id: str, topic: str):
        self.brokers = brokers
        self.group_id = group_id
        self.topic = topic
        self.consumer = None
        self._running = False
        self._consumer_thread = None

        self._configure_consumer()

    def _configure_consumer(self):
        """
        Configures and initializes the Kafka consumer instance.
        """
        conf = {
            'bootstrap.servers': self.brokers,
            'group.id': self.group_id,
            'auto.offset.reset': 'earliest', # Start consuming from the beginning if no committed offset
            'enable.auto.commit': True,      # Automatically commit offsets
            'auto.commit.interval.ms': 5000, # Commit offsets every 5 seconds
            'on_commit': self._on_commit_callback # Optional: for debugging commit issues
        }
        try:
            self.consumer = Consumer(conf)
            self.consumer.subscribe([self.topic])
            logger.info(f"Consumer for group '{self.group_id}' subscribed to topic '{self.topic}'.")
        except KafkaException as e:
            logger.error(f"Failed to create or subscribe Kafka consumer for group '{self.group_id}': {e}")
            sys.exit(1) # Exit if consumer cannot be initialized

    def _on_commit_callback(self, err, partitions):
        """
        Callback function for consumer offset commits.
        """
        if err:
            logger.error(f"Failed to commit offsets for group '{self.group_id}': {err}")
        else:
            # This can be noisy, uncomment for detailed debugging of commits
            # logger.debug(f"Offsets committed for group '{self.group_id}' partitions: {partitions}")
            pass

    def _delivery_report(self, err, msg):
        """
        Callback for producer delivery reports. Used by subclasses that create producers.
        """
        if err is not None:
            logger.error(f"Message delivery failed to topic {msg.topic()} for key {msg.key().decode('utf-8') if msg.key() else 'N/A'}: {err}")
        # else:
            # This can be noisy, uncomment for detailed debugging of message delivery
            # logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()} (key: {msg.key().decode('utf-8') if msg.key() else 'N/A'})")

    def _create_producer(self):
        """
        Helper method for child classes to create a producer instance.
        """
        p_conf = {
            'bootstrap.servers': self.brokers,
            'acks': 'all',  # Ensure data is safely replicated
            'retries': 3,   # Number of retries on failed production
            'linger.ms': 0, # Send immediately (no batching by time)
            'batch.size': 1 # Send individual messages immediately (no batching by size)
        }
        try:
            # Pass the delivery_report method as the callback for this producer
            return Producer(p_conf, on_delivery=self._delivery_report)
        except KafkaException as e:
            logger.error(f"Failed to create Kafka producer for group '{self.group_id}': {e}")
            sys.exit(1) # Exit if producer cannot be initialized

    def process_message(self, key: str, payload: dict):
        """
        Abstract method to be implemented by subclasses.
        Processes a single Kafka message.
        """
        raise NotImplementedError("Subclasses must implement process_message method.")

    def run(self):
        """
        Starts the consumer polling loop. This method blocks.
        """
        if not self.consumer:
            logger.error(f"Consumer for group '{self.group_id}' not initialized. Cannot run.")
            return

        logger.info(f"Starting Kafka consumer for group '{self.group_id}' on topic '{self.topic}'...")
        self._running = True
        try:
            while self._running:
                # Poll for messages with a timeout
                msg = self.consumer.poll(timeout=1.0) 

                if msg is None:
                    # No message received within the timeout, continue polling
                    continue
                if msg.error():
                    # Handle Kafka errors
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        # End of partition reached. Not an error, just an informational signal.
                        logger.debug(f"Reached end of partition {msg.topic()} [{msg.partition()}] for group '{self.group_id}'")
                    else:
                        # Other consumer errors
                        logger.error(f"Consumer error for group '{self.group_id}': {msg.error()}")
                    continue

                # Decode message key and value
                key_decoded = msg.key().decode('utf-8') if msg.key() else None
                try:
                    payload_decoded = json.loads(msg.value().decode('utf-8'))
                    self.process_message(key_decoded, payload_decoded)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON payload for group '{self.group_id}': {e} - Raw: {msg.value().decode('utf-8')}")
                except Exception as e:
                    logger.error(f"Error processing message for key '{key_decoded}' in group '{self.group_id}': {e}", exc_info=True)

        except KeyboardInterrupt:
            logger.info(f"Consumer for group '{self.group_id}' stopped by user (KeyboardInterrupt).")
        except Exception as e:
            logger.critical(f"Critical error in consumer for group '{self.group_id}': {e}", exc_info=True)
        finally:
            self.stop() # Ensure consumer is properly closed on exit

    def start_in_thread(self):
        """
        Starts the consumer in a separate daemon thread.
        Daemon threads will automatically exit when the main program exits.
        """
        if self._consumer_thread is None or not self._consumer_thread.is_alive():
            self._consumer_thread = threading.Thread(target=self.run, daemon=True)
            self._consumer_thread.start()
            logger.info(f"Consumer for group '{self.group_id}' started in background thread.")
        else:
            logger.warning(f"Consumer for group '{self.group_id}' is already running or starting.")

    def stop(self):
        """
        Stops the consumer loop and closes the consumer.
        """
        if self._running:
            self._running = False
            logger.info(f"Stopping consumer for group '{self.group_id}'...")
            if self.consumer:
                self.consumer.close()
                logger.info(f"Consumer for group '{self.group_id}' closed.")
            if self._consumer_thread and threading.current_thread() != self._consumer_thread:
                # Only join if not trying to join self (to avoid deadlock)
                self._consumer_thread.join(timeout=5) # Wait for thread to finish
                if self._consumer_thread.is_alive():
                    logger.warning(f"Consumer thread for '{self.group_id}' did not terminate cleanly within timeout.")

