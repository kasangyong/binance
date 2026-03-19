import os
import ccxt
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'options': {'defaultType': 'future'}
})

def debug_positions():
    print("Fetching positions...")
    positions = exchange.fetch_positions()
    print(f"Total positions items: {len(positions)}")
    
    # Show first few symbols to see the format
    for pos in positions[:10]:
        print(f"Symbol: {pos['symbol']}, Contracts: {pos['contracts']}")
    
    # Search for XRP related
    print("\nSearching for XRP positions:")
    for pos in positions:
        if 'XRP' in pos['symbol']:
            print(f"Found: {pos['symbol']}, Size: {pos['contracts']}, Entry: {pos['entryPrice']}, Raw: {pos['info']['symbol']}")

    # Check the specific logic in trading_bot.py
    target = 'XRP/USDT'
    target_norm = target.replace('/', '')
    print(f"\nTarget Normalized: {target_norm}")
    
    for pos in positions:
        pos_norm = pos['symbol'].replace(':', '').replace('/', '')
        if pos_norm == target_norm: # Simple match attempt
             print(f"MATCH! Symbol: {pos['symbol']} matches {target}")
        
        # Another common format is XRPUSDT
        if pos['symbol'] == 'XRPUSDT' or pos['info']['symbol'] == 'XRPUSDT':
             print(f"MATCH by info/direct! Symbol: {pos['symbol']}")

if __name__ == "__main__":
    debug_positions()
