"""Download raw GST Council documents (HTML & PDF) into data/raw/."""

import logging
from pathlib import Path
from typing import Dict, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

SOURCES: List[Dict[str, str]] = [
    {
        "name": "gst_council_faq_page0.html",
        "url": "https://gstcouncil.gov.in/en/faq?page=0",
        "document": "GST Council Official FAQs (Page 0)",
    },
    {
        "name": "56th_council_pib_press_release.pdf",
        "url": "https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf",
        "document": "56th GST Council Meeting PIB Press Release (Sept 2025)",
    },
    {
        "name": "gst_council_faq_page1.html",
        "url": "https://gstcouncil.gov.in/en/faq?page=1",
        "document": "GST Council Official FAQs (Page 1)",
    },
    {
        "name": "gst_council_faq_page2.html",
        "url": "https://gstcouncil.gov.in/en/faq?page=2",
        "document": "GST Council Official FAQs (Page 2)",
    },
]


def _build_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
    )
    return session


def download_file(
    session: requests.Session,
    url: str,
    dest_path: Path,
    timeout: tuple = (10, 30),
) -> bool:
    """Download a single URL to dest_path with connect/read timeouts and error handling."""
    try:
        logger.info("Fetching %s ...", url)
        response = session.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        size_kb = dest_path.stat().st_size / 1024
        logger.info("Saved %s (%.1f KB)", dest_path.name, size_kb)
        return True

    except requests.exceptions.Timeout:
        logger.error("Timeout while downloading %s", url)
    except requests.exceptions.HTTPError as exc:
        logger.error("HTTP error %s for %s", exc.response.status_code if exc.response else "unknown", url)
    except requests.exceptions.ConnectionError as exc:
        logger.error("Connection error for %s: %s", url, exc)
    except requests.exceptions.RequestException as exc:
        logger.error("Request failed for %s: %s", url, exc)
    except OSError as exc:
        logger.error("File write error for %s: %s", dest_path, exc)

    return False


def fetch_all(sources: List[Dict[str, str]] = SOURCES) -> Dict[str, bool]:
    """Download all configured GST Council documents into data/raw/."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = _build_session()
    results: Dict[str, bool] = {}

    for src in sources:
        dest = RAW_DIR / src["name"]
        ok = download_file(session, src["url"], dest)
        results[src["name"]] = ok

    succeeded = sum(1 for v in results.values() if v)
    logger.info("Fetch complete: %d/%d files downloaded successfully.", succeeded, len(results))
    return results


if __name__ == "__main__":
    fetch_all()
