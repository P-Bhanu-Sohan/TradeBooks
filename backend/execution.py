# execution.py - Remove dependency on windows
from . import config
from .orderbook import record_trade
from .config import CASH, POSITIONS, save_state
def execute_order(stock, action, qty, price):  # Add price parameter
    global CASH
    notional = price * qty
    
    if action in ['BUY', 'BUY_TO_COVER']:
        CASH -= notional
        POSITIONS[stock] += qty
    else:  # SELL, SELL_SHORT
        CASH += notional
        POSITIONS[stock] -= qty

    # Calculate P&L (removed book value calculation since it's done in orderbook)
    record_trade(stock, action, qty, price)
    # execution.py
    config.save_state()  # Persist state after each trade
    save_state()