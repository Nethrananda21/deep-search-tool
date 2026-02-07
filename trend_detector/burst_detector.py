"""
Burst Detection Algorithm
Implements sliding window burst detection for identifying emerging trends
Based on Kleinberg's burst detection principles, simplified for real-time use
"""
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import math


@dataclass
class BurstSignal:
    """Represents a detected burst/spike in keyword frequency"""
    keyword: str
    current_count: int
    baseline_count: float
    burst_score: float  # How much above baseline (multiplier)
    velocity: float  # Rate of growth
    first_seen: datetime
    last_seen: datetime
    peak_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "current_count": self.current_count,
            "baseline_count": round(self.baseline_count, 2),
            "burst_score": round(self.burst_score, 2),
            "velocity": round(self.velocity, 2),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "peak_count": self.peak_count
        }


@dataclass
class KeywordWindow:
    """Sliding window for tracking keyword frequency over time"""
    counts: deque = field(default_factory=lambda: deque(maxlen=12))  # 12 windows = 1 hour at 5min intervals
    timestamps: deque = field(default_factory=lambda: deque(maxlen=12))
    first_seen: Optional[datetime] = None
    peak_count: int = 0


class BurstDetector:
    """
    Detects keyword bursts using sliding window analysis
    
    Strategy:
    1. Track keyword frequency in sliding time windows
    2. Calculate baseline from historical windows
    3. Detect bursts when current > baseline * threshold
    4. Calculate velocity (rate of growth)
    """
    
    def __init__(
        self,
        window_size_seconds: int = 300,  # 5 minutes
        min_burst_threshold: float = 3.0,  # 3x baseline = burst
        min_absolute_count: int = 5,  # Minimum mentions to consider
        min_velocity: float = 1.5  # Minimum growth rate
    ):
        self.window_size = window_size_seconds
        self.min_burst_threshold = min_burst_threshold
        self.min_absolute_count = min_absolute_count
        self.min_velocity = min_velocity
        
        # keyword -> KeywordWindow
        self.keyword_windows: Dict[str, KeywordWindow] = defaultdict(KeywordWindow)
        
        # Current window accumulator
        self.current_window: Dict[str, int] = defaultdict(int)
        self.current_window_start: datetime = datetime.now()
        
        # Active bursts
        self.active_bursts: Dict[str, BurstSignal] = {}
    
    def add_keyword(self, keyword: str, count: int = 1):
        """Add a keyword occurrence to the current window"""
        keyword = keyword.lower().strip()
        if len(keyword) < 2:
            return
        
        self.current_window[keyword] += count
        
        # Update first_seen if new keyword
        if self.keyword_windows[keyword].first_seen is None:
            self.keyword_windows[keyword].first_seen = datetime.now()
    
    def add_text(self, text: str):
        """Extract and add keywords from text (tweet/post)"""
        # Simple tokenization
        words = text.lower().split()
        
        for word in words:
            # Clean word
            word = ''.join(c for c in word if c.isalnum())
            
            # Skip short words and common stop words
            if len(word) < 3:
                continue
            if word in STOP_WORDS:
                continue
            
            self.add_keyword(word)
        
        # Also extract hashtags
        import re
        hashtags = re.findall(r'#(\w+)', text.lower())
        for tag in hashtags:
            self.add_keyword(f"#{tag}")
    
    def flush_window(self) -> List[BurstSignal]:
        """
        Close current window, add to history, and detect bursts
        Call this periodically (e.g., every 5 minutes)
        """
        now = datetime.now()
        bursts = []
        
        # Process each keyword in current window
        for keyword, count in self.current_window.items():
            window = self.keyword_windows[keyword]
            
            # Add current count to history
            window.counts.append(count)
            window.timestamps.append(now)
            
            # Update peak
            if count > window.peak_count:
                window.peak_count = count
            
            # Need at least 2 windows to detect burst
            if len(window.counts) < 2:
                continue
            
            # Calculate baseline (average of previous windows, excluding current)
            historical = list(window.counts)[:-1]
            if not historical:
                continue
            
            baseline = sum(historical) / len(historical)
            
            # Skip if baseline is too low (noise filtering)
            if baseline < 1 and count < self.min_absolute_count:
                continue
            
            # Calculate burst score
            if baseline > 0:
                burst_score = count / baseline
            else:
                burst_score = count * 2  # No baseline, use count as proxy
            
            # Calculate velocity (growth rate)
            if len(window.counts) >= 2:
                prev_count = window.counts[-2]
                if prev_count > 0:
                    velocity = count / prev_count
                else:
                    velocity = count
            else:
                velocity = 1.0
            
            # Check if this is a burst
            is_burst = (
                burst_score >= self.min_burst_threshold and
                count >= self.min_absolute_count and
                velocity >= self.min_velocity
            )
            
            if is_burst:
                burst = BurstSignal(
                    keyword=keyword,
                    current_count=count,
                    baseline_count=baseline,
                    burst_score=burst_score,
                    velocity=velocity,
                    first_seen=window.first_seen or now,
                    last_seen=now,
                    peak_count=window.peak_count
                )
                bursts.append(burst)
                self.active_bursts[keyword] = burst
            elif keyword in self.active_bursts:
                # Burst ended
                del self.active_bursts[keyword]
        
        # Reset current window
        self.current_window = defaultdict(int)
        self.current_window_start = now
        
        # Sort bursts by score
        bursts.sort(key=lambda x: x.burst_score, reverse=True)
        
        return bursts
    
    def get_active_bursts(self) -> List[BurstSignal]:
        """Get all currently active bursts"""
        return list(self.active_bursts.values())
    
    def get_top_keywords(self, n: int = 20) -> List[Tuple[str, int]]:
        """Get top N keywords in current window"""
        sorted_kw = sorted(
            self.current_window.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_kw[:n]


# Common stop words to filter out
STOP_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'to', 'of',
    'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
    'during', 'before', 'after', 'above', 'below', 'between', 'under',
    'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
    'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
    'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
    'very', 'just', 'and', 'but', 'if', 'or', 'because', 'until', 'while',
    'this', 'that', 'these', 'those', 'am', 'it', 'its', 'my', 'me', 'you',
    'your', 'he', 'she', 'they', 'them', 'his', 'her', 'their', 'what',
    'which', 'who', 'whom', 'get', 'got', 'like', 'lol', 'omg', 'https',
    'http', 'www', 'com', 'just', 'now', 'new', 'one', 'two', 'also'
}


# Convenience function
def create_burst_detector(**kwargs) -> BurstDetector:
    return BurstDetector(**kwargs)
