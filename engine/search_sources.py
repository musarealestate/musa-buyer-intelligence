"""
MUSA Buyer Intelligence
Public Web Search Module

Market: Cleveland, Ohio
Sources: Publicly accessible web search results only.
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
    """Read result links and snippets from supported DDG HTML layouts."""

    def __init__(self):
        super().__init__()
        self.results = []
        self.current = None
        self.in_result_link = False
        self.in_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()

        if tag == "a" and (
            "result__a" in classes or "result-link" in classes
        ):
            self.current = {
                "title": "",
                "url": attrs.get("href", ""),
                "snippet": "",
            }
            self.in_result_link = True

        elif self.current and "result__snippet" in classes:
            self.in_snippet = True

    def handle_data(self, data):
        if self.current:
            if self.in_result_link:
                self.current["title"] += data
            elif self.in_snippet:
                self.current["snippet"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.in_result_link and self.current:
            self.in_result_link = False
            self.results.append(self.current)
            self.current = None

        elif tag in ("div", "td") and self.in_snippet:
            self.in_snippet = False


def clean_url(url):
    if not url:
        return ""

    parsed = urllib.parse.urlparse(url)

    if "duckduckgo.com" in parsed.netloc:
        params = urllib.parse.parse_qs(parsed.query)
        if "uddg" in params:
            return params["uddg"][0]

    if url.startswith("//"):
        return "https:" + url

    return url


def build_search_queries():
    city = MARKET["city"]
    state = MARKET["state"]

    queries = []

    for investor_type in INVESTOR_TYPES:
        queries.extend([
            f'"{city}" "{state}" {investor_type}',
            f'{city} Ohio real estate investor {investor_type}',
        ])

    queries.extend([
        f'site:facebook.com "{city}" "cash buyer" real estate',
        f'site:facebook.com "{city}" "buying houses" investor',
        f'site:facebook.com "{city}" landlord real estate investor',
    ])

    return list(dict.fromkeys(queries))


def search_web(query, max_results=10):
    endpoint = "https://html.duckduckgo.com/html/"
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://duckduckgo.com/",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            status = response.status
            page = response.read().decode("utf-8", errors="replace")

        parser = SearchResultParser()
        parser.feed(page)

        results = []

        for item in parser.results:
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

            if len(results) >= max_results:
                break

        if not results:
            lower_page = page.lower()

            if "captcha" in lower_page or "anomaly" in lower_page:
                print("Search response may be blocked by a bot check.")
            elif status != 200:
                print(f"Unexpected HTTP status: {status}")
            else:
                print(
                    "No recognized result links. "
                    f"Response length: {len(page)} characters."
                )

        return results

    except Exception as error:
        print(f"Search failed: {query} | {type(error).__name__}: {error}")
        return []


def discover_public_sources():
    all_results = []
    seen_urls = set()
    queries = build_search_queries()

    print(f"Market: {MARKET['city']}, {MARKET['state']}")
    print(f"Search queries: {len(queries)}")

    for number, query in enumerate(queries, start=1):
        print(f"\n[{number}/{len(queries)}] Searching: {query}")

        results = search_web(query)

        print(f"Results found for this query: {len(results)}")

        for result in results:
            url = result["url"]

            if url not in seen_urls:
                seen_urls.add(url)
                all_results.append(result)

        time.sleep(2)

    return all_results


if __name__ == "__main__":
    results = discover_public_sources()

    print("\n========== MUSA RESEARCH RESULTS ==========")
    print(f"Total unique sources: {len(results)}")

    for result in results:
        print("\nTitle:", result["title"])
        print("Website:", result["source"])
        print("URL:", result["url"])
        print("Evidence:", result["snippet"])
        print("Search:", result["search_query"])
