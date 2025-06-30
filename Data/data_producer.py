# File: Data/data_producer.py

import yfinance as yf
from confluent_kafka import Producer
import json
import time
import datetime
import pandas as pd
import threading # To handle streaming multiple stocks concurrently
import logging
import sys

# Configure logging for the producer
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("DataProducer")


# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
KAFKA_TOPIC_DAILY_DELAYED_BARS = 'market_data_daily_delayed_bars'
STOCK_SYMBOLS = ['GOOG', 'AAPL', 'AMZN', 'META', 'NFLX', 'MSFT', 'TSLA']
STREAM_INTERVAL_SECONDS = 1 # Stream each 1-minute bar every 1 second

# --- Kafka Producer Setup ---
def delivery_report(err, msg):
    """
    Callback function for Kafka message delivery reports.
    """
    if err is not None:
        logger.error(f"Delivery failed for record {msg.key().decode('utf-8') if msg.key() else 'N/A'}: {err}")
    else:
        # This can be noisy, uncomment for detailed debugging of message delivery
        # logger.debug(f"Produced to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()} (key: {msg.key().decode('utf-8') if msg.key() else 'N/A'})")
        pass 

producer_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'acks': 'all',  # Ensure data is safely replicated
    'retries': 3,   # Number of retries on failed production
    'linger.ms': 0, # Send immediately for 1-second interval, no batching needed
    'batch.size': 1 # Send individual messages immediately, as we're delaying per message
}
try:
    producer = Producer(producer_conf, on_delivery=delivery_report)
except Exception as e:
    logger.critical(f"Failed to initialize Kafka Producer: {e}", exc_info=True)
    sys.exit(1)


# --- Functions ---

def get_current_ist_time():
    """
    Get the current time in IST (Indian Standard Time).
    """
    return datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))

def get_last_trading_day_data_for_symbols(symbols, interval='1m'):
    """
    Downloads data for the last *complete* trading day for a list of symbols.
    Returns a dictionary of DataFrames, one for each symbol.
    """
    logger.info(f"[{get_current_ist_time()}] Determining last trading day for {', '.join(symbols)}...")

    # yfinance 1m interval only allows for last 7 days of data, anything <1d is max 60 days
    # We use "7d" period to ensure we capture at least one full trading day
    period_to_check = "7d" 
    today_ist = get_current_ist_time()
    today_date_ist = today_ist.date()

    all_symbols_data = {} # Dictionary to store DataFrame for each symbol

    try:
        # Download data for all symbols at once.
        # group_by='ticker' will give a MultiIndex where the first level is the ticker symbol
        data = yf.download(
            tickers=symbols,
            period=period_to_check,
            interval=interval,
            prepost=False, # Do not get pre/post market data
            actions=False,  # Do not get dividend/split actions
            group_by='ticker', # This is crucial for multi-symbol download structure
            progress=False # Suppress progress bar for cleaner logs
        )

        if data.empty:
            logger.warning(f"No data found for any of the symbols in the last {period_to_check} with interval {interval}.")
            return {}

        for symbol in symbols:
            # Extract data for the current symbol.
            # Check if the symbol exists in the MultiIndex columns
            if isinstance(data.columns, pd.MultiIndex):
                if symbol not in data.columns.levels[0]:
                    logger.warning(f"No data found for {symbol} in the downloaded MultiIndex DataFrame. Skipping.")
                    continue
                symbol_data = data[symbol]
            else: 
                # This case handles if only one symbol was requested and yfinance returns a single-index DataFrame
                # However, since `symbols` is always a list, `data` will likely be MultiIndex.
                # This is a fallback for robustness.
                symbol_data = data

            # Convert index to timezone-aware datetime objects and then to IST for filtering
            # yfinance typically returns data in the exchange's local time (e.g., US/Eastern for AAPL)
            # It's safest to localize to the known exchange timezone first, then convert to IST.
            if symbol_data.index.tz is None:
                # Assuming US/Eastern for US stocks, adjust if tracking other exchanges
                symbol_data.index = symbol_data.index.tz_localize('America/New_York', ambiguous='infer', nonexistent='shift_forward')
            symbol_data.index = symbol_data.index.tz_convert('Asia/Kolkata') # Convert to IST for filtering "yesterday" from our perspective

            # Get unique dates present in the data, sorted descending (most recent first)
            available_dates_ist = sorted(symbol_data.index.normalize().unique(), reverse=True)

            last_trading_day_data = pd.DataFrame()
            # Iterate through available dates to find the first *complete* trading day prior to today
            for market_day_ist in available_dates_ist:
                if market_day_ist.date() == today_date_ist:
                    # Skip today's data as we want "yesterday's" complete data
                    continue
                
                # Filter data for this specific market day
                last_trading_day_data = symbol_data[symbol_data.index.normalize() == market_day_ist]
                if not last_trading_day_data.empty:
                    logger.info(f"[{get_current_ist_time()}] Identified last complete trading day as {market_day_ist.strftime('%Y-%m-%d IST')} for {symbol}.")
                    break # Found the last complete trading day, exit loop
            
            if last_trading_day_data.empty:
                logger.warning(f"[{get_current_ist_time()}] Could not find a complete last trading day in the downloaded data for {symbol}. Skipping.")
                continue

            # Ensure data is sorted by timestamp for sequential streaming
            all_symbols_data[symbol] = last_trading_day_data.sort_index()

    except Exception as e:
        logger.error(f"[{get_current_ist_time()}] Error downloading yesterday's data for symbols {', '.join(symbols)}: {e}", exc_info=True)
        return {}

    return all_symbols_data

