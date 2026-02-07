"""
Trend Detector Module - Memecoin Trend Detection System
Detects emerging Twitter trends and correlates with new token launches
"""

from .burst_detector import BurstDetector, BurstSignal, create_burst_detector
from .twitter_monitor import TwitterTrendMonitor, TrendAlert, create_twitter_monitor
from .pumpfun_monitor import PumpFunMonitor, NewToken, create_pumpfun_monitor
from .correlation_engine import CorrelationEngine, MemecoinOpportunity, create_correlation_engine
from .alerter import ConsoleAlerter, TelegramAlerter, create_console_alerter
from .scanner import TrendScanner, create_trend_scanner

__all__ = [
    'BurstDetector', 'BurstSignal', 'create_burst_detector',
    'TwitterTrendMonitor', 'TrendAlert', 'create_twitter_monitor',
    'PumpFunMonitor', 'NewToken', 'create_pumpfun_monitor',
    'CorrelationEngine', 'MemecoinOpportunity', 'create_correlation_engine',
    'ConsoleAlerter', 'TelegramAlerter', 'create_console_alerter',
    'TrendScanner', 'create_trend_scanner',
]
