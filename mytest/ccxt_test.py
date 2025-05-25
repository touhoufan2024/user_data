import ccxt

def fetch_ticker_price(exchange_name, symbol):
    try:
        exchange_class = getattr(ccxt, exchange_name)
        exchange = exchange_class()
        ticker = exchange.fetch_ticker(symbol)
        print(f"{exchange_name} {symbol} latest price: {ticker['last']}")
        return ticker['last']
    except Exception as e:
        print(f"Failed to fetch {symbol} price from {exchange_name}: {e}")
        return None

if __name__ == "__main__":
    symbol = "BTC/USDT"

    print("Fetching Binance BTC/USDT price...")
    binance_price = fetch_ticker_price("binance", symbol)

    print("\nFetching OKX BTC/USDT price...")
    okx_price = fetch_ticker_price("okx", symbol)
