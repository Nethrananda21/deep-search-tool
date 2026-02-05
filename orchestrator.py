"""
Search Orchestrator - OPTIMIZED for fast, accurate results
Key optimizations:
1. Concurrent execution with timeouts
2. Query preprocessing and expansion
3. Result deduplication and smart ranking
4. Cached engines (singleton pattern)
"""
import asyncio
import time
import re
from typing import List, Dict, Any, Optional
from functools import lru_cache

from engines.reddit_search import create_reddit_search
from engines.web_search import create_web_search
from engines.youtube_search import create_youtube_search
from engines.twitter_search import create_twitter_search
from utils.models import SearchQuery, SearchResults


class QueryOptimizer:
    """Optimizes search queries for better results"""
    
    # Common stop words to filter out
    STOP_WORDS = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 
                  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                  'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                  'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                  'through', 'during', 'before', 'after', 'above', 'below',
                  'between', 'under', 'again', 'further', 'then', 'once', 'my', 'i'}
    
    # Keywords that indicate repair/fix intent
    REPAIR_KEYWORDS = {'fix', 'repair', 'solve', 'solution', 'broken', 'not working',
                       'issue', 'problem', 'error', 'how to', 'help', 'stuck'}
    
    @classmethod
    def optimize(cls, query: str, context: Optional[str] = None) -> str:
        """Optimize query for better search results"""
        # Clean query
        query = query.strip()
        
        # Add context if provided
        if context:
            query = f"{query} {context}"
        
        # Extract key terms (remove stop words for search engines)
        words = query.lower().split()
        key_terms = [w for w in words if w not in cls.STOP_WORDS and len(w) > 2]
        
        # Detect if it's a repair query and enhance
        query_lower = query.lower()
        is_repair_query = any(kw in query_lower for kw in cls.REPAIR_KEYWORDS)
        
        # If no repair intent detected, add "how to fix" for better results
        if not is_repair_query and len(key_terms) >= 2:
            # Check if it seems like a problem description
            problem_indicators = ['not', 'broken', 'stopped', 'wont', "won't", "doesn't", 
                                  'cant', "can't", 'failed', 'error', 'issue']
            if any(ind in query_lower for ind in problem_indicators):
                query = f"how to fix {query}"
        
        return query
    
    @classmethod
    def extract_product_terms(cls, query: str) -> List[str]:
        """Extract product/brand names for better targeting"""
        # Common brand patterns
        brands = []
        
        # Look for capitalized words (likely brand names)
        words = query.split()
        for word in words:
            if word[0].isupper() and len(word) > 2:
                brands.append(word.lower())
        
        return brands


