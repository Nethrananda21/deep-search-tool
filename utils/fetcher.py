"""
Optimized Asynchronous HTTP fetcher
Key optimizations:
1. Retry logic with exponential backoff
2. Response caching for repeated requests
3. Faster timeout handling
4. Semaphore for rate limiting
"""
import asyncio
import aiohttp
import hashlib
from typing import Optional, Dict, Any, List
from config import config


class AsyncFetcher:
    """Optimized async HTTP client"""
    
    # Simple in-memory cache for recent requests
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
    
    def _get_cache_key(self, url: str, params: Dict = None) -> str:
        """Generate cache key from URL and params"""
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
        """Fetch a single URL with retry logic"""
        
        # Check cache first
        if use_cache:
            cache_key = self._get_cache_key(url, params)
            if cache_key in AsyncFetcher._cache:
                return AsyncFetcher._cache[cache_key]
        
        async with self._semaphore:
            for attempt in range(retry_count + 1):
                try:
                    timeout = aiohttp.ClientTimeout(total=self.timeout)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        merged_headers = {**self.headers, **(headers or {})}
                        async with session.request(
                            method, url, 
                            params=params, 
                            headers=merged_headers,
                            ssl=False
                        ) as response:
                            if response.status == 200:
                                if json_response:
                                    result = await response.json()
                                else:
                                    result = await response.text()
                                
                                # Cache successful responses
                                if use_cache and result:
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


# Singleton instance
fetcher = AsyncFetcher()
