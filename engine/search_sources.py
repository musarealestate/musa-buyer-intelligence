
"""
MUSA Buyer Intelligence
Public Web Research Engine

Uses dashboard inputs from GitHub Actions.
Searches publicly accessible web results only.
Returns research evidence to the MUSA Google Sheets CRM.
"""

import json
import os
import re
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser


# --------------------------------------------------
# 1. DASHBOARD INPUTS
# --------------------------------------------------

def get_input(name, default=""):
    return os.environ.get(name, default).strip()


SEARCH_ID = get_input("INPUT_SEARCH_ID")
COUNTRY = get_input("INPUT_COUNTRY", "United States")
STATE = get_input("INPUT_STATE")
CITY = get_input("INPUT_CITY")
COUNTY = get_input("INPUT_COUNTY")
ZIP_CODE = get_input("INPUT_ZIP")
INVESTOR_TYPE = get_input("INPUT_INVESTOR_TYPE")
SEARCH_QUERY = get_input("INPUT_SEARCH_QUERY")
SOURCE_TARGET = get_input(
    "INPUT_SOURCE_TARGET",
    "Public web research"
)

SHEETS_API_URL = get_input("MUSA_SHEETS_API_URL")
SHEETS_TOKEN = get_input("MUSA_SHEETS_TOKEN")


# --------------------------------------------------
# 2. SEARCH RESULT PARSER
# --------------------------------------------------

class SearchResultParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.results = []
        self.current = None
        self.in_link = False
        self.in_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()

        if tag == "a" and (
            "result__a" in classes
            or "result-link" in classes
        ):
            self.current = {
                "title": "",
                "url": attrs.get("href", ""),
                "snippet": ""
            }
            self.in_link = True

        elif self.current and (
            "result__snippet" in classes
            or "result-snippet" in classes
        ):
            self.in_snippet = True

    def handle_data(self, data):
        if not self.current:
            return

        if self.in_link:
            self.current["title"] += data

        elif self.in_snippet:
            self.current["snippet"] += data

    def handle_endtag(self, tag):

        if tag == "a" and self.in_link and self.current:
            self.in_link = False
            self.results.append(self.current)
            self.current = None

        elif tag in ("div", "td") and self.in_snippet:
            self.in_snippet = False


# --------------------------------------------------
# 3. SEARCH QUERY BUILDER
# --------------------------------------------------

def build_search_queries():

    location_parts = [
        CITY,
        COUNTY,
        STATE,
        COUNTRY
    ]

    location = " ".join(
        part for part in location_parts if part
    )

    investor_terms = []

    if not INVESTOR_TYPE or INVESTOR_TYPE.lower() in (
        "all investor types",
        "all"
    ):
        investor_terms = [
            "cash buyers",
            "house flippers",
            "real estate investors",
            "landlords",
            "property developers",
            "wholesale real estate buyers"
        ]
    else:
        investor_terms = [INVESTOR_TYPE]

    queries = []

    for investor in investor_terms:
        queries.append(
            f'"{location}" {investor}'
        )

        queries.append(
            f'{location} real estate investment company {investor}'
        )

    if "facebook" in SOURCE_TARGET.lower():
        queries.extend([
            f'site:facebook.com "{location}" real estate investor',
            f'site:facebook.com "{location}" cash buyer',
            f'site:facebook.com "{location}" house flipper'
        ])

    elif "company" in SOURCE_TARGET.lower():
        queries.extend([
            f'{location} real estate investment companies',
            f'{location} property investment company contact',
            f'{location} real estate investors website'
        ])

    else:
        queries.extend([
            f'{location} real estate investment companies',
            f'{location} property investors contact',
            f'{location} cash home buyers'
        ])

    if SEARCH_QUERY:
        queries.append(
            f'{location} {SEARCH_QUERY}'
        )

    if ZIP_CODE:
        queries.append(
            f'"{ZIP_CODE}" real estate investors'
        )

    return list(dict.fromkeys(
        query.strip() for query in queries if query.strip()
    ))


# --------------------------------------------------
# 4. CLEAN SEARCH RESULT URL
# --------------------------------------------------

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


# --------------------------------------------------
# 5. PUBLIC WEB SEARCH
# --------------------------------------------------

def search_web(query, max_results=10):

    endpoint = "https://html.duckduckgo.com/html/"

    data = urllib.parse.urlencode({
        "q": query
    }).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9"
        }
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=25
        ) as response:

            page = response.read().decode(
                "utf-8",
                errors="replace"
            )

        parser = SearchResultParser()
        parser.feed(page)

        results = []

        for item in parser.results:

            url = clean_url(item["url"])

            if not url.startswith(("http://", "https://")):
                continue

            title = re.sub(
                r"\s+",
                " ",
                item["title"]
            ).strip()

            snippet = re.sub(
                r"\s+",
                " ",
                item["snippet"]
            ).strip()

            if not title and not snippet:
                continue

            results.append({
                "title": title,
                "url": url,
                "snippet": snippet,
                "search_query": query,
                "source": urllib.parse.urlparse(url).netloc
            })

            if len(results) >= max_results:
                break

        return results

    except Exception as error:

        print(
            "Search failed:",
            query,
            type(error).__name__,
            str(error)
        )

        return []


