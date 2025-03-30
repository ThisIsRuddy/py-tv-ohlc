import os
import asyncio
from dotenv import load_dotenv

from lib.tradingview import TradingviewClient
from lib.storeCandles import store_candles

load_dotenv()

TV_SESSION_ID = os.getenv("TV_SESSION_ID")
TV_MAX_CANDLES = os.getenv("TV_MAX_CANDLES")

if not TV_SESSION_ID:
    raise EnvironmentError("TV_SESSION_ID is required")


async def main():
    client = TradingviewClient()
    await client.connect()

    symbols = [
        "BYBIT:BTCUSDT.P",
        "BYBIT:ETHUSDT.P",
        "BYBIT:AVAXUSDT.P",
        "BYBIT:DOGEUSDT.P",
        "BYBIT:LTCUSDT.P",
        "BYBIT:XRPUSDT.P",
    ]
    timeframes = [
        1, 5, 15, 30, 60, 120, 240, "1D", "1W", "1M"
    ]

    try:
        for symbol in symbols:
            for timeframe in timeframes:
                await store_candles(
                    client=client,
                    symbol=symbol,
                    timeframe=timeframe,
                    amount=int(TV_MAX_CANDLES) | 10000
                )

    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[main] Interrupted by user. Exiting.")
    except Exception as e:
        print(f"[main] Uncaught exception: {e}")
