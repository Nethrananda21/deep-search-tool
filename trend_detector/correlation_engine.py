"""
Correlation Engine
Matches Twitter trends with new token launches to find memecoin opportunities
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

from .burst_detector import BurstSignal
from .twitter_monitor import TrendAlert
from .pumpfun_monitor import NewToken


@dataclass
class MemecoinOpportunity:
    """A potential memecoin opportunity - trend matched with token"""
    trend_keyword: str
    token: NewToken
    match_score: float  # 0-1 similarity
    trend_score: float  # Burst score from Twitter
    opportunity_score: float  # Combined score
    time_delta_minutes: float  # Time between trend and token launch
    alert_time: datetime
    
    def to_dict(self) -> dict:
        return {
            "trend_keyword": self.trend_keyword,
            "token_name": self.token.name,
            "token_symbol": self.token.symbol,
            "token_mint": self.token.mint,
            "match_score": round(self.match_score, 3),
            "trend_score": round(self.trend_score, 2),
            "opportunity_score": round(self.opportunity_score, 2),
            "time_delta_minutes": round(self.time_delta_minutes, 1),
            "alert_time": self.alert_time.isoformat()
        }
    
    def __str__(self) -> str:
        return (
            f"🎯 OPPORTUNITY: '{self.trend_keyword}' → ${self.token.symbol}\n"
            f"   Match: {self.match_score:.0%} | Trend: {self.trend_score:.1f}x | "
            f"Score: {self.opportunity_score:.1f}\n"
            f"   Token: {self.token.name} ({self.token.mint[:12]}...)\n"
            f"   Time gap: {self.time_delta_minutes:.0f} min"
        )


class CorrelationEngine:
    """
    Correlates Twitter trends with Pump.fun token launches
    
    Strategy:
    1. Fuzzy match trend keywords to token names/symbols
    2. Score matches by similarity and timing
    3. Alert on high-scoring opportunities
    """
    
    def __init__(
        self,
        min_match_score: float = 0.6,  # Minimum string similarity
        max_time_gap_hours: float = 24,  # Max time between trend and token
        on_opportunity: Optional[callable] = None
    ):
        self.min_match_score = min_match_score
        self.max_time_gap_hours = max_time_gap_hours
        self.on_opportunity = on_opportunity
        
        # Track opportunities
        self.opportunities: List[MemecoinOpportunity] = []
        self.seen_matches: set = set()  # Avoid duplicate alerts
    
    def correlate(
        self,
        trends: List[TrendAlert],
        tokens: List[NewToken]
    ) -> List[MemecoinOpportunity]:
        """
        Find correlations between trends and tokens
        Returns list of opportunities sorted by score
        """
        opportunities = []
        now = datetime.now()
        max_gap = timedelta(hours=self.max_time_gap_hours)
        
        for trend in trends:
            trend_kw = trend.keyword.lower().strip('#$')
            
            for token in tokens:
                # Check time gap
                time_delta = abs((now - token.timestamp).total_seconds() / 60)
                if timedelta(minutes=time_delta) > max_gap:
                    continue
                
                # Calculate match score
                match_score = self._calculate_match_score(trend_kw, token)
                
                if match_score >= self.min_match_score:
                    # Check for duplicates
                    match_key = f"{trend_kw}:{token.mint}"
                    if match_key in self.seen_matches:
                        continue
                    self.seen_matches.add(match_key)
                    
                    # Calculate opportunity score
                    opportunity_score = self._calculate_opportunity_score(
                        match_score=match_score,
                        trend_score=trend.burst_score,
                        time_delta_minutes=time_delta,
                        is_meme_candidate=trend.is_meme_candidate
                    )
                    
                    opportunity = MemecoinOpportunity(
                        trend_keyword=trend.keyword,
                        token=token,
                        match_score=match_score,
                        trend_score=trend.burst_score,
                        opportunity_score=opportunity_score,
                        time_delta_minutes=time_delta,
                        alert_time=now
                    )
                    
                    opportunities.append(opportunity)
                    self.opportunities.append(opportunity)
                    
                    # Callback
                    if self.on_opportunity:
                        self.on_opportunity(opportunity)
        
        # Sort by opportunity score
        opportunities.sort(key=lambda x: x.opportunity_score, reverse=True)
        
        return opportunities
    
    def match_trend_to_tokens(
        self,
        trend_keyword: str,
        tokens: List[NewToken]
    ) -> List[Tuple[NewToken, float]]:
        """
        Find tokens matching a specific trend keyword
        Returns list of (token, match_score) tuples
        """
        trend_kw = trend_keyword.lower().strip('#$')
        matches = []
        
        for token in tokens:
            score = self._calculate_match_score(trend_kw, token)
            if score >= self.min_match_score:
                matches.append((token, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def match_token_to_trends(
        self,
        token: NewToken,
        trends: List[TrendAlert]
    ) -> List[Tuple[TrendAlert, float]]:
        """
        Find trends matching a specific token
        Returns list of (trend, match_score) tuples
        """
        matches = []
        
        for trend in trends:
            trend_kw = trend.keyword.lower().strip('#$')
            score = self._calculate_match_score(trend_kw, token)
            if score >= self.min_match_score:
                matches.append((trend, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def _calculate_match_score(self, keyword: str, token: NewToken) -> float:
        """
        Calculate fuzzy match score between keyword and token
        Returns 0-1 score
        """
        scores = []
        
        # Match against token name
        if token.name:
            name_lower = token.name.lower()
            
            # Exact substring match
            if keyword in name_lower or name_lower in keyword:
                scores.append(0.95)
            else:
                # Fuzzy match
                scores.append(SequenceMatcher(None, keyword, name_lower).ratio())
            
            # Match against individual words in name
            for word in name_lower.split():
                if keyword == word:
                    scores.append(1.0)
                elif keyword in word or word in keyword:
                    scores.append(0.85)
        
        # Match against symbol
        if token.symbol:
            symbol_lower = token.symbol.lower()
            
            if keyword == symbol_lower:
                scores.append(1.0)
            elif keyword in symbol_lower or symbol_lower in keyword:
                scores.append(0.9)
            else:
                scores.append(SequenceMatcher(None, keyword, symbol_lower).ratio())
        
        return max(scores) if scores else 0.0
    
    def _calculate_opportunity_score(
        self,
        match_score: float,
        trend_score: float,
        time_delta_minutes: float,
        is_meme_candidate: bool
    ) -> float:
        """
        Calculate overall opportunity score
        Higher = better opportunity
        """
        # Base score from match quality (0-30 points)
        score = match_score * 30
        
        # Trend strength bonus (0-30 points)
        # Cap at 10x burst
        trend_bonus = min(trend_score, 10) * 3
        score += trend_bonus
        
        # Freshness bonus (0-25 points)
        # Newer = better
        if time_delta_minutes < 60:
            freshness = 25
        elif time_delta_minutes < 180:
            freshness = 20
        elif time_delta_minutes < 360:
            freshness = 15
        elif time_delta_minutes < 720:
            freshness = 10
        else:
            freshness = 5
        score += freshness
        
        # Meme candidate bonus (0-15 points)
        if is_meme_candidate:
            score += 15
        
        return score
    
    def get_top_opportunities(self, n: int = 10) -> List[MemecoinOpportunity]:
        """Get top N opportunities by score"""
        sorted_ops = sorted(
            self.opportunities,
            key=lambda x: x.opportunity_score,
            reverse=True
        )
        return sorted_ops[:n]
    
    def clear_old_matches(self, hours: int = 24):
        """Clear matches older than N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        self.opportunities = [
            op for op in self.opportunities
            if op.alert_time > cutoff
        ]


# Factory function
def create_correlation_engine(**kwargs) -> CorrelationEngine:
    return CorrelationEngine(**kwargs)
