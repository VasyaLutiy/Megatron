"""Discovery of logins through the GitHub user-search endpoint.

encode_query percent-encodes a search query the way GitHub writes it in
its own Link headers. search_url builds the first page URL of a user
search. parse_search_page reads one search-response body.
discover_logins walks pages through the client, following Link: rel="next"
verbatim, and concatenates the logins in API order.

No network library is imported here: the module talks to the API only
through the GitHubClient it is given.
"""

from typing import Dict, List

from megatron.github_client import API_ROOT, parse_next_link

_UNRESERVED = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


def encode_query(query):
    # type: (str) -> str
    """Percent-encode the UTF-8 bytes of query.

    A-Z a-z 0-9 - . _ ~ are kept; every other byte becomes %XX with
    upper-case hex.
    """
    out = []
    for byte in query.encode("utf-8"):
        char = chr(byte)
        if char in _UNRESERVED:
            out.append(char)
        else:
            out.append("%%%02X" % byte)
    return "".join(out)


def search_url(query, per_page=30):
    # type: (str, int) -> str
    """Return the first-page URL of a user search."""
    return (
        API_ROOT + "/search/users?q=" + encode_query(query)
        + "&per_page=" + str(per_page)
    )


def parse_search_page(data):
    # type: (Dict) -> Dict
    """Read one search-response body into logins and totals."""
    return {
        "logins": [item["login"] for item in data["items"]],
        "total_count": data["total_count"],
        "incomplete_results": bool(data["incomplete_results"]),
    }


async def discover_logins(client, query, pages, per_page=30):
    # type: (object, str, int, int) -> Dict[str, object]
    """Fetch up to pages of a user search and collect the logins.

    The first URL is search_url(query, per_page); every next URL is the
    rel="next" of the previous response's Link header, verbatim. The
    client's transport is wrapped for the duration of the call so the
    Link header of each response can be seen; the original transport is
    restored in finally, also when an error propagates.
    """
    if pages < 1:
        raise ValueError("pages must be >= 1, got %r" % (pages,))
    original = client.transport  # type: object
    stored = {"link": None}  # type: Dict[str, object]

    def wrapper(url, headers):
        # type: (str, Dict[str, str]) -> tuple
        status, resp_headers, body = original(url, headers)
        lowered = {
            key.lower(): value for key, value in resp_headers.items()
        }
        stored["link"] = lowered.get("link")
        return status, resp_headers, body

    client.transport = wrapper
    try:
        logins = []  # type: List[str]
        total_count = None  # type: object
        incomplete_results = False
        fetched = 0
        url = search_url(query, per_page)
        while fetched < pages:
            data = await client.fetch_json(url)
            page = parse_search_page(data)
            if total_count is None:
                total_count = page["total_count"]
            logins.extend(page["logins"])
            if page["incomplete_results"]:
                incomplete_results = True
            fetched += 1
            if fetched >= pages:
                break
            next_url = parse_next_link(stored["link"])
            if next_url is None:
                break
            url = next_url
        return {
            "logins": logins,
            "total_count": total_count,
            "incomplete_results": incomplete_results,
            "pages": fetched,
        }
    finally:
        client.transport = original
