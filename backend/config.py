import os
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Absolute path to project root
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
logger.info(f"Project root: {PROJECT_ROOT}")

# Ensure data directory exists
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
logger.info(f"Data directory: {DATA_DIR}")

# Guaranteed writable order book path
ORDER_BOOK_PATH = os.path.join(DATA_DIR, 'order_book.csv')
logger.info(f"Order book location: {ORDER_BOOK_PATH}")

# Kafka settings
KAFKA_CONFIG = {'bootstrap.servers': 'localhost:9092'}
TOPICS = {
    'MSFT': 'topic_msft', 'AAPL': 'topic_aapl', 'AMZN': 'topic_amzn',
    'NVDA': 'topic_nvda', 'TSLA': 'topic_tsla', 'GOOG': 'topic_goog'
}
DATA_PATHS = {stock: os.path.join(DATA_DIR, f"{stock}.csv") for stock in TOPICS}

# Portfolio accounting
INITIAL_CAPITAL = 100_000.0
CASH = INITIAL_CAPITAL
POSITIONS = {stock: 0 for stock in TOPICS}
LAST_PRICE = {stock: 0.0 for stock in TOPICS}
ENTRY_PRICES = {stock: 0.0 for stock in TOPICS}
HOLDINGS_VALUE = 0.0

# Strategy parameters
VOLUME_WINDOW = 20
VOLUME_MULTIPLIER = 3.0
REJECTION_THRESHOLD = 0.7
EMA_SHORT_WINDOW = 5
EMA_LONG_WINDOW = 20
ATR_WINDOW = 14
STOP_LOSS_MULTIPLIER = 0.3
TAKE_PROFIT_MULTIPLIER = 0.5
RISK_PER_TRADE = 0.01

# Initialize and manage state
def init_state():
    global CASH, POSITIONS, LAST_PRICE, ENTRY_PRICES, HOLDINGS_VALUE
    state_file = os.path.join(DATA_DIR, 'trading_state.json')
    
    if os.path.exists(state_file):
        try:
            with open(state_file) as f:
                state = json.load(f)
                CASH = state.get('CASH', INITIAL_CAPITAL)
                POSITIONS = state.get('POSITIONS', {stock: 0 for stock in TOPICS})
                LAST_PRICE = state.get('LAST_PRICE', {stock: 0.0 for stock in TOPICS})
                ENTRY_PRICES = state.get('ENTRY_PRICES', {stock: 0.0 for stock in TOPICS})
                HOLDINGS_VALUE = state.get('HOLDINGS_VALUE', 0.0)
            logger.info("Loaded state from file")
        except:
            reset_state()
    else:
        reset_state()

def reset_state():
    global CASH, POSITIONS, LAST_PRICE, ENTRY_PRICES, HOLDINGS_VALUE
    CASH = INITIAL_CAPITAL
    POSITIONS = {stock: 0 for stock in TOPICS}
    LAST_PRICE = {stock: 0.0 for stock in TOPICS}
    ENTRY_PRICES = {stock: 0.0 for stock in TOPICS}
    HOLDINGS_VALUE = 0.0
    save_state()
    logger.info("Reset to initial state")

def save_state():
    state = {
        'CASH': CASH,
        'POSITIONS': POSITIONS,
        'LAST_PRICE': LAST_PRICE,
        'ENTRY_PRICES': ENTRY_PRICES,
        'HOLDINGS_VALUE': HOLDINGS_VALUE
    }
    state_file = os.path.join(DATA_DIR, 'trading_state.json')
    with open(state_file, 'w') as f:
        json.dump(state, f)
    logger.info("Saved state to file")

def update_holdings_value():
    global HOLDINGS_VALUE
    HOLDINGS_VALUE = sum(
        POSITIONS[stock] * LAST_PRICE[stock]
        for stock in POSITIONS
    )

def get_equity():
    return CASH + HOLDINGS_VALUE

# Verify path access
def verify_path_access():
    try:
        test_path = os.path.join(DATA_DIR, 'access_test.tmp')
        with open(test_path, 'w') as f:
            f.write("test")
        os.remove(test_path)
        logger.info("Path access verified: directory is writable")
        return True
    except Exception as e:
        logger.error(f"PATH ACCESS DENIED: {str(e)}")
        return False

# Initialize on import
init_state()
verify_path_access()