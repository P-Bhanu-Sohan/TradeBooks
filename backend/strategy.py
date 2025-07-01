# strategy.py - Pass price to execute_order
import json
import os
import csv
from collections import deque
from datetime import datetime, timedelta
from .execution import execute_order
from .config import (
    PROJECT_ROOT, INITIAL_CAPITAL, CASH, POSITIONS,
    LOOKBACK, ZENTRY, ZEXIT, RISK_PER_TRADE,
    REBALANCE_INTERVAL, last_rebalance, DATA_PATHS
)

# Initialize windows with historical data
windows = {s: deque(maxlen=LOOKBACK) for s in POSITIONS}

def initialize_windows():
    for stock in POSITIONS:
        path = DATA_PATHS[stock]
        if os.path.exists(path):
            with open(path) as f:
                reader = csv.DictReader(f)
                for row in list(reader)[-LOOKBACK:]:
                    windows[stock].append(float(row['close']))

initialize_windows()

def get_equity():
    return CASH + sum(POSITIONS[s] * (windows[s][-1] if windows[s] else 0) for s in POSITIONS)

def dynamic_weights():
    scores = {}
    for s, win in windows.items():
        if len(win) >= 2:
            returns = (win[-1] - win[0]) / win[0]
            scores[s] = max(returns, 0)
        else:
            scores[s] = 0
    total = sum(scores.values()) or 1
    return {s: scores[s] / total for s in POSITIONS}

def rebalance_if_needed(now):
    global last_rebalance
    if last_rebalance is None or (now - last_rebalance) >= timedelta(minutes=REBALANCE_INTERVAL):
        last_rebalance = now
        equity = get_equity()
        weights = dynamic_weights()
        for stock, target_weight in weights.items():
            if not windows[stock]:
                continue
            price = windows[stock][-1]
            target_shares = int((equity * target_weight) / price)
            current_shares = POSITIONS[stock]
            delta = target_shares - current_shares
            
            if delta > 0:
                execute_order(stock, 'BUY', delta, price)  # Pass price
            elif delta < 0:
                execute_order(stock, 'SELL', -delta, price)  # Pass price

def handle_tick(stock, tick):
    data = json.loads(tick) if isinstance(tick, str) else tick
    now = datetime.fromisoformat(data['datetime'])
    price = data['close']
    win = windows[stock]
    win.append(price)
    
    if len(win) < LOOKBACK:
        return
    
    mean = sum(win) / LOOKBACK
    std = (sum((p - mean)**2 for p in win) / LOOKBACK)**0.5 or 1e-6
    z = (price - mean) / std
    
    equity = get_equity()
    risk = equity * RISK_PER_TRADE
    qty = max(int(risk / (std or 1e-6)), 1)
    current_position = POSITIONS[stock]
    
    if z > ZENTRY and current_position >= 0:
        if current_position > 0:
            execute_order(stock, 'SELL', current_position, price)  # Pass price
        execute_order(stock, 'SELL_SHORT', qty, price)  # Pass price
        
    elif z < -ZENTRY and current_position <= 0:
        if current_position < 0:
            execute_order(stock, 'BUY_TO_COVER', -current_position, price)  # Pass price
        execute_order(stock, 'BUY', qty, price)  # Pass price
        
    elif abs(z) < ZEXIT and current_position != 0:
        if current_position > 0:
            execute_order(stock, 'SELL', current_position, price)  # Pass price
        else:
            execute_order(stock, 'BUY_TO_COVER', -current_position, price)  # Pass price
    
    rebalance_if_needed(now)