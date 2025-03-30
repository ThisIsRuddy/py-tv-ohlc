import csv
from datetime import datetime
from pathlib import Path

from .tradingview import get_candles

Path("data").mkdir(exist_ok=True)

async def store_candles(client, symbol: str, timeframe: int, amount: int = 1000):
    print(f"[store_candles] Fetching candles for symbol: {symbol}, timeframe: {timeframe}")
    candles = await get_candles(
        client=client,
        symbols=[symbol],
        amount=amount,
        timeframe=timeframe
    )
    print(f"[store_candles] Candle count: {len(candles)}")

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"data/{symbol}-{timeframe}-{timestamp}.csv".replace(":", "-")

    print(f"[store_candles] Writing candles to file: {filename}")
    with open(filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for c in candles:
            writer.writerow([
                c.timestamp,
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume
            ])
    print(f"[store_candles] Stored candles to CSV for symbol: {symbol}, timeframe: {timeframe}, file: {filename}")