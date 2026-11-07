"""
MUSA Buyer Intelligence
Public Web Search Module

Initial target: Cleveland, Ohio
Categories: Cash Buyers, Flippers, Landlords, Developers

Uses publicly accessible DuckDuckGo HTML search results.
No login, private profiles, or restricted groups are accessed.
"""

import re
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser


MARKET = {
    "city": "Cleveland",
    "state": "Ohio",
    "country": "USA",
}

INVESTOR_TYPES = [
    "cash buyers",
    "house flippers",
    "real estate landlords",
    "real estate developers",
]


class SearchResultParser(HTMLParser):
    """Extract search result titles, links and snippets."""

    def __init__(self):
        super().__init__()
        self.results = []
        self.current = None
        self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "a" and "result__a" in attrs.get("class", ""):
            self.current = {
                "title": "",
                "url": attrs.get("href", ""),
                "snippet": "",
            }
            self.capture = "title"

        elif tag in ("a", "div", "td") and (
            "result__snippet" in attrs.get("class", "")
        ):
            if self.current:
                self.capture = "snippet"

    def handle_data(self, data):
        if self.current and self.capture:
            self.current[self.capture] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.capture == "title" and self.current:
            self.results.append(self.current)
            self.current = None
            self.capture = None

        elif tag in ("a", "div", "td") and self.capture == "snippet":
            self.capture = None


def clean_url(url):
    """Resolve DuckDuckGo redirect URLs."""
    if not url:
        return ""

    parsed = urllib.parse.urlparse(url)

    if "duckduckgo.com" in parsed.netloc:
        params = urllib.parse.parse_qs(parsed.query)
        if "uddg" in params:
            return params["uddg"][0]

    return url


def build_search_queries():
    """Create targeted Cleveland investor searches."""

    city = MARKET["city"]
    state = MARKET["state"]

    queries = []

    for investor_type in INVESTOR_TYPES:
        queries.extend([
            f'"{city}" "{state}" {investor_type}',
            f'{city} Ohio real estate investor {investor_type}',
            f'{city} property investor buying houses',
        ])

    # Publicly indexed Facebook content only.
    queries.extend([
        f'site:facebook.com "{city}" "cash buyer" real estate',
        f'site:facebook.com "{city}" "buying houses" investor',
        f'site:facebook.com "{city}" landlord real estate investor',
    ])

    return list(dict.fromkeys(queries))


def search_web(query, max_results=10):
    """Search public web results using DuckDuckGo HTML."""

    endpoint = "https://html.duckduckgo.com/html/"

    data = urllib.parse.urlencode({"q": query}).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; MUSAResearchBot/1.0)"
            )
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            page = response.read().decode("utf-8", errors="replace")

        parser = SearchResultParser()
        parser.feed(page)

        results = []

        for item in parser.results[:max_results]:
            url = clean_url(item["url"])

            if not url.startswith(("http://", "https://")):
                continue

            results.append({
                "title": re.sub(r"\s+", " ", item["title"]).strip(),
                "url": url,
                "snippet": re.sub(
                    r"\s+", " ", item["snippet"]
                ).strip(),
                "search_query": query,
                "source": urllib.parse.urlparse(url).netloc,
            })

        return results

    except Exception as error:
        print(f"Search failed: {query} | {error}")
        return []


def discover_public_sources():
    """Run all market searches and remove duplicate URLs."""

    all_results = []
    seen_urls = set()

    queries = build_search_queries()

    print(f"Market: {MARKET['city']}, {MARKET['state']}")
    print(f"Search queries: {len(queries)}")

    for number, query in enumerate(queries, start=1):
        print(f"[{number}/{len(queries)}] Searching: {query}")

        results = search_web(query)

        for result in results:
            url = result["url"]

            if url not in seen_urls:
                seen_urls.add(url)
                all_results.append(result)

        # Reduce the chance of rate limiting.
        time.sleep(2)

    return all_results


if __name__ == "__main__":
    results = discover_public_sources()

    print("\nMUSA RESEARCH RESULTS")
    print(f"Total unique sources: {len(results)}")

    for result in results:
        print("\nTitle:", result["title"])
        print("Website:", result["source"])
        print("URL:", result["url"])
        print("Evidence:", result["snippet"])
