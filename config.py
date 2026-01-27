"""
Configuration for Deep Search Tool
Uses web scraping only - no API keys needed!
"""


class Config:
    """Configuration settings"""
    
    # Search settings
    DEFAULT_MAX_RESULTS: int = 10
    REQUEST_TIMEOUT: int = 15
    MAX_CONCURRENT_REQUESTS: int = 10
    
    # User agent for web scraping
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )


config = Config()
