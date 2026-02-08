# Deep Search Tool 🔍

An **intense, fast, and deep search tool** that searches Reddit, forums, articles, and YouTube for solutions. Perfect for troubleshooting and repair queries.

## Features

- 🚀 **Fast** - Parallel searches across all sources (~3 seconds)
- 📺 **YouTube Transcripts** - Extracts video captions for better context
- 🎯 **Smart Ranking** - Results ranked by relevance
- 🔧 **Repair-Focused** - Optimized for fix/repair queries
- 📊 **Multiple Output Formats** - Console table, JSON, or file

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run a search
python main.py --query "your problem here"
```

---

## Usage

### Command Line Options

```bash
python main.py [OPTIONS]

Input (one required):
  --input, -i FILE      Path to JSON input file
  --query, -q TEXT      Direct search query
  --stdin               Read JSON from stdin

Options:
  --sources, -s LIST    Sources to search: reddit, forums, youtube, all (default: all)
  --max, -m NUMBER      Max results per source (default: 10)
  --output, -o FILE     Save results to file
  --json                Output raw JSON (no formatting)
  --context, -c TEXT    Additional context for the search
```

### Examples

```bash
# Simple query - searches all sources
python main.py --query "how to fix JBL headphones earcup"

# Search specific sources only
python main.py --query "laptop overheating" --sources reddit youtube

# Limit results
python main.py --query "Windows blue screen" --max 5

# Save JSON output
python main.py --query "iPhone battery drain" --json --output results.json

# Add context for better results
python main.py --query "screen flickering" --context "Dell laptop, Windows 11"

# Use JSON input file
python main.py --input query.json
```

---

## Input JSON Format

Create a JSON file with your search parameters:

```json
{
  "query": "How to fix my broken JBL headphones",
  "context": "earcup detached from headband",
  "sources": ["reddit", "forums", "youtube"],
  "max_results": 10
}
```

### Fields

| Field         | Type   | Required | Description                              |
| ------------- | ------ | -------- | ---------------------------------------- |
| `query`       | string | ✅ Yes   | Your search query                        |
| `context`     | string | No       | Additional context for better results    |
| `sources`     | array  | No       | Which sources to search (default: all)   |
| `max_results` | number | No       | Maximum results per source (default: 10) |

---

## Output JSON Format

The tool outputs structured JSON with results from each source:

```json
{
  "query": "JBL headphones earcup repair",
  "timestamp": "2026-01-27T10:45:53.246456",
  "results": {
    "reddit": [
      {
        "title": "Need help for repairing headphones",
        "url": "https://reddit.com/r/headphones/...",
        "subreddit": "r/headphones",
        "score": 42,
        "num_comments": 8,
        "snippet": "The right earcup bracket is broken...",
        "relevance": 0.85
      }
    ],
    "forums": [
      {
        "title": "JBL Tune 720BT Ear Cup Replacement",
        "url": "https://www.ifixit.com/Guide/...",
        "source": "iFixit",
        "snippet": "Step-by-step ear cup replacement guide...",
        "relevance": 0.92
      }
    ],
    "youtube": [
      {
        "title": "How To Replace JBL Tune 500BT Ear-pads",
        "url": "https://www.youtube.com/watch?v=...",
        "channel": "Techscrew DIY",
        "views": "149,785 views",
        "duration": "1:56",
        "transcript": "Hi today I will show you how to change...",
        "relevance": 0.88
      }
    ]
  },
  "total_results": 14,
  "search_time_ms": 2982.74
}
```

---
## Feeding Results to Local LLM

### Option 1: Pipe to Ollama

```bash
python main.py --query "JBL earcup repair" --json | ollama run llama3 "Based on these search results, how do I fix my headphones?"
```
### Option 2: Python Script

```python
import json
import subprocess

# Run search
result = subprocess.run(
    ["python", "main.py", "--query", "JBL headphones repair", "--json"],
    capture_output=True, text=True
)
search_results = json.loads(result.stdout)

# Format for LLM
context = ""
for source, results in search_results["results"].items():
    for r in results:
        context += f"[{source.upper()}] {r['title']}\n"
        if r.get('transcript'):
            context += f"Transcript: {r['transcript'][:300]}\n"
        elif r.get('snippet'):
            context += f"Snippet: {r['snippet'][:200]}\n"
        context += "\n"

# Send to LLM (example with Ollama API)
import requests
response = requests.post("http://localhost:11434/api/generate", json={
    "model": "llama3",
    "prompt": f"Based on these search results:\n\n{context}\n\nHow do I fix my JBL headphones?",
    "stream": False
})
print(response.json()["response"])
```

### Option 3: Save & Load

```bash
# Save results
python main.py --query "fix my device" --json --output results.json

# Load in Python
import json
with open("results.json") as f:
    data = json.load(f)
```

---

## Sources Searched

| Source      | Description                                    |
| ----------- | ---------------------------------------------- |
| **reddit**  | Reddit posts and discussions                   |
| **forums**  | iFixit, Stack Overflow, tech forums, HowToGeek |
| **youtube** | YouTube videos with transcript extraction      |

---

## Tips for Better Results

1. **Be specific** - "JBL Tune 500BT earcup detached" > "headphones broken"
2. **Add context** - Use `--context` for device model, OS version, etc.
3. **Check transcripts** - YouTube transcripts often have detailed repair steps
4. **Combine sources** - Reddit for discussion, iFixit for guides, YouTube for visuals
