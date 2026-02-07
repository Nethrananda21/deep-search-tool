"""
Pump.fun Token Monitor
Monitors new token launches on Pump.fun via PumpPortal WebSocket API
"""
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
import aiohttp


@dataclass
class NewToken:
    """Represents a newly launched token on Pump.fun"""
    mint: str  # Token mint address
    name: str
    symbol: str
    uri: str  # Metadata URI
    timestamp: datetime
    initial_buy: Optional[float] = None
    market_cap: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "mint": self.mint,
            "name": self.name,
            "symbol": self.symbol,
            "uri": self.uri,
            "timestamp": self.timestamp.isoformat(),
            "initial_buy": self.initial_buy,
            "market_cap": self.market_cap
        }
    
    def get_searchable_terms(self) -> List[str]:
        """Get terms that could match Twitter trends"""
        terms = []
        
        # Token name (split into words)
        if self.name:
            terms.extend(self.name.lower().split())
            terms.append(self.name.lower())
        
        # Token symbol
        if self.symbol:
            terms.append(self.symbol.lower())
            terms.append(f"${self.symbol.lower()}")
        
        return [t for t in terms if len(t) >= 2]


class PumpFunMonitor:
    """
    Monitors Pump.fun for new token launches via PumpPortal WebSocket
    
    WebSocket endpoint: wss://pumpportal.fun/api/data
    Subscribe method: {"method": "subscribeNewToken"}
    """
    
    WEBSOCKET_URL = "wss://pumpportal.fun/api/data"
    
    def __init__(
        self,
        on_new_token: Optional[Callable[[NewToken], None]] = None
    ):
        self.on_new_token = on_new_token
        self.is_running = False
        self.recent_tokens: List[NewToken] = []
        self.max_history = 100  # Keep last 100 tokens
        self._ws = None
        self._reconnect_delay = 5
    
    async def connect_and_subscribe(self):
        """Connect to WebSocket and subscribe to new tokens"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.WEBSOCKET_URL) as ws:
                    self._ws = ws
                    print("✅ Connected to PumpPortal WebSocket")
                    
                    # Subscribe to new token events
                    subscribe_msg = json.dumps({"method": "subscribeNewToken"})
                    await ws.send_str(subscribe_msg)
                    print("📡 Subscribed to new token events")
                    
                    # Listen for messages
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            print(f"WebSocket error: {ws.exception()}")
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            print("WebSocket closed")
                            break
                            
        except aiohttp.ClientError as e:
            print(f"Connection error: {e}")
        except Exception as e:
            print(f"WebSocket error: {e}")
    
    async def _handle_message(self, data: str):
        """Handle incoming WebSocket message"""
        try:
            msg = json.loads(data)
            
            # Check if it's a new token event
            if isinstance(msg, dict) and 'mint' in msg:
                token = NewToken(
                    mint=msg.get('mint', ''),
                    name=msg.get('name', ''),
                    symbol=msg.get('symbol', ''),
                    uri=msg.get('uri', ''),
                    timestamp=datetime.now(),
                    initial_buy=msg.get('initialBuy'),
                    market_cap=msg.get('marketCap')
                )
                
                # Add to history
                self.recent_tokens.append(token)
                if len(self.recent_tokens) > self.max_history:
                    self.recent_tokens.pop(0)
                
                # Callback
                if self.on_new_token:
                    self.on_new_token(token)
                
                # Log
                print(f"🆕 New token: {token.name} (${token.symbol}) - {token.mint[:8]}...")
                
        except json.JSONDecodeError:
            pass  # Ignore non-JSON messages
        except Exception as e:
            print(f"Error handling message: {e}")
    
    async def start_monitoring(self):
        """Start continuous monitoring with auto-reconnect"""
        self.is_running = True
        print("🚀 Starting Pump.fun token monitoring...")
        
        while self.is_running:
            try:
                await self.connect_and_subscribe()
            except Exception as e:
                print(f"Monitor error: {e}")
            
            if self.is_running:
                print(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
        
        print("Pump.fun monitoring stopped")
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.is_running = False
        if self._ws:
            asyncio.create_task(self._ws.close())
    
    def get_recent_tokens(self, hours: int = 24) -> List[NewToken]:
        """Get tokens launched in the last N hours"""
        cutoff = datetime.now() - __import__('datetime').timedelta(hours=hours)
        return [t for t in self.recent_tokens if t.timestamp > cutoff]
    
    def search_tokens(self, keyword: str) -> List[NewToken]:
        """Search recent tokens by name or symbol"""
        keyword = keyword.lower().strip()
        matches = []
        
        for token in self.recent_tokens:
            terms = token.get_searchable_terms()
            if any(keyword in term or term in keyword for term in terms):
                matches.append(token)
        
        return matches


class PumpFunScraper:
    """
    Fallback: Scrape Pump.fun website for new tokens
    Use this if WebSocket is unavailable
    """
    
    PUMPFUN_URL = "https://pump.fun"
    
    def __init__(self):
        from utils.fetcher import AsyncFetcher
        self.fetcher = AsyncFetcher()
    
    async def get_new_tokens(self, limit: int = 20) -> List[NewToken]:
        """Scrape recently launched tokens from pump.fun"""
        tokens = []
        
        try:
            # Try the API endpoint if available
            api_url = f"{self.PUMPFUN_URL}/api/tokens?sort=created&limit={limit}"
            
            response = await self.fetcher.fetch(api_url, json_response=True)
            
            if response and isinstance(response, list):
                for item in response[:limit]:
                    token = NewToken(
                        mint=item.get('mint', ''),
                        name=item.get('name', ''),
                        symbol=item.get('symbol', ''),
                        uri=item.get('uri', ''),
                        timestamp=datetime.now(),
                        market_cap=item.get('marketCap')
                    )
                    tokens.append(token)
                    
        except Exception as e:
            print(f"Scraper error: {e}")
        
        return tokens


# Factory functions
def create_pumpfun_monitor(**kwargs) -> PumpFunMonitor:
    return PumpFunMonitor(**kwargs)

def create_pumpfun_scraper() -> PumpFunScraper:
    return PumpFunScraper()
