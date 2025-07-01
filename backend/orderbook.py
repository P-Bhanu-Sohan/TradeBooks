import csv
import os
import logging
from datetime import datetime
from . import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def record_trade(symbol, action, qty, price):
    """Reliable trade recording with multiple fallbacks"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(config.ORDER_BOOK_PATH), exist_ok=True)
        
        # File creation flag
        create_header = not os.path.exists(config.ORDER_BOOK_PATH)
        
        # Open file in append mode
        with open(config.ORDER_BOOK_PATH, 'a', newline='') as f:
            writer = csv.writer(f)
            
            # Write header if new file
            if create_header:
                writer.writerow([
                    'timestamp', 'symbol', 'action', 'qty', 'price', 
                    'notional', 'cash', 'holdings_value', 'equity'
                ])
                logger.info("Created new order book with header")
            
            # Prepare data
            ts = datetime.utcnow().isoformat()
            notional = price * qty
            
            # Write trade record
            writer.writerow([
                ts,
                symbol,
                action,
                qty,
                round(price, 4),
                round(notional, 4),
                round(config.CASH, 4),
                round(config.HOLDINGS_VALUE, 4),
                round(config.get_equity(), 4)
            ])
            
            # Force write to disk
            f.flush()
        
        # Success message
        print(f"\n✅ TRADE RECORDED: {symbol} {action} {qty} @ {price}")
        print(f"   Location: {config.ORDER_BOOK_PATH}")
        return True
        
    except Exception as e:
        # Fallback 1: Try simple text log
        try:
            fallback_path = os.path.join(config.DATA_DIR, 'emergency_trades.log')
            with open(fallback_path, 'a') as f:
                f.write(f"{datetime.utcnow().isoformat()},{symbol},{action},{qty},{price}\n")
            print(f"\n⚠️ PRIMARY RECORD FAILED - Used emergency log")
            print(f"   Emergency location: {fallback_path}")
            return True
        except:
            # Final fallback: Console only
            print(f"\n❌ CRITICAL FAILURE: Could not record trade anywhere")
            print(f"   Trade details: {symbol} {action} {qty} @ {price}")
            return False