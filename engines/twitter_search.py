"""
Twitter Search Engine - Scrapes Twitter/X for sentiment analysis
Uses Nitter (open-source Twitter frontend) - no API keys needed
"""
import asyncio
import re
from typing import List
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from utils.fetcher import AsyncFetcher
from utils.models import TwitterResult
from config import config


class TwitterSearch:
    """Twitter search engine using Nitter instances"""
    
    # Nitter instances (public Twitter frontends)
    NITTER_INSTANCES = [
        "https://nitter.net",
        "https://nitter.cz",
        "https://nitter.privacydev.net",
    ]
    
    def __init__(self):
        self.fetcher = AsyncFetcher()
    
    async def search(self, query: str, max_results: int = 10) -> List[TwitterResult]:
        """
        Search Twitter for tweets matching the query
        Uses Nitter instances with DuckDuckGo fallback
        """
        results = []
        
        # Strategy 1: Try Nitter instances
        for instance in self.NITTER_INSTANCES:
            try:
                nitter_results = await self._search_nitter(instance, query, max_results)
                if nitter_results:
                    results.extend(nitter_results)
                    break  # Success, no need to try other instances
            except Exception as e:
                print(f"Nitter instance {instance} failed: {e}")
                continue
        
        # Strategy 2: Fallback to DuckDuckGo if Nitter fails
        if not results:
            ddg_results = await self._search_via_duckduckgo(query, max_results)
            results.extend(ddg_results)
        
        # Calculate relevance scores
        results = self._calculate_relevance(results, query)
        
        # Sort by relevance and return
        results.sort(key=lambda x: x.relevance, reverse=True)
        return results[:max_results]
    
    async def _search_nitter(self, instance: str, query: str, limit: int = 10) -> List[TwitterResult]:
        """Search using a Nitter instance"""
        results = []
        encoded_query = quote_plus(query)
        url = f"{instance}/search?f=tweets&q={encoded_query}"
        
        try:
            html = await self.fetcher.fetch(url)
            if html:
                soup = BeautifulSoup(html, 'lxml')
                
                # Parse tweet containers
                for tweet in soup.select('.timeline-item')[:limit]:
                    try:
                        # Author
                        author_elem = tweet.select_one('.username')
                        author = author_elem.get_text(strip=True) if author_elem else ""
                        
                        # Tweet text
                        text_elem = tweet.select_one('.tweet-content')
                        text = text_elem.get_text(strip=True) if text_elem else ""
                        
                        # Skip if no text
                        if not text:
                            continue
                        
                        # Tweet URL
                        link_elem = tweet.select_one('.tweet-link')
                        tweet_path = link_elem.get('href', '') if link_elem else ""
                        tweet_url = f"https://twitter.com{tweet_path}" if tweet_path else ""
                        
                        # Stats
                        stats = tweet.select('.tweet-stat')
                        likes = 0
                        retweets = 0
                        replies = 0
                        
                        for stat in stats:
                            stat_text = stat.get_text(strip=True)
                            icon = stat.select_one('.icon-heart, .icon-retweet, .icon-comment')
                            if icon:
                                icon_class = ' '.join(icon.get('class', []))
                                try:
                                    value = int(re.sub(r'[^\d]', '', stat_text) or 0)
                                except:
                                    value = 0
                                
                                if 'heart' in icon_class:
                                    likes = value
                                elif 'retweet' in icon_class:
                                    retweets = value
                                elif 'comment' in icon_class:
                                    replies = value
                        
                        # Timestamp
                        time_elem = tweet.select_one('.tweet-date a')
                        timestamp = time_elem.get('title', '') if time_elem else ""
                        
                        results.append(TwitterResult(
                            text=text[:500],  # Limit text for processing
                            author=author,
                            url=tweet_url,
                            likes=likes,
                            retweets=retweets,
                            replies=replies,
                            timestamp=timestamp
                        ))
                        
                    except Exception as e:
                        continue
                        
        except Exception as e:
            print(f"Nitter search error: {e}")
        
        return results
    
    async def _search_via_duckduckgo(self, query: str, limit: int = 10) -> List[TwitterResult]:
        """Fallback: Search Twitter via DuckDuckGo"""
        results = []
        search_query = f"site:twitter.com {query}"
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
                        
                        # Only include twitter.com links
                        if 'twitter.com' in link.lower() or 'x.com' in link.lower():
                            # Extract username from URL
                            author_match = re.search(r'(?:twitter|x)\.com/(\w+)', link)
                            author = f"@{author_match.group(1)}" if author_match else ""
                            
                            # Use snippet as tweet text
                            text = snippet_elem.get_text(strip=True) if snippet_elem else ""
                            
                            results.append(TwitterResult(
                                text=text[:500],
                                author=author,
                                url=link,
                                likes=0,  # Not available from DuckDuckGo
                                retweets=0,
                                replies=0,
                                timestamp=""
                            ))
        except Exception as e:
            print(f"DuckDuckGo Twitter search error: {e}")
        
        return results
    
    def _calculate_relevance(self, results: List[TwitterResult], query: str) -> List[TwitterResult]:
        """Calculate relevance score for sentiment analysis priority"""
        query_terms = set(query.lower().split())
        
        for result in results:
            score = 0.0
            
            # Text relevance (60%) - most important for sentiment analysis
            text_terms = set(result.text.lower().split())
            text_overlap = len(query_terms & text_terms) / len(query_terms) if query_terms else 0
            score += text_overlap * 0.6
            
            # Engagement score (30%) - popular tweets have more impact
            engagement = result.likes + (result.retweets * 2)
            if engagement > 0:
                import math
                score += min(math.log10(engagement + 1) / 5, 0.3)
            
            # Has author boost (10%)
            if result.author:
                score += 0.1
            
            result.relevance = min(score, 1.0)
        
        return results


# Factory function
def create_twitter_search() -> TwitterSearch:
    return TwitterSearch()
