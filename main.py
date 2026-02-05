"""
Deep Search Tool - Main Entry Point

An intense, fast, and deep search tool that searches the web and YouTube for solutions.

Usage:
    python main.py --input query.json
    python main.py --query "your problem here"
    python main.py --query "fix windows blue screen" --sources reddit youtube
    echo '{"query": "python pip error"}' | python main.py --stdin
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from orchestrator import deep_search
from config import config
from utils.fetcher import AsyncFetcher

console = Console()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Deep Search Tool - Search Reddit, Forums, and YouTube for solutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --query "how to fix pip install error"
  python main.py --input query.json
  python main.py --query "windows BSOD" --sources reddit forums
  python main.py --query "react hooks tutorial" --sources youtube --max 5
        """
    )
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input", "-i",
        type=str,
        help="Path to JSON input file"
    )
    input_group.add_argument(
        "--query", "-q",
        type=str,
        help="Direct search query string"
    )
    input_group.add_argument(
        "--stdin",
        action="store_true",
        help="Read JSON input from stdin"
    )
    
    # Additional options
    parser.add_argument(
        "--sources", "-s",
        nargs="+",
        choices=["reddit", "forums", "youtube", "twitter", "all"],
        default=["all"],
        help="Sources to search (default: all)"
    )
    parser.add_argument(
        "--max", "-m",
        type=int,
        default=10,
        help="Maximum results per source (default: 10)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON (no formatting)"
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Output formatted context for LLM consumption"
    )
    parser.add_argument(
        "--context", "-c",
        type=str,
        help="Additional context for the search"
    )
    
    return parser.parse_args()


def build_query(args) -> dict:
    """Build query dict from arguments"""
    if args.input:
        # Load from file
        with open(args.input, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    elif args.stdin:
        # Read from stdin
        return json.loads(sys.stdin.read())
    
    else:
        # Build from direct query
        sources = args.sources
        if "all" in sources:
            sources = ["reddit", "forums", "youtube", "twitter"]
        
        return {
            "query": args.query,
            "context": args.context,
            "sources": sources,
            "max_results": args.max
        }


def display_results(results: dict, raw_json: bool = False):
    """Display results in a beautiful format"""
    if raw_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    
    # Header
    console.print()
    console.print(Panel(
        f"[bold cyan]Query:[/] {results['query']}\n"
        f"[bold green]Results:[/] {results['total_results']} found in {results['search_time_ms']}ms",
        title="🔍 Deep Search Results",
        border_style="cyan"
    ))
    
    # Reddit Results
    if "reddit" in results["results"] and results["results"]["reddit"]:
        console.print("\n[bold red]📱 Reddit[/]")
        table = Table(show_header=True, header_style="bold red")
        table.add_column("Score", style="cyan", width=6)
        table.add_column("Title", style="white", max_width=50)
        table.add_column("Subreddit", style="green", width=15)
        table.add_column("URL", style="blue", max_width=40)
        
        for r in results["results"]["reddit"][:10]:
            table.add_row(
                str(r.get("score", 0)),
                r.get("title", "")[:50],
                r.get("subreddit", ""),
                r.get("url", "")[:40]
            )
        console.print(table)
    
    # Forum Results
    if "forums" in results["results"] and results["results"]["forums"]:
        console.print("\n[bold yellow]💬 Forums & Articles[/]")
        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Source", style="cyan", width=15)
        table.add_column("Title", style="white", max_width=50)
        table.add_column("URL", style="blue", max_width=50)
        
        for r in results["results"]["forums"][:10]:
            table.add_row(
                r.get("source", ""),
                r.get("title", "")[:50],
                r.get("url", "")[:50]
            )
        console.print(table)
    
    # YouTube Results
    if "youtube" in results["results"] and results["results"]["youtube"]:
        console.print("\n[bold magenta]🎬 YouTube Videos[/]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Duration", style="cyan", width=8)
        table.add_column("Title", style="white", max_width=40)
        table.add_column("Channel", style="green", width=12)
        table.add_column("Transcript", style="dim", max_width=50)
        table.add_column("URL", style="blue", max_width=30)
        
        for r in results["results"]["youtube"][:10]:
            transcript_preview = r.get("transcript", "")[:80]
            if len(r.get("transcript", "")) > 80:
                transcript_preview += "..."
            
            table.add_row(
                r.get("duration", ""),
                r.get("title", "")[:40],
                r.get("channel", "")[:12],
                transcript_preview if transcript_preview else "[No captions]",
                r.get("url", "")
            )
        console.print(table)
    
    # Twitter Results (for sentiment analysis)
    if "twitter" in results["results"] and results["results"]["twitter"]:
        console.print("\n[bold cyan]🐦 Twitter/X (Sentiment)[/]")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Author", style="green", width=15)
        table.add_column("Tweet", style="white", max_width=60)
        table.add_column("❤️", style="red", width=6)
        table.add_column("🔁", style="blue", width=6)
        table.add_column("URL", style="dim", max_width=30)
        
        for r in results["results"]["twitter"][:10]:
            table.add_row(
                r.get("author", "")[:15],
                r.get("text", "")[:60],
                str(r.get("likes", 0)),
                str(r.get("retweets", 0)),
                r.get("url", "")[:30]
            )
        console.print(table)
    
    console.print()


async def main():
    """Main entry point"""
    args = parse_args()
    
    try:
        # Build query
        query = build_query(args)
        
        # Show progress
        if not args.json:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]Searching...[/]"),
                console=console
            ) as progress:
                task = progress.add_task("search", total=None)
                results = await deep_search(query)
        else:
            results = await deep_search(query)
        
        # Output results
        if args.output:
            if args.llm:
                from llm_integration import format_for_llm
                output_content = format_for_llm(results)
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output_content)
            else:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
            if not args.json and not args.llm:
                console.print(f"[green]Results saved to {args.output}[/]")
        else:
            if args.llm:
                from llm_integration import format_for_llm
                print(format_for_llm(results))
            else:
                display_results(results, args.json)
    
    except FileNotFoundError as e:
        console.print(f"[red]Error: File not found - {e}[/]")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON - {e}[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        sys.exit(1)
    finally:
        # Clean up: close the aiohttp session to avoid resource leak warnings
        await AsyncFetcher.close()


if __name__ == "__main__":
    asyncio.run(main())
