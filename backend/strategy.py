import json
import numpy as np
import logging
from collections import deque
from datetime import datetime
from .execution import execute_order
from . import config  # Import the entire config module

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Data storage
price_windows = {stock: deque(maxlen=config.VOLUME_WINDOW) for stock in config.POSITIONS}
bar_windows = {stock: deque(maxlen=config.VOLUME_WINDOW) for stock in config.POSITIONS}
ema_short = {stock: None for stock in config.POSITIONS}
ema_long = {stock: None for stock in config.POSITIONS}
atr = {stock: None for stock in config.POSITIONS}

# Initialize EMAs and ATR
def initialize_indicators(stock, price):
    ema_short[stock] = price
    ema_long[stock] = price
    atr[stock] = 0.0
    logger.info(f"Initialized indicators for {stock} at price {price}")

# Update technical indicators
def update_indicators(stock, bar):
    close = bar['close']
    
    # Update EMAs
    if ema_short[stock] is None:
        initialize_indicators(stock, close)
    else:
        alpha_short = 2 / (config.EMA_SHORT_WINDOW + 1)
        alpha_long = 2 / (config.EMA_LONG_WINDOW + 1)
        ema_short[stock] = alpha_short * close + (1 - alpha_short) * ema_short[stock]
        ema_long[stock] = alpha_long * close + (1 - alpha_long) * ema_long[stock]
    
    # Update ATR
    if len(bar_windows[stock]) >= 2:
        prev_bar = list(bar_windows[stock])[-2]
        tr = max(
            bar['high'] - bar['low'],
            abs(bar['high'] - prev_bar['close']),
            abs(bar['low'] - prev_bar['close'])
        )
        if atr[stock] is None:
            atr[stock] = tr
        else:
            alpha_atr = 2 / (config.ATR_WINDOW + 1)
            atr[stock] = alpha_atr * tr + (1 - alpha_atr) * atr[stock]

