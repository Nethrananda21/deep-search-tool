"""
Twitter Trend Monitor
Continuously monitors Twitter for emerging trends using the existing twitter_search
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass

from .burst_detector import BurstDetector, BurstSignal, create_burst_detector


@dataclass
class TrendAlert:
    """A detected trend that might spawn a memecoin"""
    keyword: str
    burst_score: float
    velocity: float
    mention_count: int
    trend_type: str  # 'hashtag', 'keyword', 'phrase'
    first_detected: datetime
    sample_tweets: List[str]
    is_meme_candidate: bool
    
    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "burst_score": round(self.burst_score, 2),
            "velocity": round(self.velocity, 2),
            "mention_count": self.mention_count,
            "trend_type": self.trend_type,
            "first_detected": self.first_detected.isoformat(),
            "sample_tweets": self.sample_tweets[:3],
            "is_meme_candidate": self.is_meme_candidate
        }


class TwitterTrendMonitor:
    """
    Monitors Twitter for emerging trends using burst detection
    
    Flow:
    1. Periodically search Twitter for broad terms (crypto, meme, etc.)
    2. Extract keywords from results
    3. Feed into burst detector
    4. Alert when bursts detected
    """
    
    # Terms that suggest meme potential
    MEME_INDICATORS = {
        'meme', 'coin', 'token', '$', 'pump', 'moon', 'ape', 'degen',
        'ser', 'gm', 'wagmi', 'ngmi', 'lfg', 'fomo', 'hodl', 'based',
        'viral', 'trending', 'bullish', 'send', 'buy', 'gem'
    }
    
    # Crypto-related search queries to monitor
    MONITOR_QUERIES = [
        "crypto meme",
        "solana meme",
        "new coin",
        "memecoin",
        "pump fun",
        "viral tweet",
        "trending meme",
    ]
    
    def __init__(
        self,
        poll_interval_seconds: int = 300,  # 5 minutes
        on_trend_detected: Optional[Callable[[TrendAlert], None]] = None
    ):
        self.poll_interval = poll_interval_seconds
        self.on_trend_detected = on_trend_detected
        
        # Burst detector for finding spikes
        self.burst_detector = create_burst_detector(
            window_size_seconds=poll_interval_seconds,
            min_burst_threshold=2.5,  # 2.5x normal = trend
            min_absolute_count=3,
            min_velocity=1.3
        )
        
        # Track sample tweets for each keyword
        self.keyword_samples: Dict[str, List[str]] = {}
        
        # Running state
        self.is_running = False
        self.last_poll: Optional[datetime] = None
        
        # Import twitter search
        try:
            from engines.twitter_search import create_twitter_search
            self.twitter_search = create_twitter_search()
        except ImportError:
            self.twitter_search = None
    
    async def poll_once(self) -> List[TrendAlert]:
        """
        Perform one polling cycle:
        1. Search Twitter with monitor queries
        2. Extract keywords
        3. Detect bursts
        4. Return trend alerts
        """
        if self.twitter_search is None:
            print("Twitter search not available")
            return []
        
        all_tweets = []
        
        # Search for each monitor query
        for query in self.MONITOR_QUERIES:
            try:
                results = await self.twitter_search.search(query, max_results=10)
                for result in results:
                    tweet_text = result.text
                    all_tweets.append(tweet_text)
                    
                    # Add to burst detector
                    self.burst_detector.add_text(tweet_text)
                    
                    # Track samples for keywords
                    words = tweet_text.lower().split()
                    for word in words:
                        word = ''.join(c for c in word if c.isalnum() or c == '#')
                        if len(word) >= 3:
                            if word not in self.keyword_samples:
                                self.keyword_samples[word] = []
                            if len(self.keyword_samples[word]) < 5:
                                self.keyword_samples[word].append(tweet_text[:200])
                
                # Small delay between queries
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Error searching '{query}': {e}")
                continue
        
        # Flush window and get bursts
        bursts = self.burst_detector.flush_window()
        
        # Convert bursts to trend alerts
        alerts = []
        for burst in bursts:
            # Determine trend type
            if burst.keyword.startswith('#'):
                trend_type = 'hashtag'
            elif burst.keyword.startswith('$'):
                trend_type = 'ticker'
            else:
                trend_type = 'keyword'
            
            # Check if it's a meme candidate
            is_meme = self._is_meme_candidate(burst.keyword)
            
            alert = TrendAlert(
                keyword=burst.keyword,
                burst_score=burst.burst_score,
                velocity=burst.velocity,
                mention_count=burst.current_count,
                trend_type=trend_type,
                first_detected=burst.first_seen,
                sample_tweets=self.keyword_samples.get(burst.keyword, []),
                is_meme_candidate=is_meme
            )
            alerts.append(alert)
            
            # Callback if provided
            if self.on_trend_detected:
                self.on_trend_detected(alert)
        
        self.last_poll = datetime.now()
        return alerts
    
    def _is_meme_candidate(self, keyword: str) -> bool:
        """Check if keyword is likely to spawn a memecoin"""
        kw_lower = keyword.lower()
        
        # Check for meme indicators in the keyword itself
        for indicator in self.MEME_INDICATORS:
            if indicator in kw_lower:
                return True
        
        # Check sample tweets for meme indicators
        samples = self.keyword_samples.get(keyword, [])
        for sample in samples:
            sample_lower = sample.lower()
            indicator_count = sum(1 for ind in self.MEME_INDICATORS if ind in sample_lower)
            if indicator_count >= 2:
                return True
        
        return False
    
    async def start_monitoring(self):
        """Start continuous monitoring loop"""
        self.is_running = True
        print(f"🔍 Starting Twitter trend monitoring (poll every {self.poll_interval}s)")
        
        while self.is_running:
            try:
                alerts = await self.poll_once()
                
                if alerts:
                    print(f"\n🚨 {len(alerts)} trend(s) detected!")
                    for alert in alerts:
                        emoji = "🔥" if alert.is_meme_candidate else "📈"
                        print(f"  {emoji} {alert.keyword}: {alert.burst_score:.1f}x burst, {alert.mention_count} mentions")
                else:
                    print(f"✓ Poll complete, no new trends ({datetime.now().strftime('%H:%M:%S')})")
                
                # Wait for next poll
                await asyncio.sleep(self.poll_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Monitor error: {e}")
                await asyncio.sleep(30)  # Wait before retry
        
        print("Twitter monitoring stopped")
    
    def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.is_running = False
    
    def get_current_trends(self) -> List[BurstSignal]:
        """Get currently active bursts"""
        return self.burst_detector.get_active_bursts()
    
    def get_top_keywords(self, n: int = 20) -> List[tuple]:
        """Get top keywords in current window"""
        return self.burst_detector.get_top_keywords(n)


# Factory function
def create_twitter_monitor(**kwargs) -> TwitterTrendMonitor:
    return TwitterTrendMonitor(**kwargs)