# --------------------------------------------------
# 6. DISCOVER PUBLIC SOURCES
# --------------------------------------------------

def discover_public_sources():

    all_results = []
    seen_urls = set()

    queries = build_search_queries()

    print("MUSA BUYER RESEARCH")
    print("Search ID:", SEARCH_ID)
    print("Location:", CITY, COUNTY, STATE, COUNTRY)
    print("Investor type:", INVESTOR_TYPE)
    print("Queries:", len(queries))

    for number, query in enumerate(queries, start=1):

        print(
            f"\n[{number}/{len(queries)}] Searching: {query}"
        )

        results = search_web(query)

        print("Results:", len(results))

        for result in results:

            url = result["url"]

            if url not in seen_urls:
                seen_urls.add(url)
                all_results.append(result)

        # Avoid sending too many rapid requests.
        time.sleep(2)

    return all_results


# --------------------------------------------------
# 7. PREPARE GOOGLE SHEETS BUYER RECORDS
# --------------------------------------------------

def prepare_buyer_records(results):

    buyers = []

    for result in results:

        # A search-result title is not proof of a person's identity.
        # Store it as a company/source label for human review.

        buyer = {
            "company": result["title"],
            "city": CITY,
            "state": STATE,
            "zip": ZIP_CODE,
            "county": COUNTY,
            "investorType": INVESTOR_TYPE,

            "sourcePlatform": result["source"],
            "sourceUrl": result["url"],

            "evidenceNotes": result["snippet"],

            "aiNotes": (
                "Public search result collected for research. "
                "This source has not been independently verified. "
                "Review the original page before contacting."
            ),

            "verificationStatus": "Needs Review",
            "contactStatus": "Not Contacted",

            "notes": (
                "Search ID: " + SEARCH_ID
                + " | Search query: "
                + result["search_query"]
            )
        }

        buyers.append(buyer)

    return buyers


# --------------------------------------------------
# 8. SEND RESULTS TO GOOGLE SHEETS
# --------------------------------------------------

def send_to_google_sheets(action, payload):

    if not SHEETS_API_URL or not SHEETS_TOKEN:
        raise RuntimeError(
            "Missing MUSA_SHEETS_API_URL or "
            "MUSA_SHEETS_TOKEN GitHub secrets."
        )

    request_data = {
        "action": action,
        "token": SHEETS_TOKEN,
        "searchId": SEARCH_ID
    }

    request_data.update(payload)

    encoded = json.dumps(
        request_data
    ).encode("utf-8")

    request = urllib.request.Request(
        SHEETS_API_URL,
        data=encoded,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request,
        timeout=60
    ) as response:

        response_text = response.read().decode(
            "utf-8",
            errors="replace"
        )

    print("\nGoogle Sheets response:")
    print(response_text)

    result = json.loads(response_text)

    if not result.get("success"):
        raise RuntimeError(
            result.get("message", "Google Sheets rejected the results.")
        )

    return result


# --------------------------------------------------
# 9. MAIN RESEARCH PROCESS
# --------------------------------------------------

def main():

    if not SEARCH_ID:
        raise RuntimeError(
            "Search ID missing. Workflow must pass INPUT_SEARCH_ID."
        )

    if not STATE and not CITY and not COUNTY and not ZIP_CODE:
        raise RuntimeError(
            "Please provide at least one location detail."
        )

    results = discover_public_sources()

    print("\n========== RESEARCH SUMMARY ==========")
    print("Unique public sources:", len(results))

    if not results:

        send_to_google_sheets(
            "updateTask",
            {
                "status": "No Results",
                "notes": (
                    "Research completed, but no recognized public "
                    "search results were returned. Search provider "
                    "may have limited or blocked the request."
                )
            }
        )

        print("No results returned. Queue updated.")
        return

    buyers = prepare_buyer_records(results)

    response = send_to_google_sheets(
        "saveBuyers",
        {
            "buyers": buyers,
            "sourceUrl": results[0]["url"]
        }
    )

    print("\n========== GOOGLE SHEETS RESULT ==========")

    print(
        "Saved:",
        response.get("results", {}).get("saved", 0)
    )

    print(
        "Duplicates:",
        response.get("results", {}).get("duplicates", 0)
    )

    print(
        "Errors:",
        response.get("results", {}).get("errors", 0)
    )

    print("\nMUSA research process finished.")


if __name__ == "__main__":
    main()
