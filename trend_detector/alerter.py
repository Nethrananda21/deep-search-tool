"""
Alert System
Sends notifications when memecoin opportunities are detected
"""
import asyncio
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from .correlation_engine import MemecoinOpportunity


class ConsoleAlerter:
    """Simple console-based alerter with colors"""
    
    # ANSI color codes
    COLORS = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'reset': '\033[0m',
        'bold': '\033[1m'
    }
    
    def __init__(self, min_score: float = 50.0):
        self.min_score = min_score
        self.alert_count = 0
    
    def alert(self, opportunity: MemecoinOpportunity):
        """Print alert to console"""
        if opportunity.opportunity_score < self.min_score:
            return
        
        self.alert_count += 1
        
        # Determine alert level
        if opportunity.opportunity_score >= 80:
            color = 'red'
            emoji = "🔥🔥🔥"
            level = "HIGH"
        elif opportunity.opportunity_score >= 60:
            color = 'yellow'
            emoji = "🔥🔥"
            level = "MEDIUM"
        else:
            color = 'cyan'
            emoji = "🔥"
            level = "LOW"
        
        c = self.COLORS
        
        print(f"\n{c['bold']}{c[color]}")
        print("=" * 60)
        print(f"{emoji} MEMECOIN OPPORTUNITY #{self.alert_count} - {level} {emoji}")
        print("=" * 60)
        print(f"{c['reset']}")
        
        print(f"{c['cyan']}Trend:{c['reset']} {opportunity.trend_keyword}")
        print(f"{c['green']}Token:{c['reset']} {opportunity.token.name} (${opportunity.token.symbol})")
        print(f"{c['blue']}Mint:{c['reset']} {opportunity.token.mint}")
        print()
        print(f"Match Score: {opportunity.match_score:.0%}")
        print(f"Trend Score: {opportunity.trend_score:.1f}x burst")
        print(f"Opportunity: {opportunity.opportunity_score:.1f}/100")
        print(f"Time Gap: {opportunity.time_delta_minutes:.0f} minutes")
        print()
        print(f"{c['magenta']}Pump.fun: https://pump.fun/{opportunity.token.mint}{c['reset']}")
        print(f"{c['bold']}{c[color]}")
        print("=" * 60)
        print(f"{c['reset']}\n")
    
    def log(self, message: str, level: str = "info"):
        """Log a message"""
        c = self.COLORS
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if level == "error":
            color = c['red']
        elif level == "warning":
            color = c['yellow']
        elif level == "success":
            color = c['green']
        else:
            color = c['white']
        
        print(f"{c['cyan']}[{timestamp}]{color} {message}{c['reset']}")


class TelegramAlerter:
    """
    Send alerts via Telegram bot
    Requires: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars
    """
    
    def __init__(self, bot_token: str, chat_id: str, min_score: float = 60.0):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.min_score = min_score
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def alert(self, opportunity: MemecoinOpportunity):
        """Send alert via Telegram"""
        if opportunity.opportunity_score < self.min_score:
            return
        
        # Format message
        if opportunity.opportunity_score >= 80:
            emoji = "🔥🔥🔥"
        elif opportunity.opportunity_score >= 60:
            emoji = "🔥🔥"
        else:
            emoji = "🔥"
        
        message = f"""
{emoji} *MEMECOIN OPPORTUNITY* {emoji}

*Trend:* `{opportunity.trend_keyword}`
*Token:* {opportunity.token.name} (${opportunity.token.symbol})

📊 *Scores:*
• Match: {opportunity.match_score:.0%}
• Trend: {opportunity.trend_score:.1f}x burst
• Opportunity: {opportunity.opportunity_score:.0f}/100

⏱ Time gap: {opportunity.time_delta_minutes:.0f} min

🔗 [Buy on Pump.fun](https://pump.fun/{opportunity.token.mint})
"""
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{self.api_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": False
                    }
                )
        except Exception as e:
            print(f"Telegram error: {e}")
    
    async def send_message(self, text: str):
        """Send a simple text message"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{self.api_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text
                    }
                )
        except Exception as e:
            print(f"Telegram error: {e}")


# Factory functions
def create_console_alerter(**kwargs) -> ConsoleAlerter:
    return ConsoleAlerter(**kwargs)

def create_telegram_alerter(bot_token: str, chat_id: str, **kwargs) -> TelegramAlerter:
    return TelegramAlerter(bot_token, chat_id, **kwargs)
