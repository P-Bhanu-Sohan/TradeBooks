# config.py - Add project root path
import os
import json
# Add this at the top
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STATE_FILE = os.path.join(PROJECT_ROOT, 'trading_state.json')

# Initialize state
def init_state():
    if not os.path.exists(STATE_FILE):
        save_state()

def save_state():
    state = {
        'CASH': CASH,
        'POSITIONS': POSITIONS,
        'last_rebalance': last_rebalance.isoformat() if last_rebalance else None
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def load_state():
    global CASH, POSITIONS, last_rebalance
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
            CASH = state['CASH']
            POSITIONS = state['POSITIONS']
            last_rebalance = datetime.fromisoformat(state['last_rebalance']) if state['last_rebalance'] else None

# Kafka settings
KAFKA_CONFIG = {'bootstrap.servers': 'localhost:9092'}
TOPICS = {
    'MSFT': 'topic_msft', 'AAPL': 'topic_aapl', 'AMZN': 'topic_amzn',
    'NVDA': 'topic_nvda', 'TSLA': 'topic_tsla', 'GOOG': 'topic_goog'
}
DATA_PATHS = {stock: os.path.join(PROJECT_ROOT, f"data/{stock}.csv") for stock in TOPICS}  # Fixed path

# Portfolio accounting
INITIAL_CAPITAL = 100_000.0
CASH = INITIAL_CAPITAL
POSITIONS = {stock: 0 for stock in TOPICS}

# Strategy parameters
LOOKBACK = 20
ZENTRY = 2.0
ZEXIT = 0.5
RISK_PER_TRADE = 0.01

# Rebalance
REBALANCE_INTERVAL = 60  # minutes
last_rebalance = None
# config.py


# ... existing config ...

# State persistence
ORDER_BOOK_PATH = os.path.join(PROJECT_ROOT, 'order_book.csv')
STATE_FILE = os.path.join(PROJECT_ROOT, 'trading_state.json')

def save_state():
    state = {
        'CASH': CASH,
        'POSITIONS': POSITIONS,
        'last_rebalance': last_rebalance.isoformat() if last_rebalance else None
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def load_state():
    global CASH, POSITIONS, last_rebalance
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
            CASH = state['CASH']
            POSITIONS = state['POSITIONS']
            last_rebalance = datetime.fromisoformat(state['last_rebalance']) if state['last_rebalance'] else None
init_state()