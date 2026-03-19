import os
import ccxt
import ollama
from dotenv import load_dotenv

def test_environment():
    print("Testing Environment Setup...")
    # Load .env
    load_dotenv()
    binance_api = os.getenv("BINANCE_API_KEY")
    print(f"1. .env Load Check: {'SUCCESS' if binance_api else 'NOT SET YET (Expected for now)'}")

    # CCXT Load Check
    try:
        exchange = ccxt.binance()
        ticker = exchange.fetch_ticker('BTC/USDT')
        print(f"2. CCXT Binance Check: SUCCESS (BTC Price: {ticker['last']})")
    except Exception as e:
        print(f"2. CCXT Binance Check: FAILED ({e})")

    # Ollama Check
    try:
        response = ollama.chat(model='gemma2:2b', messages=[
            {
                'role': 'user',
                'content': 'Say hello in one word.',
            }
        ])
        print(f"3. Ollama gemma2:2b Check: SUCCESS (Response: {response['message']['content'].strip()})")
    except Exception as e:
        print(f"3. Ollama gemma2:2b Check: FAILED ({e}) - Ensure Ollama is running and gemma2:2b is pulled.")

if __name__ == "__main__":
    test_environment()
