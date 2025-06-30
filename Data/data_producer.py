# Assuming this is the content of your existing data_producer.py
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
        logger.error(f"Delivery failed for record {msg.key().decode('utf-8')}: {err}")
    else:
        # logger.debug(f"Produced to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")
        pass # Suppress frequent print for interval streaming

producer_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'acks': 'all',  # Ensure data is safely replicated
    'retries': 3,   # Number of retries on failed production
    'linger.ms': 0, # Send immediately for 1-second interval, no batching needed
    'batch.size': 1 # Send individual messages immediately, as we're delaying per message
}
producer = Producer(producer_conf)

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

    period_to_check = "7d" # yfinance 1m interval only allows for last 7 days of data
    today_ist = get_current_ist_time()
    today_date_ist = today_ist.date()

    all_symbols_data = {} # Dictionary to store DataFrame for each symbol

    try:
        # Download data for all symbols at once.
        data = yf.download(
            tickers=symbols,
            period=period_to_check,
            interval=interval,
            prepost=False,
            actions=False,
            group_by='ticker' # This is crucial for multi-symbol download structure
        )

        if data.empty:
            logger.warning(f"No data found for any of the symbols in the last {period_to_check} with interval {interval}.")
            return {}

        for symbol in symbols:
            # Extract data for the current symbol.
            # Need to handle cases where a symbol might not have data if group_by='ticker' isn't perfect
            if isinstance(data.columns, pd.MultiIndex):
                if symbol not in data.columns.levels[0]:
                    logger.warning(f"No data found for {symbol} in the downloaded MultiIndex DataFrame. Skipping.")
                    continue
                symbol_data = data[symbol]
            else: # Single symbol download returns non-MultiIndex
                symbol_data = data

            # Convert index to timezone-aware datetime objects and then to IST for filtering
            if symbol_data.index.tz is None:
                symbol_data.index = symbol_data.index.tz_localize('America/New_York', ambiguous='infer', nonexistent='shift_forward')
            symbol_data.index = symbol_data.index.tz_convert('Asia/Kolkata')

            # Get unique dates present in the data, sorted descending (most recent first)
            available_dates_ist = sorted(symbol_data.index.normalize().unique(), reverse=True)

            last_trading_day_data = pd.DataFrame()
            for market_day_ist in available_dates_ist:
                if market_day_ist.date() == today_date_ist:
                    continue
                
                last_trading_day_data = symbol_data[symbol_data.index.normalize() == market_day_ist]
                if not last_trading_day_data.empty:
                    logger.info(f"[{get_current_ist_time()}] Identified last complete trading day as {market_day_ist.strftime('%Y-%m-%d IST')} for {symbol}.")
                    break
            
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
            'volume': int(row['Volume'])
        }
        payload = json.dumps(record).encode('utf-8')
        
        try:
            producer.produce(topic, key=symbol.encode('utf-8'), value=payload, callback=delivery_report)
            producer.poll(0) # Process delivery reports immediately
            
            # logger.info(f"[{get_current_ist_time()}] Streamed bar for {symbol}: {index.strftime('%Y-%m-%d %H:%M:%S IST')} - Close: {row['Close']}")
        except Exception as e:
            logger.error(f"[{get_current_ist_time()}] Error producing message for {symbol} to Kafka: {e}", exc_info=True)

        time.sleep(delay_seconds) # Simulate streaming delay

    producer.flush() # Ensure all remaining messages are sent for this symbol
    logger.info(f"[{get_current_ist_time()}] Finished streaming historical data for {symbol}.")

# --- Main Orchestration Logic ---
if __name__ == '__main__':
    logger.info(f"[{get_current_ist_time()}] Starting daily delayed data feeder for symbols: {', '.join(STOCK_SYMBOLS)}...")

    # Step 1: Download yesterday's data for all symbols
    all_yesterdays_data = get_last_trading_day_data_for_symbols(STOCK_SYMBOLS, interval='1m')

    streaming_threads = []

    if all_yesterdays_data:
        # Step 2: Stream yesterday's data for each symbol concurrently in 1-second intervals
        for symbol, data_df in all_yesterdays_data.items():
            if not data_df.empty:
                logger.info(f"[{get_current_ist_time()}] Creating streaming thread for {symbol}...")
                thread = threading.Thread(
                    target=stream_historical_data_in_intervals,
                    args=(symbol, producer, KAFKA_TOPIC_DAILY_DELAYED_BARS, data_df, STREAM_INTERVAL_SECONDS),
                    daemon=True # Make thread a daemon so it exits with main process
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

    producer.flush()
    logger.info(f"[{get_current_ist_time()}] Daily delayed data feeder has completed its overall task.")