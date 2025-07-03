import logging
from . import config
from .orderbook import record_trade

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def execute_order(stock, action, qty, price):
    """Execute trade with robust recording""" 
    # Input validation
    if qty <= 0:
        logger.error(f"Invalid quantity: {qty} for {stock}")
        return
    if price <= 0:
        logger.error(f"Invalid price: {price} for {stock}")
        return
        
    # Calculate trade value
    notional = price * qty
    
    # Pre-trade snapshot
    pre_cash = config.CASH
    pre_holdings = config.HOLDINGS_VALUE
    pre_equity = config.get_equity()
    
    print(f"\n⭐ EXECUTING TRADE: {stock} {action} {qty} @ {price}")
    print(f"   Pre-trade cash: ${pre_cash:,.2f}")
    print(f"   Pre-trade holdings: ${pre_holdings:,.2f}")
    print(f"   Pre-trade equity: ${pre_equity:,.2f}")
    
    # Update cash and positions
    try:
        if action == 'BUY':
            if config.CASH < notional:
                logger.error(f"Insufficient cash for {qty} {stock} @ {price}")
                return
                
            config.CASH -= notional
            config.POSITIONS[stock] += qty
            config.ENTRY_PRICES[stock] = price
            
        elif action == 'SELL':
            if config.POSITIONS[stock] < qty:
                logger.error(f"Insufficient shares to sell {qty} {stock}")
                return
                
            config.CASH += notional
            config.POSITIONS[stock] -= qty
            
            # Clear entry price if position closed
            if config.POSITIONS[stock] == 0:
                config.ENTRY_PRICES[stock] = 0.0
                
        else:
            logger.error(f"Invalid action: {action}")
            return
            
        # Update last price and portfolio value
        config.LAST_PRICE[stock] = price
        config.update_holdings_value()
        
    except Exception as e:
        logger.error(f"Trade execution failed: {str(e)}")
        return
    
    # Record trade
    record_trade(stock, action, qty, price)
    
    # Post-trade snapshot
    print(f"   Post-trade cash: ${config.CASH:,.2f}")
    print(f"   Post-trade holdings: ${config.HOLDINGS_VALUE:,.2f}")
    print(f"   Post-trade equity: ${config.get_equity():,.2f}")
    
    # Save state
    config.save_state()