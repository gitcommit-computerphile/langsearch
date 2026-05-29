import wikipedia as wiki_lib
import arxiv
from langchain_core.tools import tool
from youtubesearchpython import VideosSearch


@tool
def search_wikipedia(query: str) -> str:
    """Search Wikipedia for information about a person, place, event, or concept."""
    try:
        results = wiki_lib.search(query, results=3)
        if not results:
            return "No Wikipedia results found."
        summary = wiki_lib.summary(results[0], sentences=6, auto_suggest=False)
        return f"Source: Wikipedia — {results[0]}\n\n{summary}"
    except wiki_lib.DisambiguationError as e:
        try:
            summary = wiki_lib.summary(e.options[0], sentences=6, auto_suggest=False)
            return f"Source: Wikipedia — {e.options[0]}\n\n{summary}"
        except Exception:
            return f"Multiple results found: {', '.join(e.options[:5])}"
    except Exception as e:
        return f"Wikipedia search failed: {str(e)}"


@tool
def search_arxiv(query: str) -> str:
    """Search ArXiv for academic research papers on a scientific or technical topic."""
    try:
        search = arxiv.Search(query=query, max_results=3,
                              sort_by=arxiv.SortCriterion.Relevance)
        papers = []
        for paper in search.results():
            authors = ", ".join(str(a) for a in paper.authors[:3])
            papers.append(
                f"Title: {paper.title}\n"
                f"Authors: {authors}\n"
                f"Published: {paper.published.strftime('%Y-%m-%d')}\n"
                f"Summary: {paper.summary[:400]}\n"
                f"URL: {paper.entry_id}"
            )
        return "\n\n---\n\n".join(papers) if papers else "No ArXiv papers found."
    except Exception as e:
        return f"ArXiv search failed: {str(e)}"


@tool
def search_youtube(query: str) -> str:
    """Search YouTube for videos, tutorials, or lectures on a topic."""
    try:
        search = VideosSearch(query, limit=5)
        results = search.result().get("result", [])
        if not results:
            return "No YouTube videos found."
        lines = []
        for v in results:
            title = v.get("title", "")
            channel = v.get("channel", {}).get("name", "")
            duration = v.get("duration", "")
            link = v.get("link", "")
            lines.append(f"• {title} | {channel} | {duration} | {link}")
        return "YouTube Results:\n" + "\n".join(lines)
    except Exception as e:
        return f"YouTube search failed: {str(e)}"


def get_all_tools() -> list:
    return [search_wikipedia, search_arxiv, search_youtube]