"""
Fetch page metadata (title, description, thumbnail) for web URLs,
Twitter/X posts, and YouTube videos/podcasts.
"""

import re
from urllib.parse import urlparse, parse_qs
from typing import Optional, Tuple
import httpx
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ReadLaterBot/1.0; +https://github.com/readlater)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 10.0


def detect_type(url: str) -> str:
    host = urlparse(url).netloc.lower().lstrip("www.")
    if host in ("twitter.com", "x.com"):
        return "twitter"
    if host in ("youtube.com", "youtu.be", "m.youtube.com"):
        return "youtube"
    return "web"


def _youtube_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower().lstrip("www.")
    if host == "youtu.be":
        return parsed.path.lstrip("/")
    qs = parse_qs(parsed.query)
    return qs.get("v", [None])[0]


async def fetch_metadata(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (title, description, thumbnail) for the given URL."""
    kind = detect_type(url)
    try:
        if kind == "youtube":
            return await _fetch_youtube(url)
        elif kind == "twitter":
            return await _fetch_twitter(url)
        else:
            return await _fetch_generic(url)
    except Exception:
        return None, None, None


async def _fetch_youtube(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    vid = _youtube_video_id(url)
    thumbnail = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else None

    # Use oEmbed for title/author — no API key needed
    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.get(oembed_url, headers=HEADERS)
            if r.status_code == 200:
                data = r.json()
                title = data.get("title")
                author = data.get("author_name")
                description = f"YouTube video by {author}" if author else None
                return title, description, thumbnail
        except Exception:
            pass

    # Fallback to scraping og: tags
    title, description, og_thumb = await _fetch_generic(url)
    return title, description, og_thumb or thumbnail


async def _fetch_twitter(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Twitter/X blocks most scrapers; use publish.twitter.com oEmbed
    oembed_url = f"https://publish.twitter.com/oembed?url={url}&omit_script=true"
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.get(oembed_url, headers=HEADERS)
            if r.status_code == 200:
                data = r.json()
                author = data.get("author_name", "")
                html = data.get("html", "")
                # Strip HTML tags to get plain text preview
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text(separator=" ").strip()
                # Truncate description
                if len(text) > 280:
                    text = text[:277] + "..."
                title = f"Post by @{author}" if author else "Twitter/X post"
                return title, text or None, None
        except Exception:
            pass

    return "Twitter/X post", None, None


async def _fetch_generic(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        r = await client.get(url, headers=HEADERS)
        r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    def og(prop: str) -> Optional[str]:
        tag = soup.find("meta", property=f"og:{prop}") or soup.find(
            "meta", attrs={"name": f"og:{prop}"}
        )
        return tag.get("content") if tag else None

    def meta(name: str) -> Optional[str]:
        tag = soup.find("meta", attrs={"name": name})
        return tag.get("content") if tag else None

    title = (
        og("title")
        or (soup.title.string.strip() if soup.title else None)
        or meta("title")
    )
    description = og("description") or meta("description")
    thumbnail = og("image")

    return title, description, thumbnail
