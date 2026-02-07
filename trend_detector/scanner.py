"""
Memecoin Trend Scanner - Main Entry Point
Combines Twitter trend detection with Pump.fun token monitoring
"""
import asyncio
import argparse
import os
from datetime import datetime
from typing import Optional

from .twitter_monitor import TwitterTrendMonitor, TrendAlert, create_twitter_monitor
from .pumpfun_monitor import PumpFunMonitor, NewToken, create_pumpfun_monitor
from .correlation_engine import CorrelationEngine, MemecoinOpportunity, create_correlation_engine
from .alerter import ConsoleAlerter, create_console_alerter


class TrendScanner:
    """
    Main scanner that orchestrates:
    1. Twitter trend monitoring
    2. Pump.fun token monitoring
    3. Correlation and alerting
    """
    
    def __init__(
        self,
        twitter_poll_interval: int = 300,  # 5 minutes
        min_opportunity_score: float = 50.0,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None
    ):
        # Initialize components
        self.twitter_monitor = create_twitter_monitor(
            poll_interval_seconds=twitter_poll_interval,
            on_trend_detected=self._on_trend_detected
        )
        
        self.pumpfun_monitor = create_pumpfun_monitor(
            on_new_token=self._on_new_token
        )
        
        self.correlation_engine = create_correlation_engine(
            min_match_score=0.5,
            max_time_gap_hours=24,
            on_opportunity=self._on_opportunity
        )
        
        self.alerter = create_console_alerter(min_score=min_opportunity_score)
        
        # Optional Telegram
        self.telegram_alerter = None
        if telegram_bot_token and telegram_chat_id:
            from .alerter import create_telegram_alerter
            self.telegram_alerter = create_telegram_alerter(
                telegram_bot_token, telegram_chat_id,
                min_score=min_opportunity_score
            )
        
        # State
        self.is_running = False
        self.recent_trends: list = []
        self.recent_tokens: list = []
    
    def _on_trend_detected(self, trend: TrendAlert):
        """Callback when a new trend is detected"""
        self.recent_trends.append(trend)
        
        # Keep last 100 trends
        if len(self.recent_trends) > 100:
            self.recent_trends = self.recent_trends[-100:]
        
        # Log
        emoji = "🔥" if trend.is_meme_candidate else "📈"
        self.alerter.log(
            f"{emoji} Trend: {trend.keyword} ({trend.burst_score:.1f}x burst)",
            "success" if trend.is_meme_candidate else "info"
        )
        
        # Correlate with recent tokens
        self._check_correlations()
    
    def _on_new_token(self, token: NewToken):
        """Callback when a new token is launched"""
        self.recent_tokens.append(token)
        
        # Keep last 100 tokens
        if len(self.recent_tokens) > 100:
            self.recent_tokens = self.recent_tokens[-100:]
        
        # Log
        self.alerter.log(f"🆕 Token: {token.name} (${token.symbol})", "info")
        
        # Correlate with recent trends
        self._check_correlations()
    
    def _on_opportunity(self, opportunity: MemecoinOpportunity):
        """Callback when an opportunity is found"""
        # Console alert
        self.alerter.alert(opportunity)
        
        # Telegram alert (async)
        if self.telegram_alerter:
            asyncio.create_task(self.telegram_alerter.alert(opportunity))
    
    def _check_correlations(self):
        """Check for correlations between trends and tokens"""
        if not self.recent_trends or not self.recent_tokens:
            return
        
        self.correlation_engine.correlate(
            self.recent_trends,
            self.recent_tokens
        )
    
    async def start(self):
        """Start all monitors"""
        self.is_running = True
        
        print("\n" + "=" * 60)
        print("🚀 MEMECOIN TREND SCANNER")
        print("=" * 60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Monitoring: Twitter trends + Pump.fun launches")
        print("=" * 60 + "\n")
        
        # Run both monitors concurrently
        await asyncio.gather(
            self.twitter_monitor.start_monitoring(),
            self.pumpfun_monitor.start_monitoring(),
            return_exceptions=True
        )
    
    def stop(self):
        """Stop all monitors"""
        self.is_running = False
        self.twitter_monitor.stop_monitoring()
        self.pumpfun_monitor.stop_monitoring()
        print("\n🛑 Scanner stopped")
    
    def get_status(self) -> dict:
        """Get current scanner status"""
        return {
            "is_running": self.is_running,
            "active_trends": len(self.twitter_monitor.get_current_trends()),
            "recent_tokens": len(self.recent_tokens),
            "opportunities_found": len(self.correlation_engine.opportunities),
            "top_opportunities": [
                op.to_dict() for op in 
                self.correlation_engine.get_top_opportunities(5)
            ]
        }


async def run_scanner(args):
    """Run the trend scanner"""
    scanner = TrendScanner(
        twitter_poll_interval=args.interval,
        min_opportunity_score=args.min_score,
        telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
        telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID')
    )
    
    try:
        await scanner.start()
    except KeyboardInterrupt:
        scanner.stop()


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Memecoin Trend Scanner - Detect Twitter trends and Pump.fun token correlations"
    )
    
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=300,
        help="Twitter polling interval in seconds (default: 300)"
    )
    parser.add_argument(
        "--min-score", "-m",
        type=float,
        default=50.0,
        help="Minimum opportunity score to alert (default: 50)"
    )
    parser.add_argument(
        "--twitter-only",
        action="store_true",
        help="Only monitor Twitter trends (no Pump.fun)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a quick test"
    )
    
    args = parser.parse_args()
    
    if args.test:
        print("Running test...")
        asyncio.run(run_test())
    else:
        asyncio.run(run_scanner(args))


async def run_test():
    """Quick test of the scanner components"""
    from .burst_detector import create_burst_detector
    
    print("Testing burst detector...")
    detector = create_burst_detector()
    
    # Simulate tweets
    test_tweets = [
        "Wow this new meme is hilarious #test",
        "Everyone talking about $TEST coin",
        "test test test going viral",
        "have you seen the test meme?",
        "test is trending everywhere",
    ]
    
    for tweet in test_tweets:
        detector.add_text(tweet)
    
    bursts = detector.flush_window()
    print(f"Detected {len(bursts)} bursts")
    
    for burst in bursts:
        print(f"  - {burst.keyword}: {burst.burst_score:.1f}x")
    
    print("\n✅ Test complete!")


# Factory function for external use
def create_trend_scanner(**kwargs) -> TrendScanner:
    return TrendScanner(**kwargs)


if __name__ == "__main__":
    main()
