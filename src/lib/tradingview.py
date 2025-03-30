import json
import re
import random
import string
import asyncio
import aiohttp
from typing import Dict, List, Union, Callable, Any, Optional, Set

# Type aliases and constants
MAX_BATCH_SIZE = 5000  # found experimentally
Subscriber = Callable[["TradingviewEvent"], None]
Unsubscriber = Callable[[], None]
TradingviewTimeframe = Union[int, str]  # number or '1D', '1W', '1M'


class Candle:
    def __init__(self, timestamp: int, high: float, low: float, open_price: float, close: float, volume: float):
        self.timestamp = timestamp
        self.high = high
        self.low = low
        self.open = open_price
        self.close = close
        self.volume = volume

    def __repr__(self):
        return f"Candle(timestamp={self.timestamp}, open={self.open}, high={self.high}, low={self.low}, close={self.close}, volume={self.volume})"


class TradingviewEvent:
    def __init__(self, name: str, params: List[Any]):
        self.name = name
        self.params = params


class TradingviewClient:
    """A simplified client for TradingView WebSocket API"""

    def __init__(self):
        self.session = None
        self.websocket = None
        self.subscribers: Set[Subscriber] = set()
        self.connected = False

    async def connect(self, session_id: Optional[str] = None) -> None:
        """Connect to TradingView WebSocket API"""
        token = "unauthorized_user_token"

        # Get auth token if session_id is provided
        if session_id:
            self.session = aiohttp.ClientSession()
            async with self.session.get(
                    "https://www.tradingview.com/disclaimer/",
                    headers={"Cookie": f"sessionid={session_id}"}
            ) as response:
                data = await response.text()
                match = re.search(r'"auth_token":"(.+?)"', data)
                if match:
                    token = match.group(1)

        # Create session if not already created
        if not self.session:
            self.session = aiohttp.ClientSession()

        # Connect to WebSocket
        self.websocket = await self.session.ws_connect(
            "wss://prodata.tradingview.com/socket.io/websocket",
            origin="https://prodata.tradingview.com"
        )

        # Start message handling task
        self._message_task = asyncio.create_task(self._handle_messages())

        # Wait for connection to be established
        connected_event = asyncio.Event()

        def on_session(event):
            if event.name == "session_event":
                self.send("set_auth_token", [token])
                self.connected = True
                connected_event.set()
                return True  # Remove this handler after connection
            return False

        self._add_event_handler(on_session)
        await connected_event.wait()

    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        try:
            async for msg in self.websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    payloads = self._parse_message(msg.data)

                    for payload in payloads:
                        if payload["type"] == "ping":
                            await self.websocket.send_str(payload["data"])

                        elif payload["type"] == "session":
                            # Notify session event handlers
                            event = TradingviewEvent("session_event", [payload["data"]])
                            self._notify_subscribers(event)

                        elif payload["type"] == "event":
                            # Notify event subscribers
                            event = TradingviewEvent(
                                name=payload["data"]["m"],
                                params=payload["data"]["p"]
                            )
                            self._notify_subscribers(event)

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"WebSocket error: {self.websocket.exception()}")
                    break

        except Exception as e:
            print(f"Error in message handler: {e}")
        finally:
            self.connected = False

    def _parse_message(self, message: str) -> List[Dict[str, Any]]:
        """Parse TradingView's custom protocol messages"""
        if not message:
            return []

        events = re.split(r"~m~\d+~m~", message)[1:]
        result = []

        for event in events:
            if event.startswith("~h~"):
                result.append({
                    "type": "ping",
                    "data": f"~m~{len(event)}~m~{event}"
                })
            else:
                try:
                    parsed = json.loads(event)

                    if "session_id" in parsed:
                        result.append({
                            "type": "session",
                            "data": parsed
                        })
                    else:
                        result.append({
                            "type": "event",
                            "data": parsed
                        })
                except json.JSONDecodeError:
                    print(f"Failed to parse message: {event}")

        return result

    def _notify_subscribers(self, event: TradingviewEvent):
        """Notify all subscribers of an event"""
        handlers_to_remove = []

        for handler in self.subscribers:
            try:
                # If handler returns True, it will be removed
                if handler(event):
                    handlers_to_remove.append(handler)
            except Exception as e:
                print(f"Error in event handler: {e}")

        # Remove handlers that returned True
        for handler in handlers_to_remove:
            self.subscribers.discard(handler)

    def _add_event_handler(self, handler: Subscriber):
        """Add an event handler"""
        self.subscribers.add(handler)

    def subscribe(self, handler: Subscriber) -> Unsubscriber:
        """Subscribe to events"""
        self.subscribers.add(handler)

        def unsubscribe():
            self.subscribers.discard(handler)

        return unsubscribe

    def send(self, name: str, params: List[Any]) -> None:
        """Send a message to TradingView"""
        if not self.websocket:
            raise RuntimeError("Not connected to TradingView")

        data = json.dumps({"m": name, "p": params})
        message = f"~m~{len(data)}~m~{data}"
        asyncio.create_task(self.websocket.send_str(message))

    async def close(self) -> None:
        """Close the connection to TradingView"""
        if self.websocket:
            await self.websocket.close()

        if self.session:
            await self.session.close()

        if self._message_task:
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                pass

        self.connected = False


