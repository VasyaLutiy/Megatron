"""The GitHub REST client: the only module of the package that talks to
the network, stdlib urllib only.

Provides API_ROOT, parse_next_link, urllib_transport, GitHubError and
GitHubClient. Rate-limit awareness comes from megatron.api_manager:
parse_rate_limit and seconds_to_wait are imported, not reimplemented.
"""

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple

from megatron.api_manager import parse_rate_limit, seconds_to_wait

API_ROOT = "https://api.github.com"


def parse_next_link(link_header):
    # type: (Optional[str]) -> Optional[str]
    """Extract the rel="next" URL from a Link header value.

    Returns None for None, "" and a header with no rel="next" entry.
    """
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.strip()
        if not section.endswith('rel="next"'):
            continue
        url_part = section.split(";")[0].strip()
        if url_part.startswith("<") and url_part.endswith(">"):
            return url_part[1:-1]
    return None


def _lookup(headers, name):
    # type: (Dict[str, str], str) -> Optional[str]
    lowered = {key.lower(): value for key, value in headers.items()}
    return lowered.get(name.lower())


def urllib_transport(url, headers):
    # type: (str, Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]
    """Synchronous transport over urllib.request.

    Returns (status, response headers, body bytes). An HTTPError is
    returned as (e.code, dict(e.headers), e.read()), not raised.
    """
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=30)
        return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


class GitHubError(Exception):
    """Raised when the API answers with a status >= 400."""

    def __init__(self, message, status):
        # type: (str, int) -> None
        super(GitHubError, self).__init__(message)
        self.status = status


class GitHubClient:
    """Minimal async client for the GitHub REST v3 API.

    token=None reads GITHUB_TOKEN from the environment at construction.
    transport=None takes the module-level urllib_transport, also at
    construction. sleep=None is asyncio.sleep, clock=None is time.time.
    """

    def __init__(self, token=None, transport=None, sleep=None, clock=None,
                 max_pages=10):
        # type: (Optional[str], object, object, object, int) -> None
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self.transport = transport if transport is not None else urllib_transport
        self.sleep = sleep if sleep is not None else asyncio.sleep
        self.clock = clock if clock is not None else time.time
        self.max_pages = max_pages
        self.rate_limit = None  # type: Optional[Dict[str, int]]

    def _request_headers(self):
        # type: () -> Dict[str, str]
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "megatron",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        return headers

    async def fetch_json(self, path):
        # type: (str) -> object
        """Fetch path (or an absolute URL) and return the decoded JSON.

        A dict body is returned as is. A list body is followed along
        Link: rel="next" until no next link or max_pages pages were
        fetched; the pages are concatenated in page order.
        """
        url = path if path.startswith("http") else API_ROOT + path
        pages = 0
        collected = []  # type: list
        while True:
            wait = seconds_to_wait(self.rate_limit, int(self.clock()))
            if wait > 0:
                await self.sleep(wait)
            loop = asyncio.get_event_loop()
            status, resp_headers, body = await loop.run_in_executor(
                None, self.transport, url, self._request_headers())
            state = parse_rate_limit(resp_headers)
            if state is not None:
                self.rate_limit = state
            if status >= 400:
                raise GitHubError(
                    "HTTP %d for %s" % (status, url), status)
            data = json.loads(body.decode("utf-8"))
            pages += 1
            if not isinstance(data, list):
                return data
            collected.extend(data)
            if pages >= self.max_pages:
                return collected
            next_url = parse_next_link(_lookup(resp_headers, "link"))
            if next_url is None:
                return collected
            url = next_url
