from confluent_kafka import Producer
import yfinance as yf
import json
import time

# Kafka configuration
def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed for record {msg.key()}: {err}")
    else:
        print(f"Produced to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

producer = Producer({'bootstrap.servers': 'localhost:9092'})
topic = 'market_data'
symbol = 'AAPL'

while True:
    data = yf.download(tickers=symbol, period='1d', interval='1m')
    latest = data.iloc[-1]
    record = {
        'symbol': symbol,
        'timestamp': str(latest.name),
        'open': latest['Open'],
        'high': latest['High'],
        'low': latest['Low'],
        'close': latest['Close'],
        'volume': int(latest['Volume'])
    }
    payload = json.dumps(record)
    producer.produce(topic, key=symbol, value=payload, callback=delivery_report)
    producer.flush()
    time.sleep(60)