# Trading logic
def handle_tick(stock, tick):
    data = json.loads(tick) if isinstance(tick, str) else tick
    bar = {
        'datetime': data['datetime'],
        'open': float(data['open']),
        'high': float(data['high']),
        'low': float(data['low']),
        'close': float(data['close']),
        'pct_change': abs(float(data.get('% change', 0)))  # Use absolute % change as volume proxy
    }
    
    # Update last price
    config.LAST_PRICE[stock] = bar['close']
    
    # Update portfolio value
    config.update_holdings_value()
    
    # Store the bar
    price_windows[stock].append(bar['close'])
    bar_windows[stock].append(bar)
    
    # Log bar received
    logger.info(f"{stock} - Bar: {bar['datetime']} | O: {bar['open']} H: {bar['high']} L: {bar['low']} C: {bar['close']} | %chg: {bar['pct_change']}")
    
    # Update indicators if we have enough data
    if len(bar_windows[stock]) > 1:
        update_indicators(stock, bar)
    
    # Skip if not enough data for trading decisions
    min_data_needed = max(config.VOLUME_WINDOW, 2)
    if len(bar_windows[stock]) < min_data_needed or atr[stock] is None:
        logger.info(f"{stock} - Not enough data: {len(bar_windows[stock])} bars (need {min_data_needed}) or ATR not set")
        return
    
    current_position = config.POSITIONS[stock]
    current_price = bar['close']
    logger.info(f"{stock} - Position: {current_position}, Entry Price: {config.ENTRY_PRICES[stock]}, ATR: {atr[stock]}, EMA Short: {ema_short[stock]}, EMA Long: {ema_long[stock]}")
    
    # EXIT LOGIC
    if current_position != 0:
        entry_price = config.ENTRY_PRICES[stock]
        atr_val = atr[stock] or (current_price * 0.01)  # Fallback to 1% if ATR not set
        
        # Long position exit conditions
        if current_position > 0:
            take_profit = entry_price + config.TAKE_PROFIT_MULTIPLIER * atr_val
            stop_loss = entry_price - config.STOP_LOSS_MULTIPLIER * atr_val
            logger.info(f"{stock} - Long position: entry={entry_price}, current={current_price}, TP={take_profit}, SL={stop_loss}")
            
            if current_price >= take_profit or current_price <= stop_loss:
                logger.info(f"{stock} - Exiting long position at {current_price}")
                execute_order(stock, 'SELL', current_position, current_price)
                config.ENTRY_PRICES[stock] = 0.0
        
        # Short position exit conditions
        elif current_position < 0:
            take_profit = entry_price - config.TAKE_PROFIT_MULTIPLIER * atr_val
            stop_loss = entry_price + config.STOP_LOSS_MULTIPLIER * atr_val
            logger.info(f"{stock} - Short position: entry={entry_price}, current={current_price}, TP={take_profit}, SL={stop_loss}")
            
            if current_price <= take_profit or current_price >= stop_loss:
                logger.info(f"{stock} - Exiting short position at {current_price}")
                execute_order(stock, 'BUY', -current_position, current_price)
                config.ENTRY_PRICES[stock] = 0.0
    
    # ENTRY LOGIC (only if flat)
    if config.POSITIONS[stock] == 0:
        # Volume surge detection
        vol_proxies = [b['pct_change'] for b in list(bar_windows[stock])[:-1]]  # Exclude current bar
        vol_avg = np.mean(vol_proxies) if vol_proxies else 0
        vol_surge = bar['pct_change'] > config.VOLUME_MULTIPLIER * vol_avg
        logger.info(f"{stock} - Volume surge: current={bar['pct_change']}, avg={vol_avg}, surge={vol_surge}")
        
        # Price rejection signal (requires at least 2 bars)
        if len(bar_windows[stock]) >= 2:
            prev_bar = list(bar_windows[stock])[-2]
            prev_range = prev_bar['high'] - prev_bar['low']
            
            if prev_range > 0:
                # Bullish rejection (long lower wick)
                bullish_reject = (prev_bar['close'] - prev_bar['low']) / prev_range > config.REJECTION_THRESHOLD
                # Bearish rejection (long upper wick)
                bearish_reject = (prev_bar['high'] - prev_bar['close']) / prev_range > config.REJECTION_THRESHOLD
            else:
                bullish_reject = False
                bearish_reject = False
            logger.info(f"{stock} - Rejection signals: bullish={bullish_reject}, bearish={bearish_reject}, prev_range={prev_range}")
        else:
            bullish_reject = False
            bearish_reject = False
            logger.info(f"{stock} - Not enough bars for rejection signal")
        
        # Trend confirmation
        trend_bullish = ema_short[stock] > ema_long[stock]
        trend_bearish = ema_short[stock] < ema_long[stock]
        logger.info(f"{stock} - Trend: bullish={trend_bullish}, bearish={trend_bearish}")
        
        # Calculate position size based on risk
        equity = config.get_equity()
        risk_amount = equity * config.RISK_PER_TRADE
        position_size = max(int(risk_amount / current_price), 1) if current_price > 0 else 0
        logger.info(f"{stock} - Position size: {position_size} (equity={equity}, risk_amount={risk_amount}, price={current_price})")
        
        # Entry conditions
        if vol_surge and bullish_reject and trend_bullish and position_size > 0:
            logger.info(f"{stock} - Entering BUY at {current_price}")
            execute_order(stock, 'BUY', position_size, current_price)
            config.ENTRY_PRICES[stock] = current_price
        
        elif vol_surge and bearish_reject and trend_bearish and position_size > 0:
            logger.info(f"{stock} - Entering SELL at {current_price}")
            execute_order(stock, 'SELL', position_size, current_price)
            config.ENTRY_PRICES[stock] = current_price
        else:
            logger.info(f"{stock} - No entry signal")
    
    # Save state after processing
    config.save_state()