async def get_candles(
        client: TradingviewClient,
        symbols: List[str],
        amount: Optional[int] = None,
        timeframe: TradingviewTimeframe = 60
) -> List[Candle]:
    """Get candles for the specified symbols"""
    if not symbols:
        return []

    chart_session = "cs_" + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(12))
    batch_size = amount if amount and amount < MAX_BATCH_SIZE else MAX_BATCH_SIZE

    result_future = asyncio.Future()
    all_candles: List[List[Candle]] = []
    current_sym_index = 0
    symbol = symbols[current_sym_index]
    current_sym_candles = []

    def handle_event(event: TradingviewEvent):
        nonlocal current_sym_index, symbol, current_sym_candles

        # Received new candles
        if event.name == 'timescale_update':
            new_candles = event.params[1]['sds_1']['s']
            if len(new_candles) > batch_size:
                # Sometimes tradingview sends already received candles
                new_candles = new_candles[:len(new_candles) - len(current_sym_candles)]
            current_sym_candles = new_candles + current_sym_candles
            return False

        # Loaded all requested candles
        if event.name in ['series_completed', 'symbol_error']:
            loaded_count = len(current_sym_candles)
            if loaded_count > 0 and loaded_count % batch_size == 0 and (not amount or loaded_count < amount):
                client.send('request_more_data', [chart_session, 'sds_1', batch_size])
                return False

            # Loaded all candles for current symbol
            if amount:
                current_sym_candles = current_sym_candles[:amount]

            candles = [
                Candle(
                    timestamp=c['v'][0],
                    open_price=c['v'][1],
                    high=c['v'][2],
                    low=c['v'][3],
                    close=c['v'][4],
                    volume=c['v'][5]
                )
                for c in current_sym_candles
            ]
            all_candles.append(candles)

            # Next symbol
            if len(symbols) - 1 > current_sym_index:
                current_sym_candles = []
                current_sym_index += 1
                symbol = symbols[current_sym_index]

                client.send('resolve_symbol', [
                    chart_session,
                    f"sds_sym_{current_sym_index}",
                    '=' + json.dumps({"symbol": symbol, "adjustment": "splits"})
                ])

                client.send('modify_series', [
                    chart_session,
                    'sds_1',
                    f"s{current_sym_index}",
                    f"sds_sym_{current_sym_index}",
                    str(timeframe),
                    ''
                ])
                return False

            # All symbols loaded
            result_future.set_result(all_candles[0] if all_candles else [])
            return True  # Remove this handler

        return False

    client._add_event_handler(handle_event)

    client.send('chart_create_session', [chart_session, ''])
    client.send('resolve_symbol', [
        chart_session,
        "sds_sym_0",
        '=' + json.dumps({"symbol": symbol, "adjustment": "splits"})
    ])
    client.send('create_series', [
        chart_session, 'sds_1', 's0', 'sds_sym_0', str(timeframe), batch_size, ''
    ])

    return await result_future