class ResultRanker:
    """Smart ranking of search results for relevance"""
    
    @classmethod
    def rank_and_dedupe(cls, results: Dict[str, List[dict]], query: str) -> Dict[str, List[dict]]:
        """Rank results by relevance and remove duplicates"""
        query_terms = set(query.lower().split())
        seen_titles = set()
        
        for source, items in results.items():
            unique_items = []
            
            for item in items:
                # Deduplication by title similarity
                title = item.get('title', '').lower()
                title_key = cls._normalize_title(title)
                
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)
                
                # Boost relevance based on multiple factors
                relevance = item.get('relevance', 0.5)
                
                # Title match boost
                title_terms = set(title.split())
                title_match = len(query_terms & title_terms) / len(query_terms) if query_terms else 0
                relevance = relevance * 0.6 + title_match * 0.4
                
                # Transcript boost for YouTube (if contains query terms)
                if source == 'youtube' and item.get('transcript'):
                    transcript_lower = item['transcript'].lower()
                    transcript_matches = sum(1 for t in query_terms if t in transcript_lower)
                    if transcript_matches > 0:
                        relevance += 0.1 * min(transcript_matches / len(query_terms), 0.3)
                
                item['relevance'] = min(relevance, 1.0)
                unique_items.append(item)
            
            # Sort by relevance
            unique_items.sort(key=lambda x: x.get('relevance', 0), reverse=True)
            results[source] = unique_items
        
        return results
    
    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title for deduplication"""
        # Remove special chars and extra spaces
        title = re.sub(r'[^\w\s]', '', title)
        title = ' '.join(title.split()[:6])  # First 6 words
        return title


class SearchOrchestrator:
    """Orchestrates concurrent searches across all engines - OPTIMIZED"""
    
    # Singleton engines for connection reuse
    _reddit_engine = None
    _web_engine = None
    _youtube_engine = None
    _twitter_engine = None
    
    def __init__(self):
        # Reuse engine instances for connection pooling
        if SearchOrchestrator._reddit_engine is None:
            SearchOrchestrator._reddit_engine = create_reddit_search()
        if SearchOrchestrator._web_engine is None:
            SearchOrchestrator._web_engine = create_web_search()
        if SearchOrchestrator._youtube_engine is None:
            SearchOrchestrator._youtube_engine = create_youtube_search()
        if SearchOrchestrator._twitter_engine is None:
            SearchOrchestrator._twitter_engine = create_twitter_search()
        
        self.reddit_engine = SearchOrchestrator._reddit_engine
        self.web_engine = SearchOrchestrator._web_engine
        self.youtube_engine = SearchOrchestrator._youtube_engine
        self.twitter_engine = SearchOrchestrator._twitter_engine
        
        self.query_optimizer = QueryOptimizer()
        self.ranker = ResultRanker()
    
    async def search(self, query: SearchQuery) -> SearchResults:
        """
        Execute deep search across all selected sources concurrently
        Returns aggregated, ranked results
        """
        start_time = time.time()
        
        # OPTIMIZATION 1: Optimize query
        optimized_query = self.query_optimizer.optimize(query.query, query.context)
        
        # Prepare tasks based on selected sources
        tasks = {}
        sources = [s.lower() for s in query.sources]
        
        # OPTIMIZATION 2: Use timeouts to prevent slow sources from blocking
        timeout = 15  # seconds
        
        if "reddit" in sources:
            tasks["reddit"] = asyncio.wait_for(
                self.reddit_engine.search(optimized_query, query.max_results),
                timeout=timeout
            )
        
        if "forums" in sources or "web" in sources:
            tasks["forums"] = asyncio.wait_for(
                self.web_engine.search(optimized_query, query.max_results),
                timeout=timeout
            )
        
        if "youtube" in sources:
            tasks["youtube"] = asyncio.wait_for(
                self.youtube_engine.search(optimized_query, query.max_results),
                timeout=timeout
            )
        
        if "twitter" in sources:
            tasks["twitter"] = asyncio.wait_for(
                self.twitter_engine.search(query.query, query.max_results),  # Use original query for sentiment
                timeout=timeout
            )
        
        # OPTIMIZATION 3: Execute all searches concurrently
        results_dict = {}
        if tasks:
            task_names = list(tasks.keys())
            task_coroutines = list(tasks.values())
            
            raw_results = await asyncio.gather(*task_coroutines, return_exceptions=True)
            
            for name, result in zip(task_names, raw_results):
                if isinstance(result, Exception):
                    if isinstance(result, asyncio.TimeoutError):
                        print(f"Timeout in {name} search")
                    else:
                        print(f"Error in {name} search: {result}")
                    results_dict[name] = []
                else:
                    # Convert to dict for JSON serialization
                    results_dict[name] = [r.model_dump() for r in result]
        
        # OPTIMIZATION 4: Smart ranking and deduplication
        results_dict = self.ranker.rank_and_dedupe(results_dict, query.query)
        
        # Calculate total results and time
        total = sum(len(v) for v in results_dict.values())
        elapsed = (time.time() - start_time) * 1000  # ms
        
        return SearchResults(
            query=query.query,
            results=results_dict,
            total_results=total,
            search_time_ms=round(elapsed, 2)
        )


async def deep_search(query_dict: dict) -> dict:
    """
    Main entry point for deep search
    Accepts a query dict and returns results dict
    """
    query = SearchQuery(**query_dict)
    orchestrator = SearchOrchestrator()
    results = await orchestrator.search(query)
    return results.to_dict()


# Factory function
def create_orchestrator() -> SearchOrchestrator:
    return SearchOrchestrator()
