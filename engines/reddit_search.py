"""
Reddit Search Engine - Searches Reddit for solutions
Uses Reddit's public JSON API (no authentication required)
"""
import asyncio
import re
from typing import List, Optional
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from utils.fetcher import AsyncFetcher
from utils.models import RedditResult
from config import config


class RedditSearch:
    """Reddit search engine using public JSON endpoints"""
    
    def __init__(self):
        self.fetcher = AsyncFetcher()
        self.base_url = "https://www.reddit.com"
    
    async def search(self, query: str, max_results: int = 10) -> List[RedditResult]:
        """
        Search Reddit for posts matching the query
        Uses multiple strategies for comprehensive results
        """
        results = []
        
        # Strategy 1: Reddit's native search API (JSON)
        reddit_results = await self._search_reddit_json(query, max_results)
        results.extend(reddit_results)
        
        # Strategy 2: Google search for Reddit (backup)
        if len(results) < max_results:
            google_results = await self._search_via_google(query, max_results - len(results))
            # Avoid duplicates
            existing_urls = {r.url for r in results}
            for r in google_results:
                if r.url not in existing_urls:
                    results.append(r)
        
        # Calculate relevance scores
        results = self._calculate_relevance(results, query)
        
        # Sort by relevance and return top results
        results.sort(key=lambda x: x.relevance, reverse=True)
        return results[:max_results]
    
    async def _search_reddit_json(self, query: str, limit: int = 25) -> List[RedditResult]:
        """Search using Reddit's JSON API"""
        results = []
        encoded_query = quote_plus(query)
        
        # Search across Reddit
        url = f"{self.base_url}/search.json"
        params = {
            "q": query,
            "sort": "relevance",
            "limit": min(limit, 100),
            "type": "link"
        }
        
        try:
            response = await self.fetcher.fetch(
                f"{url}?q={encoded_query}&sort=relevance&limit={limit}&type=link",
                json_response=True
            )
            
            if response and "data" in response:
                for post in response["data"].get("children", []):
                    data = post.get("data", {})
                    if data:
                        result = RedditResult(
                            title=data.get("title", ""),
                            url=f"https://reddit.com{data.get('permalink', '')}",
                            subreddit=f"r/{data.get('subreddit', '')}",
                            score=data.get("score", 0),
                            num_comments=data.get("num_comments", 0),
                            snippet=data.get("selftext", "")[:300] if data.get("selftext") else "",
                            author=data.get("author", ""),
                            created=str(data.get("created_utc", ""))
                        )
                        results.append(result)
        except Exception as e:
            print(f"Reddit JSON search error: {e}")
        
        return results
    
    async def _search_via_google(self, query: str, limit: int = 10) -> List[RedditResult]:
        """Fallback: Search Reddit via DuckDuckGo"""
        results = []
        search_query = f"site:reddit.com {query}"
        encoded = quote_plus(search_query)
        
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        
        try:
            html = await self.fetcher.fetch(url)
            if html:
                soup = BeautifulSoup(html, 'lxml')
                
                for result in soup.select('.result')[:limit]:
                    title_elem = result.select_one('.result__title a')
                    snippet_elem = result.select_one('.result__snippet')
                    
                    if title_elem:
                        url = title_elem.get('href', '')
                        # Extract actual URL from DuckDuckGo redirect
                        if 'reddit.com' in url:
                            # Parse subreddit from URL
                            subreddit_match = re.search(r'/r/(\w+)/', url)
                            subreddit = f"r/{subreddit_match.group(1)}" if subreddit_match else "r/unknown"
                            
                            results.append(RedditResult(
                                title=title_elem.get_text(strip=True),
                                url=url,
                                subreddit=subreddit,
                                snippet=snippet_elem.get_text(strip=True) if snippet_elem else "",
                            ))
        except Exception as e:
            print(f"DuckDuckGo Reddit search error: {e}")
        
        return results
    
    def _calculate_relevance(self, results: List[RedditResult], query: str) -> List[RedditResult]:
        """Calculate relevance score based on multiple factors"""
        query_terms = set(query.lower().split())
        
        for result in results:
            score = 0.0
            
            # Title relevance (40%)
            title_terms = set(result.title.lower().split())
            title_overlap = len(query_terms & title_terms) / len(query_terms) if query_terms else 0
            score += title_overlap * 0.4
            
            # Snippet relevance (30%)
            snippet_terms = set(result.snippet.lower().split())
            snippet_overlap = len(query_terms & snippet_terms) / len(query_terms) if query_terms else 0
            score += snippet_overlap * 0.3
            
            # Engagement score (20%) - normalized log scale
            engagement = result.score + (result.num_comments * 2)
            if engagement > 0:
                import math
                score += min(math.log10(engagement + 1) / 5, 0.2)
            
            # Subreddit relevance boost (10%)
            tech_subreddits = {'techsupport', 'programming', 'learnprogramming', 'buildapc', 
                             'sysadmin', 'python', 'javascript', 'webdev', 'linux', 'windows'}
            sub_name = result.subreddit.replace('r/', '').lower()
            if sub_name in tech_subreddits:
                score += 0.1
            
            result.relevance = min(score, 1.0)
        
        return results


# Factory function
def create_reddit_search() -> RedditSearch:
    return RedditSearch()
