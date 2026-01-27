"""
LLM Integration Module
Formats search results for optimal LLM consumption
"""
import json
from typing import Dict, Any, Optional


def format_for_llm(search_results: Dict[str, Any], max_items: int = 5) -> str:
    """
    Format search results into compact JSON for LLM consumption.
    
    Args:
        search_results: The raw search results dict
        max_items: Maximum items per source
    
    Returns:
        Compact JSON string optimized for LLM context
    """
    query = search_results.get("query", "")
    results = search_results.get("results", {})
    
    llm_data = {
        "query": query,
        "sources": {}
    }
    
    # Process Reddit results - keep only essential fields
    if "reddit" in results and results["reddit"]:
        llm_data["sources"]["reddit"] = []
        for r in results["reddit"][:max_items]:
            llm_data["sources"]["reddit"].append({
                "title": r.get("title", ""),
                "subreddit": r.get("subreddit", ""),
                "snippet": r.get("snippet", "")[:300] if r.get("snippet") else "",
                "url": r.get("url", "")
            })
    
    # Process Forum/Article results
    if "forums" in results and results["forums"]:
        llm_data["sources"]["forums"] = []
        for r in results["forums"][:max_items]:
            llm_data["sources"]["forums"].append({
                "title": r.get("title", ""),
                "source": r.get("source", ""),
                "snippet": r.get("snippet", "")[:300] if r.get("snippet") else "",
                "url": r.get("url", "")
            })
    
    # Process YouTube results with transcripts
    if "youtube" in results and results["youtube"]:
        llm_data["sources"]["youtube"] = []
        for r in results["youtube"][:max_items]:
            item = {
                "title": r.get("title", ""),
                "channel": r.get("channel", ""),
                "duration": r.get("duration", ""),
                "views": r.get("views", ""),
                "url": r.get("url", "")
            }
            # Include transcript if available (most valuable)
            if r.get("transcript"):
                item["transcript"] = r.get("transcript", "")[:500]
            llm_data["sources"]["youtube"].append(item)
    
    return json.dumps(llm_data, indent=2, ensure_ascii=False)


def create_llm_prompt(search_results: Dict[str, Any], user_question: str) -> str:
    """
    Create a complete prompt for the LLM with search context.
    
    Args:
        search_results: The raw search results dict
        user_question: The user's original question
    
    Returns:
        Complete prompt string for LLM
    """
    context = format_for_llm(search_results)
    
    prompt = f"""Based on the following search results, provide a helpful and accurate answer to the user's question.

{context}

USER QUESTION: {user_question}

Please provide:
1. A direct answer to the question
2. Step-by-step instructions if applicable
3. Links to the most relevant sources

ANSWER:"""
    
    return prompt


def get_ollama_payload(search_results: Dict[str, Any], user_question: str, model: str = "llama3") -> Dict:
    """
    Create a payload for Ollama API.
    
    Args:
        search_results: The raw search results dict
        user_question: The user's original question
        model: Ollama model name
    
    Returns:
        Dict ready to POST to Ollama API
    """
    prompt = create_llm_prompt(search_results, user_question)
    
    return {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,  # Lower for more factual responses
            "num_predict": 1024
        }
    }


if __name__ == "__main__":
    # Test with sample data
    sample = {
        "query": "JBL headphones repair",
        "results": {
            "youtube": [
                {
                    "title": "How to Replace JBL Ear Pads",
                    "channel": "DIY Tech",
                    "duration": "5:32",
                    "views": "100K views",
                    "url": "https://youtube.com/watch?v=123",
                    "transcript": "Today I'll show you how to replace the ear pads on your JBL headphones. First, remove the old pads by gently pulling..."
                }
            ],
            "forums": [
                {
                    "title": "JBL Ear Cup Replacement Guide",
                    "source": "iFixit",
                    "snippet": "Step-by-step guide to replace ear cups",
                    "url": "https://ifixit.com/guide/123"
                }
            ]
        }
    }
    
    print(format_for_llm(sample))
