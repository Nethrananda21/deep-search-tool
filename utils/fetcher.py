"""
Optimized Asynchronous HTTP fetcher with Session Reuse
Key optimizations:
1. TCP Connection Pooling via session reuse
2. Retry logic with exponential backoff
3. Response caching for repeated requests
4. Semaphore for rate limiting
"""
import asyncio
import aiohttp
import hashlib
from typing import Optional, Dict, Any, List
from config import config


class AsyncFetcher:
    """Optimized async HTTP client with session reuse"""
    
    # Class-level shared session for connection pooling
    _session: Optional[aiohttp.ClientSession] = None
    _session_lock = asyncio.Lock()
    
    # Simple in-memory cache
    _cache: Dict[str, Any] = {}
    _cache_max_size = 100
    
    def __init__(self, timeout: int = None, max_concurrent: int = None):
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.max_concurrent = max_concurrent or config.MAX_CONCURRENT_REQUESTS
        self.headers = {
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a reusable session with connection pooling"""
        if AsyncFetcher._session is None or AsyncFetcher._session.closed:
            async with AsyncFetcher._session_lock:
                if AsyncFetcher._session is None or AsyncFetcher._session.closed:
                    # TCP Connection pooling settings
                    connector = aiohttp.TCPConnector(
                        limit=self.max_concurrent,
                        limit_per_host=5,
                        ttl_dns_cache=300,
                        use_dns_cache=True,
                        ssl=False
                    )
                    timeout = aiohttp.ClientTimeout(total=self.timeout)
                    AsyncFetcher._session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers=self.headers
                    )
        return AsyncFetcher._session
    
    def _get_cache_key(self, url: str, params: Dict = None) -> str:
        """Generate cache key"""
        key = url + str(sorted(params.items()) if params else "")
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    async def fetch(
        self, 
        url: str, 
        method: str = "GET",
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        json_response: bool = False,
        use_cache: bool = False,
        retry_count: int = 2
    ) -> Optional[Any]:
        """Fetch URL with session reuse and retry logic"""
        
        # Check cache first
        cache_key = None
        if use_cache:
            cache_key = self._get_cache_key(url, params)
            if cache_key in AsyncFetcher._cache:
                return AsyncFetcher._cache[cache_key]
        
        async with self._semaphore:
            session = await self._get_session()
            
            for attempt in range(retry_count + 1):
                try:
                    merged_headers = {**self.headers, **(headers or {})}
                    async with session.request(
                        method, url, 
                        params=params, 
                        headers=merged_headers
                    ) as response:
                        if response.status == 200:
                            if json_response:
                                result = await response.json()
                            else:
                                result = await response.text()
                            
                            # Cache successful responses
                            if use_cache and result and cache_key:
                                if len(AsyncFetcher._cache) > self._cache_max_size:
                                    AsyncFetcher._cache = dict(list(AsyncFetcher._cache.items())[-50:])
                                AsyncFetcher._cache[cache_key] = result
                            
                            return result
                        elif response.status == 429:
                            await asyncio.sleep(1 * (attempt + 1))
                            continue
                        return None
                        
                except asyncio.TimeoutError:
                    if attempt < retry_count:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    return None
                except aiohttp.ClientError:
                    if attempt < retry_count:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    return None
                except Exception:
                    return None
        
        return None
    
    async def fetch_many(
        self, 
        urls: List[str], 
        json_response: bool = False
    ) -> List[Optional[Any]]:
        """Fetch multiple URLs concurrently"""
        tasks = [self.fetch(url, json_response=json_response) for url in urls]
        return await asyncio.gather(*tasks)
    
    async def fetch_json(self, url: str, params: Dict[str, Any] = None) -> Optional[dict]:
        """Fetch JSON response"""
        return await self.fetch(url, params=params, json_response=True)
    
    @classmethod
    async def close(cls):
        """Close the shared session"""
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None


# Singleton instance
fetcher = AsyncFetcher()
