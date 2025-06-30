from confluent_kafka import Consumer, Producer, KafkaException
import json
import logging
import threading
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KafkaConsumerBase:
    def __init__(self, brokers: str, group_id: str, topic: str):
        self.brokers = brokers
        self.group_id = group_id
        self.topic = topic
        self.consumer = None
        self._running = False
        self._consumer_thread = None

        self._configure_consumer()

    def _configure_consumer(self):
        conf = {
            'bootstrap.servers': self.brokers,
            'group.id': self.group_id,
            'auto.offset.reset': 'earliest', # Start consuming from the beginning if no committed offset
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 5000, # Commit offsets every 5 seconds
            'on_commit': self._on_commit_callback # Optional: for debugging commit issues
        }
        self.consumer = Consumer(conf)
        self.consumer.subscribe([self.topic])
        logger.info(f"Consumer for group '{self.group_id}' subscribed to topic '{self.topic}'.")

    def _on_commit_callback(self, err, partitions):
        if err:
            logger.error(f"Failed to commit offsets: {err}")
        else:
            # logger.debug(f"Offsets committed for partitions: {partitions}") # Can be noisy
            pass

    def _delivery_report(self, err, msg):
        """
        Callback for producer delivery reports.
        """
        if err is not None:
            logger.error(f"Message delivery failed to topic {msg.topic()} for key {msg.key()}: {err}")
        # else:
            # logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()} (key: {msg.key()})")

    def _create_producer(self):
        """
        Helper method to create a producer instance for child classes that need one.
        """
        p_conf = {
            'bootstrap.servers': self.brokers,
            'acks': 'all',  # Ensure data is safely replicated
            'retries': 3,
            'linger.ms': 0, # Send immediately
            'batch.size': 1 # No batching
        }
        return Producer(p_conf, delivery_callback=self._delivery_report)

    def process_message(self, key: str, payload: dict):
        """
        Abstract method to be implemented by subclasses.
        Processes a single Kafka message.
        """
        raise NotImplementedError("Subclasses must implement process_message method.")

    def run(self):
        """
        Starts the consumer loop.
        """
        logger.info(f"Starting Kafka consumer for group '{self.group_id}' on topic '{self.topic}'...")
        self._running = True
        try:
            while self._running:
                msg = self.consumer.poll(timeout=1.0) # Poll for 1 second

                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaException._PARTITION_EOF:
                        logger.debug(f"Reached end of partition {msg.topic()} [{msg.partition()}]")
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    continue

                key = msg.key().decode('utf-8') if msg.key() else None
                try:
                    payload = json.loads(msg.value().decode('utf-8'))
                    self.process_message(key, payload)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON payload: {e} - Raw: {msg.value().decode('utf-8')}")
                except Exception as e:
                    logger.error(f"Error processing message for key '{key}': {e}", exc_info=True)

        except KeyboardInterrupt:
            logger.info(f"Consumer for group '{self.group_id}' stopped by user.")
        finally:
            self.stop() # Ensure consumer is properly closed

    def start_in_thread(self):
        """
        Starts the consumer in a separate thread.
        """
        if self._consumer_thread is None or not self._consumer_thread.is_alive():
            self._consumer_thread = threading.Thread(target=self.run, daemon=True) # Daemon so it exits with main program
            self._consumer_thread.start()
            logger.info(f"Consumer for group '{self.group_id}' started in background thread.")
        else:
            logger.warning(f"Consumer for group '{self.group_id}' is already running.")

    def stop(self):
        """
        Stops the consumer loop and closes the consumer.
        """
        if self._running:
            self._running = False
            logger.info(f"Stopping consumer for group '{self.group_id}'...")
            self.consumer.close()
            logger.info(f"Consumer for group '{self.group_id}' closed.")
            if self._consumer_thread and threading.current_thread() != self._consumer_thread:
                # Only join if not trying to join self
                self._consumer_thread.join(timeout=5) # Wait for thread to finish
                if self._consumer_thread.is_alive():
                    logger.warning(f"Consumer thread for '{self.group_id}' did not terminate cleanly.")