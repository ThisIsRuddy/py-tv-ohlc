## TradingView Candles Downloader

### Installation
- `pip install dotenv aiohttp`

### Setup & Usage
- Copy `.env.SAMPLE` to `.env` and fill in the required values.
  - `TV_SESSION_ID` TradingView session ID
  - `TV_MAX_CANDLES` increase this to match you TV subscription (10000 Standard, 20000 Premium, 40000 Ultimate)
- Edit `src/index.py` and adjust the symbols + timeframes as required.
- Run the script `python src/index.py` to download the candles.
- The candle data will be saved in the `data` folder in CSV format.
