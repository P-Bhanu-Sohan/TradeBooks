 # orderbook.py - Fixed absolute path handling
import csv
import os
from datetime import datetime
from .config import POSITIONS, CASH, PROJECT_ROOT

OUTPUT = os.path.join(PROJECT_ROOT, 'order_book.csv')  # Absolute path

# Initialize CSV with header
if not os.path.exists(OUTPUT):
    with open(OUTPUT, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'symbol', 'action', 'qty', 'price', 'notional', 'cash', 'equity'])

def record_trade(symbol, action, qty, price):
    ts = datetime.utcnow().isoformat()
    notional = price * qty
    equity = CASH + sum(POSITIONS[s] * price for s in POSITIONS)
    with open(OUTPUT, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([ts, symbol, action, qty, price, notional, CASH, equity])