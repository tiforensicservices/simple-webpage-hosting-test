"""
test_base_scraper.py — Unit tests for BaseScraper.

All HTTP calls are mocked — no real network requests are made.
A ConcreteTestScraper subclass is used to exercise the abstract base class.

Run:
    pytest tests/test_base_scraper.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.scraper.base_scraper import BaseScraper, ShoeData


# ---------------------------------------------------------------------------
# Minimal concrete subclass for testing the abstract base
# ---------------------------------------------------------------------------


class ConcreteTestScraper(BaseScraper):
    """Minimal BaseScraper subclass used only in tests."""

    @property
    def site_name(self) -> str:
        return "test-site"

    @property
    def base_url(self) -> str:
        return "https://www.test-site.com"

    def scrape_product(self, url: str) -> ShoeData:
        return ShoeData(
            brand="TestBrand",
            model_name="TestModel",
            external_site=self.site_name,
            external_id="123",
        )

    def get_catalog_urls(
        self, category_url: str, max_pages: int = 1
    ) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scraper():
    """ConcreteTestScraper with rate limiting disabled for fast tests."""
    return ConcreteTestScraper(
        rate_limit_seconds=0.0,
        max_retries=2,
        timeout=5,
    )


def _make_200_response(html: str) -> MagicMock:
    """Return a mock 200 response with the given HTML body."""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = html
    resp.raise_for_status = MagicMock()  # No-op — does not raise
    return resp


def _make_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Return an HTTPError wrapping a mock response with the given status."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    err = requests.exceptions.HTTPError(response=mock_resp)
    return err


# ---------------------------------------------------------------------------
# ShoeData tests
# ---------------------------------------------------------------------------


class TestShoeData:
    def test_required_fields(self):
        sd = ShoeData(
            brand="Nike",
            model_name="Air Max",
            external_site="zappos",
            external_id="123",
        )
        assert sd.brand == "Nike"
        assert sd.model_name == "Air Max"
        assert sd.external_site == "zappos"
        assert sd.external_id == "123"

    def test_optional_field_defaults(self):
        sd = ShoeData(
            brand="Nike", model_name="Air Max",
            external_site="zappos", external_id="123",
        )
        assert sd.category == ""
        assert sd.gender == ""
        assert sd.colorway == ""
        assert sd.price is None
        assert sd.description == ""
        assert sd.product_url == ""
        assert sd.image_urls == []
        assert sd.raw_metadata == {}

    def test_optional_fields_set(self):
        sd = ShoeData(
            brand="Adidas",
            model_name="Ultraboost 22",
            external_site="zappos",
            external_id="999",
            price=149.95,
            gender="mens",
            colorway="Core Black/White",
            image_urls=["https://example.com/img.jpg"],
        )
        assert sd.price == 149.95
        assert sd.gender == "mens"
        assert len(sd.image_urls) == 1

    def test_image_urls_list_not_shared(self):
        """Each ShoeData instance should have its own list."""
        sd1 = ShoeData(brand="A", model_name="M", external_site="s", external_id="1")
        sd2 = ShoeData(brand="B", model_name="N", external_site="s", external_id="2")
        sd1.image_urls.append("http://example.com/1.jpg")
        assert sd2.image_urls == [], "image_urls lists should not be shared between instances"


# ---------------------------------------------------------------------------
# BaseScraper property tests
# ---------------------------------------------------------------------------


class TestBaseScraper:
    def test_site_name(self, scraper):
        assert scraper.site_name == "test-site"

    def test_base_url(self, scraper):
        assert scraper.base_url == "https://www.test-site.com"

    def test_rate_limit_default(self):
        s = ConcreteTestScraper()
        assert s.rate_limit_seconds == 2.0

    def test_max_retries_default(self):
        s = ConcreteTestScraper()
        assert s.max_retries == 3


# ---------------------------------------------------------------------------
# build_s3_key tests
# ---------------------------------------------------------------------------


class TestBuildS3Key:
    def test_default_prefix(self, scraper):
        key = scraper.build_s3_key("shoe123", "image_01.jpg")
        assert key == "raw/test-site/shoe123/image_01.jpg"

    def test_custom_prefix(self, scraper, monkeypatch):
        monkeypatch.setenv("S3_RAW_PREFIX", "raw-images/")
        scraper._s3_raw_prefix = "raw-images/"
        key = scraper.build_s3_key("shoe123", "image_01.jpg")
        assert key == "raw-images/test-site/shoe123/image_01.jpg"

    def test_key_contains_site_name(self, scraper):
        key = scraper.build_s3_key("42", "front.jpg")
        assert "test-site" in key

    def test_key_contains_external_id(self, scraper):
        key = scraper.build_s3_key("abc-999", "sole.png")
        assert "abc-999" in key


# ---------------------------------------------------------------------------
# _guess_content_type tests
# ---------------------------------------------------------------------------


class TestGuessContentType:
    def test_jpeg(self):
        assert BaseScraper._guess_content_type("http://x.com/img.jpg") == "image/jpeg"

    def test_jpeg_uppercase(self):
        assert BaseScraper._guess_content_type("http://x.com/IMG.JPG") == "image/jpeg"

    def test_png(self):
        assert BaseScraper._guess_content_type("http://x.com/img.png") == "image/png"

    def test_webp(self):
        assert BaseScraper._guess_content_type("http://x.com/img.webp") == "image/webp"

    def test_gif(self):
        assert BaseScraper._guess_content_type("http://x.com/img.gif") == "image/gif"

    def test_unknown_defaults_to_jpeg(self):
        assert BaseScraper._guess_content_type("http://x.com/image") == "image/jpeg"

    def test_strips_query_params(self):
        # URL has a .png but with query params that shouldn't affect detection
        assert BaseScraper._guess_content_type(
            "http://x.com/img.png?size=large"
        ) == "image/png"


# ---------------------------------------------------------------------------
# fetch_html tests
# ---------------------------------------------------------------------------


class TestFetchHtml:
    @patch("requests.Session.get")
    def test_returns_soup_on_success(self, mock_get, scraper):
        mock_get.return_value = _make_200_response(
            "<html><body><h1>Hello</h1></body></html>"
        )
        with patch.object(scraper, "_is_allowed_by_robots", return_value=True):
            soup = scraper.fetch_html("https://www.test-site.com/product/1")
        assert soup is not None
        assert soup.find("h1").text == "Hello"

    def test_returns_none_if_robots_disallows(self, scraper):
        with patch.object(scraper, "_is_allowed_by_robots", return_value=False):
            result = scraper.fetch_html("https://www.test-site.com/private")
        assert result is None

    @patch("requests.Session.get")
    def test_returns_none_on_404(self, mock_get, scraper):
        err = _make_http_error(404)
        mock_get.return_value.raise_for_status.side_effect = err
        with patch.object(scraper, "_is_allowed_by_robots", return_value=True):
            result = scraper.fetch_html("https://www.test-site.com/gone")
        assert result is None

    @patch("requests.Session.get")
    def test_retries_on_500(self, mock_get, scraper):
        """Should retry on 5xx errors (up to max_retries)."""
        err = _make_http_error(500)
        mock_get.return_value.raise_for_status.side_effect = err
        with patch.object(scraper, "_is_allowed_by_robots", return_value=True):
            result = scraper.fetch_html("https://www.test-site.com/error")
        assert result is None
        assert mock_get.call_count == scraper.max_retries

    @patch("requests.Session.get")
    def test_retries_on_connection_error(self, mock_get, scraper):
        """Should retry on network errors with exponential back-off."""
        mock_get.side_effect = requests.exceptions.ConnectionError("timeout")
        with (
            patch.object(scraper, "_is_allowed_by_robots", return_value=True),
            patch("time.sleep"),  # Don't actually sleep in tests
        ):
            result = scraper.fetch_html("https://www.test-site.com/slow")
        assert result is None
        assert mock_get.call_count == scraper.max_retries


# ---------------------------------------------------------------------------
# download_image tests
# ---------------------------------------------------------------------------


class TestDownloadImage:
    @patch("requests.Session.get")
    def test_returns_bytes_on_success(self, mock_get, scraper):
        resp = MagicMock()
        resp.content = b"\xff\xd8\xff\xe0"  # JPEG magic bytes
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp
        result = scraper.download_image("https://www.test-site.com/img.jpg")
        assert result == b"\xff\xd8\xff\xe0"

    @patch("requests.Session.get")
    def test_returns_none_on_network_error(self, mock_get, scraper):
        mock_get.side_effect = requests.exceptions.ConnectionError("no route")
        result = scraper.download_image("https://www.test-site.com/img.jpg")
        assert result is None

    @patch("requests.Session.get")
    def test_returns_none_on_http_error(self, mock_get, scraper):
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=MagicMock(status_code=403)
        )
        mock_get.return_value = resp
        result = scraper.download_image("https://www.test-site.com/forbidden.jpg")
        assert result is None


# ---------------------------------------------------------------------------
# scrape_product / get_catalog_urls delegation tests
# ---------------------------------------------------------------------------


class TestConcreteImplementation:
    def test_scrape_product_returns_shoe_data(self, scraper):
        data = scraper.scrape_product("https://www.test-site.com/p/1")
        assert isinstance(data, ShoeData)
        assert data.brand == "TestBrand"
        assert data.external_site == "test-site"
        assert data.external_id == "123"

    def test_get_catalog_urls_returns_list(self, scraper):
        urls = scraper.get_catalog_urls("https://www.test-site.com/c/shoes")
        assert isinstance(urls, list)