def stream_historical_data_in_intervals(symbol, producer, topic, data_to_stream, delay_seconds):
    """
    Streams historical 1-minute bar data for a single symbol to Kafka,
    simulating a stream with a fixed delay between each bar.
    """
    if data_to_stream.empty:
        logger.warning(f"[{get_current_ist_time()}] No historical data to stream for {symbol}.")
        return

    logger.info(f"[{get_current_ist_time()}] Starting to stream {len(data_to_stream)} historical 1-minute bars for {symbol} to '{topic}' with a {delay_seconds}s interval...")

    for index, row in data_to_stream.iterrows():
        record = {
            'symbol': symbol,
            'timestamp': index.isoformat(), # Use ISO format for timezone-aware datetime
            'open': row['Open'],
            'high': row['High'],
            'low': row['Low'],
            'close': row['Close'],
            'volume': int(row['Volume']) # Ensure volume is an integer
        }
        payload = json.dumps(record).encode('utf-8')
        
        try:
            # Produce the message to Kafka. The delivery_report callback will handle success/failure.
            producer.produce(topic, key=symbol.encode('utf-8'), value=payload)
            # Poll the producer to allow delivery reports to be processed and internal queues to be managed.
            # A timeout of 0ms means it won't block.
            producer.poll(0) 
            
            # This print can be very noisy for 1-second intervals and multiple symbols.
            # Uncomment if you need to see every message being streamed.
            # logger.info(f"[{get_current_ist_time()}] Streamed bar for {symbol}: {index.strftime('%Y-%m-%d %H:%M:%S IST')} - Close: {row['Close']}")
        except Exception as e:
            logger.error(f"[{get_current_ist_time()}] Error producing message for {symbol} to Kafka: {e}", exc_info=True)

        # Simulate streaming delay between each bar
        time.sleep(delay_seconds) 

    # Ensure all remaining messages in the producer's buffer are sent before the function exits
    producer.flush() 
    logger.info(f"[{get_current_ist_time()}] Finished streaming historical data for {symbol}.")

# --- Main Orchestration Logic for Data Producer ---
if __name__ == '__main__':
    logger.info(f"[{get_current_ist_time()}] Starting daily delayed data feeder for symbols: {', '.join(STOCK_SYMBOLS)}...")

    # Step 1: Download yesterday's data for all symbols in one call
    all_yesterdays_data = get_last_trading_day_data_for_symbols(STOCK_SYMBOLS, interval='1m')

    streaming_threads = []

    if all_yesterdays_data:
        # Step 2: Stream yesterday's data for each symbol concurrently in 1-second intervals
        for symbol, data_df in all_yesterdays_data.items():
            if not data_df.empty:
                logger.info(f"[{get_current_ist_time()}] Creating streaming thread for {symbol}...")
                # Create a new thread for each symbol's streaming process
                thread = threading.Thread(
                    target=stream_historical_data_in_intervals,
                    args=(symbol, producer, KAFKA_TOPIC_DAILY_DELAYED_BARS, data_df, STREAM_INTERVAL_SECONDS),
                    daemon=True # Make thread a daemon so it exits with the main process
                )
                streaming_threads.append(thread)
                thread.start()
            else:
                logger.warning(f"[{get_current_ist_time()}] No data to stream for {symbol}. Skipping.")

        # Wait for all streaming threads to complete
        for thread in streaming_threads:
            thread.join()

        logger.info(f"[{get_current_ist_time()}] All historical data streaming for all symbols has completed.")
    else:
        logger.warning(f"[{get_current_ist_time()}] No historical data could be retrieved for any of the specified symbols. Exiting.")

    # Final flush for the main producer to ensure all messages are delivered
    producer.flush()
    logger.info(f"[{get_current_ist_time()}] Daily delayed data feeder has completed its overall task.")

