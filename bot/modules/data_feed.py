"""
Data feed module for Hyperliquid API integration
Handles market data, orderbook, and account information
"""

import time
import requests
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque
import json


class HyperliquidDataFeed:
    """Data feed for Hyperliquid exchange"""

    def __init__(self, config, logger):
        """
        Initialize Hyperliquid data feed

        Args:
            config: Configuration object
            logger: Logger instance
        """
        self.config = config
        self.logger = logger

        # API endpoints
        if config.TESTNET:
            self.base_url = "https://api.hyperliquid-testnet.xyz"
        else:
            self.base_url = "https://api.hyperliquid.xyz"

        self.info_url = f"{self.base_url}/info"
        self.exchange_url = f"{self.base_url}/exchange"

        # API credentials
        self.api_key = config.HYPERLIQUID_API_KEY
        self.secret_key = config.HYPERLIQUID_SECRET_KEY
        self.wallet_address = config.HYPERLIQUID_WALLET_ADDRESS

        # Cache for market data
        self.candle_cache: Dict[str, deque] = {}
        self.last_update: Dict[str, datetime] = {}

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

    def _make_request(self, endpoint: str, method: str = 'POST', data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make an HTTP request to Hyperliquid API

        Args:
            endpoint: API endpoint URL
            method: HTTP method (GET or POST)
            data: Request payload

        Returns:
            Response data or None on error
        """
        try:
            if method == 'POST':
                response = self.session.post(endpoint, json=data, timeout=10)
            else:
                response = self.session.get(endpoint, params=data, timeout=10)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            self.logger.log_error(e, context=f"API request to {endpoint}")
            return None

    def get_candles(self, pair: str, interval: str = '1m', limit: int = 300) -> Optional[List[Dict[str, Any]]]:
        """
        Get historical candle data

        Args:
            pair: Trading pair (e.g., 'HYPE/USDC')
            interval: Candle interval ('1m', '5m', '15m', '1h', etc.)
            limit: Number of candles to fetch

        Returns:
            List of candle dictionaries or None on error
        """
        # Convert pair format (HYPE/USDC -> HYPE-USDC for Hyperliquid)
        symbol = pair.replace('/', '-')

        # Map interval to Hyperliquid format
        interval_map = {
            '1m': '1',
            '5m': '5',
            '15m': '15',
            '1h': '60',
            '4h': '240',
            '1d': '1D'
        }

        hl_interval = interval_map.get(interval, '1')

        payload = {
            'type': 'candleSnapshot',
            'req': {
                'coin': symbol.split('-')[0],  # Base currency
                'interval': hl_interval,
                'startTime': int((datetime.now() - timedelta(minutes=limit * int(hl_interval))).timestamp() * 1000),
                'endTime': int(datetime.now().timestamp() * 1000)
            }
        }

        response = self._make_request(self.info_url, method='POST', data=payload)

        if not response:
            return None

        # Parse candles
        candles = []
        for candle in response:
            candles.append({
                'timestamp': candle['t'],
                'open': float(candle['o']),
                'high': float(candle['h']),
                'low': float(candle['l']),
                'close': float(candle['c']),
                'volume': float(candle['v'])
            })

        return candles

    def get_latest_candle(self, pair: str, interval: str = '1m') -> Optional[Dict[str, Any]]:
        """
        Get the most recent closed candle

        Args:
            pair: Trading pair
            interval: Candle interval

        Returns:
            Latest candle dictionary or None
        """
        candles = self.get_candles(pair, interval, limit=2)
        if candles and len(candles) >= 2:
            # Return the second-to-last candle (last closed candle)
            return candles[-2]
        return None

    def get_orderbook(self, pair: str) -> Optional[Dict[str, Any]]:
        """
        Get current orderbook (L2 data)

        Args:
            pair: Trading pair

        Returns:
            Dictionary with best_bid, best_ask, mid_price, spread
        """
        symbol = pair.replace('/', '-')

        payload = {
            'type': 'l2Book',
            'coin': symbol.split('-')[0]
        }

        response = self._make_request(self.info_url, method='POST', data=payload)

        if not response or 'levels' not in response:
            return None

        try:
            bids = response['levels'][0]  # Bids
            asks = response['levels'][1]  # Asks

            if not bids or not asks:
                return None

            best_bid = float(bids[0]['px'])
            best_ask = float(asks[0]['px'])
            mid_price = (best_bid + best_ask) / 2
            spread = (best_ask - best_bid) / mid_price

            return {
                'best_bid': best_bid,
                'best_ask': best_ask,
                'mid_price': mid_price,
                'spread': spread,
                'bid_size': float(bids[0]['sz']),
                'ask_size': float(asks[0]['sz'])
            }

        except (IndexError, KeyError, ValueError) as e:
            self.logger.log_error(e, context=f"Parsing orderbook for {pair}")
            return None

    def get_account_state(self) -> Optional[Dict[str, Any]]:
        """
        Get current account state (equity, margin, positions)

        Returns:
            Dictionary with account information
        """
        if self.config.DRY_RUN:
            # Return simulated account state for dry run
            return {
                'equity': 10000.0,  # Starting with 10k USDC
                'margin_used': 0.0,
                'margin_available': 10000.0,
                'unrealized_pnl': 0.0,
                'positions': []
            }

        payload = {
            'type': 'clearinghouseState',
            'user': self.wallet_address
        }

        response = self._make_request(self.info_url, method='POST', data=payload)

        if not response:
            return None

        try:
            equity = float(response['marginSummary']['accountValue'])
            margin_used = float(response['marginSummary']['totalMarginUsed'])
            unrealized_pnl = float(response['marginSummary']['totalNtlPos'])

            positions = []
            for pos in response.get('assetPositions', []):
                if float(pos['position']['szi']) != 0:  # Only open positions
                    positions.append({
                        'coin': pos['position']['coin'],
                        'size': float(pos['position']['szi']),
                        'entry_price': float(pos['position']['entryPx']),
                        'unrealized_pnl': float(pos['position']['unrealizedPnl']),
                        'leverage': float(pos['position']['leverage']['value'])
                    })

            return {
                'equity': equity,
                'margin_used': margin_used,
                'margin_available': equity - margin_used,
                'unrealized_pnl': unrealized_pnl,
                'positions': positions
            }

        except (KeyError, ValueError) as e:
            self.logger.log_error(e, context="Parsing account state")
            return None

    def get_current_position(self, pair: str) -> Optional[Dict[str, Any]]:
        """
        Get current position for a specific pair

        Args:
            pair: Trading pair

        Returns:
            Position dictionary or None if no position
        """
        account_state = self.get_account_state()

        if not account_state:
            return None

        symbol = pair.split('/')[0]  # Get base currency

        for position in account_state['positions']:
            if position['coin'] == symbol:
                return position

        return None

    def get_ticker(self, pair: str) -> Optional[Dict[str, Any]]:
        """
        Get current ticker information

        Args:
            pair: Trading pair

        Returns:
            Dictionary with price and volume info
        """
        symbol = pair.replace('/', '-')

        payload = {
            'type': 'metaAndAssetCtxs'
        }

        response = self._make_request(self.info_url, method='POST', data=payload)

        if not response:
            return None

        try:
            # Find the asset in the response
            for asset in response[1]:  # assetCtxs is at index 1
                if asset['coin'] == symbol.split('-')[0]:
                    return {
                        'last_price': float(asset['markPx']),
                        'funding_rate': float(asset['funding']),
                        'open_interest': float(asset['openInterest']),
                        'volume_24h': float(asset.get('dayNtlVlm', 0))
                    }

        except (IndexError, KeyError, ValueError) as e:
            self.logger.log_error(e, context=f"Parsing ticker for {pair}")

        return None

    def validate_connection(self) -> bool:
        """
        Validate connection to Hyperliquid API

        Returns:
            bool: True if connection is successful
        """
        try:
            payload = {'type': 'metaAndAssetCtxs'}
            response = self._make_request(self.info_url, method='POST', data=payload)
            return response is not None

        except Exception as e:
            self.logger.log_error(e, context="Validating API connection")
            return False

    def get_market_info(self, pair: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive market information for a pair

        Args:
            pair: Trading pair

        Returns:
            Dictionary with market info (orderbook, ticker, latest candle)
        """
        orderbook = self.get_orderbook(pair)
        ticker = self.get_ticker(pair)
        latest_candle = self.get_latest_candle(pair, '1m')

        if not all([orderbook, ticker, latest_candle]):
            return None

        return {
            'pair': pair,
            'timestamp': datetime.now().isoformat(),
            'orderbook': orderbook,
            'ticker': ticker,
            'latest_candle': latest_candle
        }

    def stream_candles(self, pair: str, interval: str = '1m') -> Dict[str, Any]:
        """
        Simulate streaming candles by polling at regular intervals
        In a production environment, this would use WebSocket

        Args:
            pair: Trading pair
            interval: Candle interval

        Returns:
            Latest candle data
        """
        # Check if we need to update (don't poll too frequently)
        cache_key = f"{pair}_{interval}"
        now = datetime.now()

        if cache_key in self.last_update:
            time_since_update = (now - self.last_update[cache_key]).seconds
            if time_since_update < 5:  # Don't update more than once per 5 seconds
                return None

        candle = self.get_latest_candle(pair, interval)

        if candle:
            self.last_update[cache_key] = now

        return candle


class SimulatedDataFeed(HyperliquidDataFeed):
    """
    Simulated data feed for testing without live API connection
    """

    def __init__(self, config, logger):
        """Initialize simulated data feed"""
        super().__init__(config, logger)
        self.current_price = {'HYPE/USDC': 25.0, 'ZEC/USDC': 45.0}
        self.candle_counter = 0

    def get_candles(self, pair: str, interval: str = '1m', limit: int = 300) -> Optional[List[Dict[str, Any]]]:
        """Generate simulated candle data"""
        import random

        base_price = self.current_price.get(pair, 100.0)
        candles = []

        for i in range(limit):
            # Simulate price movement
            change = random.uniform(-0.02, 0.02)  # ±2% change
            open_price = base_price
            close_price = base_price * (1 + change)
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.01)
            low_price = min(open_price, close_price) * random.uniform(0.99, 1.0)
            volume = random.uniform(100000, 500000)

            candles.append({
                'timestamp': int((datetime.now() - timedelta(minutes=limit - i)).timestamp() * 1000),
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })

            base_price = close_price

        # Update current price
        self.current_price[pair] = candles[-1]['close']

        return candles

    def get_orderbook(self, pair: str) -> Optional[Dict[str, Any]]:
        """Generate simulated orderbook"""
        price = self.current_price.get(pair, 100.0)
        spread_pct = 0.001  # 0.1% spread

        best_bid = price * (1 - spread_pct / 2)
        best_ask = price * (1 + spread_pct / 2)
        mid_price = (best_bid + best_ask) / 2
        spread = (best_ask - best_bid) / mid_price

        return {
            'best_bid': best_bid,
            'best_ask': best_ask,
            'mid_price': mid_price,
            'spread': spread,
            'bid_size': 10000.0,
            'ask_size': 10000.0
        }

    def validate_connection(self) -> bool:
        """Always return True for simulated feed"""
        return True
