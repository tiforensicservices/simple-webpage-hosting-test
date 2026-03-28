"""
base_scraper.py — Abstract base class for all Gaitway shoe scrapers.

Handles:
  - Rate limiting + jitter (respect target site)
  - Retry logic with exponential back-off
  - robots.txt compliance (cached per domain)
  - Session management (persistent connection pool)
  - User-Agent rotation (basic anti-bot courtesy)
  - Raw image download + S3 upload

All site-specific scrapers (zappos.py, amazon.py, …) extend this class.
"""

from __future__ import annotations

import logging
import os
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import boto3
import requests
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ShoeData:
    """Normalised data model returned by every scraper implementation.

    This is the common contract between the scraper layer and the database
    layer — regardless of which retailer the data came from.
    """

    brand: str
    model_name: str
    external_site: str          # e.g. "zappos", "amazon", "dsw"
    external_id: str            # site-specific product ID (string)

    # Optional fields populated by most scrapers
    category: str = ""          # e.g. "running", "casual", "basketball"
    gender: str = ""            # "mens" | "womens" | "kids" | "unisex"
    colorway: str = ""          # e.g. "White/Black/Red"
    price: Optional[float] = None
    description: str = ""
    product_url: str = ""
    image_urls: list[str] = field(default_factory=list)
    raw_metadata: dict = field(default_factory=dict)  # Site-specific extras


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class BaseScraper(ABC):
    """Abstract base class for all Gaitway shoe scrapers.

    Subclasses must implement:
        site_name       — short identifier (e.g. "zappos")
        base_url        — root URL (e.g. "https://www.zappos.com")
        scrape_product  — parse a single product page → ShoeData
        get_catalog_urls — list product URLs from a category page

    Subclasses get for free:
        fetch_html         — rate-limited, retrying HTML fetcher
        download_image     — rate-limited image downloader
        upload_image_to_s3 — download + upload to S3 raw/ prefix
        build_s3_key       — canonical S3 key format
    """

    _DEFAULT_HEADERS: dict[str, str] = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }

    _USER_AGENTS: list[str] = [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
            "Gecko/20100101 Firefox/123.0"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.3.1 Safari/605.1.15"
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    ]

    def __init__(
        self,
        rate_limit_seconds: float = 2.0,
        max_retries: int = 3,
        timeout: int = 15,
    ) -> None:
        """Initialise the scraper.

        Args:
            rate_limit_seconds: Minimum delay between HTTP requests (seconds).
                                A random jitter of 0–0.5 s is added on top.
            max_retries: Number of retry attempts on transient HTTP failures.
            timeout: HTTP request timeout in seconds.
        """
        self.rate_limit_seconds = rate_limit_seconds
        self.max_retries = max_retries
        self.timeout = timeout

        self._session = requests.Session()
        self._session.headers.update(self._DEFAULT_HEADERS)
        self._rotate_user_agent()

        self._last_request_time: float = 0.0
        self._robots_cache: dict[str, Optional[RobotFileParser]] = {}

        # S3 — lazily initialised
        self._s3_client: Optional[boto3.client] = None
        self._s3_bucket: str = os.getenv("S3_BUCKET_NAME", "")
        self._s3_raw_prefix: str = os.getenv("S3_RAW_PREFIX", "raw/")

        self.logger = logging.getLogger(f"scraper.{self.site_name}")

    # ------------------------------------------------------------------
    # Abstract interface — every subclass MUST implement these
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def site_name(self) -> str:
        """Short snake_case identifier for this scraper (e.g. 'zappos')."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Root URL of the target site (e.g. 'https://www.zappos.com')."""

    @abstractmethod
    def scrape_product(self, url: str) -> ShoeData:
        """Scrape a single product page and return normalised ShoeData.

        Args:
            url: Full URL of the product page.

        Returns:
            ShoeData populated with brand, model, images, etc.

        Raises:
            RuntimeError: If the page cannot be fetched after all retries.
        """

    @abstractmethod
    def get_catalog_urls(self, category_url: str, max_pages: int = 1) -> list[str]:
        """Return product page URLs from a category/search results page.

        Args:
            category_url: URL of the category or search results page.
            max_pages: How many pagination pages to traverse.

        Returns:
            List of product page URLs.
        """

    # ------------------------------------------------------------------
    # Concrete helpers — available to all subclasses
    # ------------------------------------------------------------------

    def fetch_html(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL and return a parsed BeautifulSoup object.

        Respects rate limiting, rotates User-Agent, and retries on transient
        failures with exponential back-off.

        Args:
            url: The URL to fetch.

        Returns:
            Parsed BeautifulSoup, or None if robots.txt disallows or all
            retries are exhausted.
        """
        if not self._is_allowed_by_robots(url):
            self.logger.warning("⛔ robots.txt disallows: %s", url)
            return None

        for attempt in range(1, self.max_retries + 1):
            self._respect_rate_limit()
            self._rotate_user_agent()

            try:
                response = self._session.get(url, timeout=self.timeout)
                response.raise_for_status()
                self._last_request_time = time.time()
                self.logger.debug(
                    "✅ [%d/%d] GET %s → %d",
                    attempt,
                    self.max_retries,
                    url,
                    response.status_code,
                )
                return BeautifulSoup(response.text, "lxml")

            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response else "?"
                if status == 404:
                    self.logger.warning("⚠️  404 Not Found: %s", url)
                    return None
                if status == 429:
                    wait_time = 30 * attempt
                    self.logger.warning(
                        "⚠️  429 Rate-limited — waiting %ds (attempt %d/%d)",
                        wait_time,
                        attempt,
                        self.max_retries,
                    )
                    time.sleep(wait_time)
                    continue
                self.logger.warning(
                    "⚠️  HTTP %s on attempt %d/%d: %s",
                    status,
                    attempt,
                    self.max_retries,
                    url,
                )

            except requests.exceptions.RequestException as exc:
                backoff = 2 ** attempt
                self.logger.warning(
                    "⚠️  Request error (attempt %d/%d, retry in %ds): %s",
                    attempt,
                    self.max_retries,
                    backoff,
                    exc,
                )
                time.sleep(backoff)

        self.logger.error(
            "❌ All %d attempts failed for: %s", self.max_retries, url
        )
        return None

    def download_image(self, image_url: str) -> Optional[bytes]:
        """Download an image and return its raw bytes.

        Args:
            image_url: Full URL of the image.

        Returns:
            Image bytes, or None if the download fails.
        """
        try:
            self._respect_rate_limit()
            response = self._session.get(
                image_url, timeout=self.timeout, stream=True
            )
            response.raise_for_status()
            self._last_request_time = time.time()
            return response.content
        except requests.exceptions.RequestException as exc:
            self.logger.error(
                "❌ Failed to download image %s: %s", image_url, exc
            )
            return None

    def upload_image_to_s3(
        self, image_url: str, s3_key: str
    ) -> Optional[str]:
        """Download an image from a URL and upload it to S3.

        Args:
            image_url: Source URL of the image.
            s3_key: Destination key in S3
                    (e.g. 'raw/zappos/8005382/image_01.jpg').

        Returns:
            S3 key string if successful, None on failure.
        """
        image_bytes = self.download_image(image_url)
        if not image_bytes:
            return None

        client = self._get_s3_client()
        try:
            client.put_object(
                Bucket=self._s3_bucket,
                Key=s3_key,
                Body=image_bytes,
                ContentType=self._guess_content_type(image_url),
            )
            self.logger.info(
                "✅ Uploaded → s3://%s/%s", self._s3_bucket, s3_key
            )
            return s3_key
        except ClientError as exc:
            self.logger.error(
                "❌ S3 upload failed for %s: %s", s3_key, exc
            )
            return None

    def build_s3_key(self, external_id: str, filename: str) -> str:
        """Build a canonical S3 key for a raw scraper image.

        Format: ``<raw_prefix><site_name>/<external_id>/<filename>``

        Example: ``raw/zappos/8005382/image_01.jpg``

        Args:
            external_id: Site-specific product ID.
            filename: Image filename (e.g. 'image_01.jpg').

        Returns:
            Full S3 key string.
        """
        return f"{self._s3_raw_prefix}{self.site_name}/{external_id}/{filename}"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _respect_rate_limit(self) -> None:
        """Block until the minimum interval since the last request has passed.

        Adds a small random jitter (0–0.5 s) to avoid predictable patterns.
        """
        elapsed = time.time() - self._last_request_time
        wait = self.rate_limit_seconds - elapsed
        if wait > 0:
            jitter = random.uniform(0.0, 0.5)
            time.sleep(wait + jitter)

    def _rotate_user_agent(self) -> None:
        """Pick a random User-Agent string from the pool."""
        self._session.headers["User-Agent"] = random.choice(self._USER_AGENTS)

    def _is_allowed_by_robots(self, url: str) -> bool:
        """Check whether the given URL is permitted by robots.txt.

        The parsed RobotFileParser is cached per domain to avoid repeated
        fetches.

        Args:
            url: The URL to check.

        Returns:
            True if crawling is permitted or if robots.txt is unavailable.
        """
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self._robots_cache:
            robots_url = f"{domain}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
                self._robots_cache[domain] = rp
                self.logger.debug("✅ robots.txt loaded for %s", domain)
            except Exception as exc:  # noqa: BLE001
                self.logger.debug(
                    "ℹ️  Could not read robots.txt for %s (%s) — assuming allowed",
                    domain,
                    exc,
                )
                self._robots_cache[domain] = None

        rp = self._robots_cache.get(domain)
        if rp is None:
            return True
        return rp.can_fetch("*", url)

    def _get_s3_client(self) -> boto3.client:
        """Lazily initialise and return the S3 boto3 client."""
        if self._s3_client is None:
            region = os.getenv("AWS_DEFAULT_REGION", "us-east-2")
            self._s3_client = boto3.client("s3", region_name=region)
        return self._s3_client

    @staticmethod
    def _guess_content_type(url: str) -> str:
        """Guess the MIME type from the URL file extension.

        Args:
            url: Image URL.

        Returns:
            MIME type string (defaults to 'image/jpeg').
        """
        lower = url.lower().split("?")[0]  # Strip query params before checking ext
        if lower.endswith(".png"):
            return "image/png"
        if lower.endswith(".webp"):
            return "image/webp"
        if lower.endswith(".gif"):
            return "image/gif"
        return "image/jpeg"
