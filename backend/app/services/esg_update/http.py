"""Tiny stdlib HTTP helper (safe ESG external fetcher)."""
import os
import urllib.request
import urllib.error
from urllib.parse import urlparse

UA = "UrbanPulse-ESG-Updater/1.0 (+civic transparency project)"
ALLOWED_HOSTS = {"data.opencity.in", "data.gov.in"}
MAX_BYTES = 5 * 1024 * 1024  # Cap response at 5 MB


class UpdateError(Exception):
    """A source could not be fetched/understood. The job is logged as failed and NO data is written."""


def validate_esg_url(url: str) -> None:
    """Validate that the URL is https and only from permitted hosts data.opencity.in or data.gov.in.
    During automated testing (PYTEST_CURRENT_TEST set), local mock endpoints (127.0.0.1/localhost) are permitted.
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise UpdateError(f"Malformed URL: {url}") from e

    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").lower()

    # Allow local mock in test runner
    if os.environ.get("PYTEST_CURRENT_TEST") and hostname in {"127.0.0.1", "localhost"}:
        return

    if scheme != "https":
        raise UpdateError(f"Insecure protocol '{parsed.scheme}': only https is allowed for ESG fetches")

    if hostname not in ALLOWED_HOSTS:
        raise UpdateError(f"Host '{hostname}' is not permitted. Only {ALLOWED_HOSTS} are allowed.")


def fetch(url: str, timeout: int = 30, method: str = "GET") -> bytes:
    validate_esg_url(url)

    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            # Read at most MAX_BYTES + 1 to detect overflow
            content = r.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise UpdateError(f"Response size from {url.split('?')[0]} exceeded limit of 5 MB")
            return content
    except urllib.error.HTTPError as e:
        raise UpdateError(f"HTTP {e.code} from {url.split('?')[0]}") from e
    except UpdateError:
        raise
    except Exception as e:  # DNS, timeout, TLS ...
        raise UpdateError(f"{type(e).__name__}: {e} ({url.split('?')[0]})") from e
