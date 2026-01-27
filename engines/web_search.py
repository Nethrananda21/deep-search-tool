"""
Web/Forum Search Engine - Searches forums, repair sites, articles
Optimized for finding REPAIR and FIX solutions
"""
import asyncio
from typing import List
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from utils.fetcher import AsyncFetcher
from utils.models import ForumResult
from config import config


class WebSearch:
    """Web search engine for forums and articles - repair focused"""
    
    # Repair-focused sites (prioritized)
    REPAIR_SITES = [
        "ifixit.com",
        "reddit.com",  # Will be filtered from forums since we have separate Reddit search
    ]
    
    # Tech support sites
    TECH_SITES = [
        "stackoverflow.com",
        "superuser.com",
        "howtogeek.com",
        "makeuseof.com",
        "tomshardware.com",
        "quora.com",
        "answers.microsoft.com",
    ]
    
    def __init__(self):
        self.fetcher = AsyncFetcher()
    
    async def search(self, query: str, max_results: int = 10) -> List[ForumResult]:
        """
        Search forums and tech sites for solutions
        Uses multiple search strategies for better coverage
        """
        all_results = []
        
        # Strategy 1: Direct search (no site restrictions - most relevant)
        direct_results = await self._search_direct(query, max_results)
        all_results.extend(direct_results)
        
        # Strategy 2: iFixit specific search (for repair queries)
        ifixit_results = await self._search_site_specific("ifixit.com", query, 5)
        all_results.extend(ifixit_results)
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)
        
        # Calculate relevance
        unique_results = self._calculate_relevance(unique_results, query)
        
        # Sort and return
        unique_results.sort(key=lambda x: x.relevance, reverse=True)
        return unique_results[:max_results]
    
    async def _search_direct(self, query: str, limit: int = 10) -> List[ForumResult]:
        """Direct DuckDuckGo search - no site restrictions for best relevance"""
        results = []
        
        # Add "fix" or "repair" to query if not present for better results
        enhanced_query = query
        query_lower = query.lower()
        if not any(word in query_lower for word in ["fix", "repair", "solve", "solution", "how to"]):
            enhanced_query = f"how to fix {query}"
        
        encoded = quote_plus(enhanced_query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        
        try:
            html = await self.fetcher.fetch(url)
            if html:
                soup = BeautifulSoup(html, 'lxml')
                
                for result in soup.select('.result')[:limit * 2]:  # Get more, filter later
                    title_elem = result.select_one('.result__title a')
                    snippet_elem = result.select_one('.result__snippet')
                    
                    if title_elem:
                        link = title_elem.get('href', '')
                        
                        # Skip Reddit (we have dedicated Reddit search)
                        if 'reddit.com' in link.lower():
                            continue
                        
                        source = self._extract_source(link)
                        
                        results.append(ForumResult(
                            title=title_elem.get_text(strip=True),
                            url=link,
                            source=source,
                            snippet=snippet_elem.get_text(strip=True) if snippet_elem else ""
                        ))
                        
                        if len(results) >= limit:
                            break
        except Exception as e:
            print(f"DuckDuckGo direct search error: {e}")
        
        return results
    
    async def _search_site_specific(self, site: str, query: str, limit: int = 5) -> List[ForumResult]:
        """Search a specific site via DuckDuckGo"""
        results = []
        
        search_query = f"site:{site} {query}"
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
                        link = title_elem.get('href', '')
                        source = self._extract_source(link)
                        
                        results.append(ForumResult(
                            title=title_elem.get_text(strip=True),
                            url=link,
                            source=source,
                            snippet=snippet_elem.get_text(strip=True) if snippet_elem else ""
                        ))
        except Exception as e:
            print(f"Site-specific search error for {site}: {e}")
        
        return results
    
    def _extract_source(self, url: str) -> str:
        """Extract source name from URL"""
        source_map = {
            "stackoverflow.com": "Stack Overflow",
            "superuser.com": "Super User",
            "serverfault.com": "Server Fault",
            "askubuntu.com": "Ask Ubuntu",
            "github.com": "GitHub",
            "howtogeek.com": "How-To Geek",
            "makeuseof.com": "MakeUseOf",
            "tomshardware.com": "Tom's Hardware",
            "quora.com": "Quora",
            "ifixit.com": "iFixit",
            "microsoft.com": "Microsoft",
            "google.com": "Google Support",
        }
        
        for domain, name in source_map.items():
            if domain in url.lower():
                return name
        
        # Extract domain as source
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except:
            return "Web"
    
    def _calculate_relevance(self, results: List[ForumResult], query: str) -> List[ForumResult]:
        """Calculate relevance score"""
        query_terms = set(query.lower().split())
        
        # Priority sources get a boost
        priority_sources = {"Stack Overflow", "Super User", "GitHub", "iFixit"}
        
        for result in results:
            score = 0.0
            
            # Title relevance (50%)
            title_terms = set(result.title.lower().split())
            title_overlap = len(query_terms & title_terms) / len(query_terms) if query_terms else 0
            score += title_overlap * 0.5
            
            # Snippet relevance (30%)
            snippet_terms = set(result.snippet.lower().split())
            snippet_overlap = len(query_terms & snippet_terms) / len(query_terms) if query_terms else 0
            score += snippet_overlap * 0.3
            
            # Source quality boost (20%)
            if result.source in priority_sources:
                score += 0.2
            elif result.source in ["How-To Geek", "MakeUseOf", "Tom's Hardware"]:
                score += 0.15
            else:
                score += 0.05
            
            result.relevance = min(score, 1.0)
        
        return results


# Factory function
def create_web_search() -> WebSearch:
    return WebSearch()
