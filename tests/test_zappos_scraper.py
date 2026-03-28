"""
test_zappos_scraper.py — Unit tests for ZapposScraper.

All HTTP calls are mocked — no network access or Zappos account needed.
Tests use representative HTML fragments that mirror Zappos' SSR output.

Run:
    pytest tests/test_zappos_scraper.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from src.scraper.base_scraper import ShoeData
from src.scraper.zappos import ZapposScraper


# ---------------------------------------------------------------------------
# Sample HTML fixtures — mirror real Zappos SSR output
# ---------------------------------------------------------------------------

PRODUCT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta property="og:title" content="Nike Air Max 90" />
  <meta property="og:description" content="A timeless classic Nike sneaker." />
  <meta property="og:image"
        content="https://img.zappos.com/images/nike-air-max-90_front.jpg" />
  <meta property="og:price:amount" content="89.95" />
</head>
<body>
  <h1>Nike Air Max 90</h1>
  <span itemprop="brand">Nike</span>
  <span itemprop="price" content="89.95">$89.95</span>
  <nav aria-label="breadcrumb">
    <a href="/">Home</a>
    <a href="/c/shoes">Shoes</a>
    <a href="/c/mens-running-shoes">Running</a>
  </nav>
  <div>
    <img src="https://img.zappos.com/images/nike-air-max-90_front.jpg"
         alt="front view" />
    <img src="https://img.zappos.com/images/nike-air-max-90_side.jpg"
         alt="side view" />
    <img src="https://img.zappos.com/images/nike-air-max-90_sole.jpg"
         alt="sole view" />
  </div>
</body>
</html>
"""

CATALOG_HTML = """
<html><body>
  <a href="/p/nike-air-max-90/product/8005382">Air Max 90</a>
  <a href="/p/adidas-ultraboost-22/product/7654321">Ultraboost 22</a>
  <a href="/p/new-balance-990v6/product/1122334">990v6</a>
  <a href="/other-link">Not a product link</a>
  <a href="/c/mens-running-shoes">Category link</a>
</body></html>
"""

CATALOG_HTML_NO_PRODUCTS = """
<html><body>
  <p>No results found.</p>
</body></html>
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scraper():
    """ZapposScraper with rate limiting disabled for fast unit tests."""
    return ZapposScraper(rate_limit_seconds=0.0, max_retries=2, timeout=5)


@pytest.fixture
def product_soup():
    """Parsed BeautifulSoup from PRODUCT_HTML."""
    return BeautifulSoup(PRODUCT_HTML, "lxml")


@pytest.fixture
def catalog_soup():
    """Parsed BeautifulSoup from CATALOG_HTML."""
    return BeautifulSoup(CATALOG_HTML, "lxml")


# ---------------------------------------------------------------------------
# Identity / property tests
# ---------------------------------------------------------------------------


class TestZappossScraperIdentity:
    def test_site_name(self, scraper):
        assert scraper.site_name == "zappos"

    def test_base_url(self, scraper):
        assert scraper.base_url == "https://www.zappos.com"


# ---------------------------------------------------------------------------
# _extract_product_id
# ---------------------------------------------------------------------------


class TestExtractProductId:
    def test_standard_url(self, scraper):
        url = "https://www.zappos.com/p/nike-air-max-90/product/8005382"
        assert scraper._extract_product_id(url) == "8005382"

    def test_short_url(self, scraper):
        url = "https://www.zappos.com/product/8005382"
        assert scraper._extract_product_id(url) == "8005382"

    def test_fallback_last_segment(self, scraper):
        url = "https://www.zappos.com/some/other/path/12345"
        assert scraper._extract_product_id(url) == "12345"


# ---------------------------------------------------------------------------
# _parse_price
# ---------------------------------------------------------------------------


class TestParsePrice:
    def test_dollar_sign(self, scraper):
        assert scraper._parse_price("$89.95") == 89.95

    def test_plain_number(self, scraper):
        assert scraper._parse_price("120") == 120.0

    def test_with_cents(self, scraper):
        assert scraper._parse_price("149.99") == 149.99

    def test_with_comma(self, scraper):
        assert scraper._parse_price("1,200.00") == 1200.0

    def test_none_on_garbage(self, scraper):
        assert scraper._parse_price("N/A") is None

    def test_none_on_empty(self, scraper):
        assert scraper._parse_price("") is None


# ---------------------------------------------------------------------------
# _upgrade_zappos_image_url
# ---------------------------------------------------------------------------


class TestUpgradeZappossImageUrl:
    def test_sr_token_replaced(self, scraper):
        url = "https://img.zappos.com/shoe.jpg?SR38,50"
        assert "SR600,600" in scraper._upgrade_zappos_image_url(url)

    def test_sx_token_replaced(self, scraper):
        url = "https://img.zappos.com/_SX90_shoe.jpg"
        assert "_SX600_" in scraper._upgrade_zappos_image_url(url)

    def test_dimension_token_replaced(self, scraper):
        url = "https://img.zappos.com/90x90/shoe.jpg"
        assert "600x600" in scraper._upgrade_zappos_image_url(url)

    def test_unchanged_if_no_tokens(self, scraper):
        url = "https://img.zappos.com/shoe-hires.jpg"
        assert scraper._upgrade_zappos_image_url(url) == url


# ---------------------------------------------------------------------------
# HTML extraction helpers
# ---------------------------------------------------------------------------


class TestExtractBrand:
    def test_from_itemprop(self, scraper, product_soup):
        assert scraper._extract_brand(product_soup) == "Nike"

    def test_fallback_unknown(self, scraper):
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        assert scraper._extract_brand(soup) == "Unknown"

    def test_from_data_brand(self, scraper):
        html = '<html><body><div data-brand="Adidas"></div></body></html>'
        soup = BeautifulSoup(html, "lxml")
        assert scraper._extract_brand(soup) == "Adidas"


class TestExtractModel:
    def test_strips_brand_prefix(self, scraper, product_soup):
        model = scraper._extract_model(product_soup, "Nike")
        assert model == "Air Max 90"

    def test_returns_full_h1_if_brand_unknown(self, scraper, product_soup):
        model = scraper._extract_model(product_soup, "Unknown")
        assert model == "Nike Air Max 90"

    def test_fallback_og_title(self, scraper):
        html = """
        <html><head>
          <meta property="og:title" content="Adidas Ultraboost 22" />
        </head></html>
        """
        soup = BeautifulSoup(html, "lxml")
        assert scraper._extract_model(soup, "Adidas") == "Ultraboost 22"


class TestExtractPrice:
    def test_from_itemprop(self, scraper, product_soup):
        assert scraper._extract_price(product_soup) == 89.95

    def test_from_og_price(self, scraper):
        html = """
        <html><head>
          <meta property="og:price:amount" content="129.95" />
        </head></html>
        """
        soup = BeautifulSoup(html, "lxml")
        assert scraper._extract_price(soup) == 129.95

    def test_none_when_missing(self, scraper):
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        assert scraper._extract_price(soup) is None


class TestExtractDescription:
    def test_from_og_description(self, scraper, product_soup):
        desc = scraper._extract_description(product_soup)
        assert "classic" in desc.lower()

    def test_empty_when_missing(self, scraper):
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        assert scraper._extract_description(soup) == ""


class TestExtractImageUrls:
    def test_returns_list(self, scraper, product_soup):
        urls = scraper._extract_image_urls(product_soup)
        assert isinstance(urls, list)
        assert len(urls) >= 1

    def test_all_urls_from_zappos_domain(self, scraper, product_soup):
        urls = scraper._extract_image_urls(product_soup)
        assert all("zappos" in u for u in urls)

    def test_no_duplicates(self, scraper, product_soup):
        urls = scraper._extract_image_urls(product_soup)
        assert len(urls) == len(set(urls))


class TestExtractGender:
    def test_mens_from_url(self, scraper, product_soup):
        result = scraper._extract_gender(
            product_soup,
            "https://www.zappos.com/c/mens-running-shoes",
        )
        assert result == "mens"

    def test_womens_from_url(self, scraper, product_soup):
        result = scraper._extract_gender(
            product_soup,
            "https://www.zappos.com/c/womens-sneakers",
        )
        assert result == "womens"

    def test_kids_from_url(self, scraper, product_soup):
        result = scraper._extract_gender(
            product_soup,
            "https://www.zappos.com/c/kids-shoes",
        )
        assert result == "kids"

    def test_unisex_fallback(self, scraper):
        soup = BeautifulSoup("<html></html>", "lxml")
        result = scraper._extract_gender(
            soup,
            "https://www.zappos.com/p/some-shoe/product/123",
        )
        assert result == "unisex"


class TestExtractCategory:
    def test_from_breadcrumb(self, scraper, product_soup):
        category = scraper._extract_category(product_soup)
        assert category == "running"

    def test_empty_when_no_breadcrumb(self, scraper):
        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        assert scraper._extract_category(soup) == ""


# ---------------------------------------------------------------------------
# Catalog URL extraction
# ---------------------------------------------------------------------------


class TestExtractCatalogProductUrls:
    def test_finds_all_product_links(self, scraper, catalog_soup):
        urls = scraper._extract_catalog_product_urls(catalog_soup)
        assert len(urls) == 3

    def test_all_urls_are_absolute(self, scraper, catalog_soup):
        urls = scraper._extract_catalog_product_urls(catalog_soup)
        assert all(u.startswith("https://www.zappos.com") for u in urls)

    def test_no_duplicates(self, scraper, catalog_soup):
        urls = scraper._extract_catalog_product_urls(catalog_soup)
        assert len(urls) == len(set(urls))

    def test_returns_empty_for_no_products(self, scraper):
        soup = BeautifulSoup(CATALOG_HTML_NO_PRODUCTS, "lxml")
        urls = scraper._extract_catalog_product_urls(soup)
        assert urls == []

    def test_non_product_links_excluded(self, scraper, catalog_soup):
        urls = scraper._extract_catalog_product_urls(catalog_soup)
        assert not any("/c/" in u for u in urls), (
            "Category links should not appear in product URL list"
        )


# ---------------------------------------------------------------------------
# scrape_product (mocked fetch_html)
# ---------------------------------------------------------------------------


class TestScrapeProduct:
    @patch.object(ZapposScraper, "fetch_html")
    def test_returns_shoe_data(self, mock_fetch, scraper, product_soup):
        mock_fetch.return_value = product_soup
        data = scraper.scrape_product(
            "https://www.zappos.com/p/nike-air-max-90/product/8005382"
        )
        assert isinstance(data, ShoeData)
        assert data.brand == "Nike"
        assert data.external_id == "8005382"
        assert data.external_site == "zappos"
        assert data.price == 89.95
        assert len(data.image_urls) >= 1
        assert data.product_url == (
            "https://www.zappos.com/p/nike-air-max-90/product/8005382"
        )

    @patch.object(ZapposScraper, "fetch_html")
    def test_raises_on_fetch_failure(self, mock_fetch, scraper):
        mock_fetch.return_value = None
        with pytest.raises(RuntimeError, match="Failed to fetch"):
            scraper.scrape_product(
                "https://www.zappos.com/p/missing/product/999"
            )


# ---------------------------------------------------------------------------
# get_catalog_urls (mocked fetch_html)
# ---------------------------------------------------------------------------


class TestGetCatalogUrls:
    @patch.object(ZapposScraper, "fetch_html")
    def test_returns_product_urls(self, mock_fetch, scraper, catalog_soup):
        mock_fetch.return_value = catalog_soup
        urls = scraper.get_catalog_urls(
            "https://www.zappos.com/c/mens-running-shoes", max_pages=1
        )
        assert len(urls) == 3
        assert all("zappos.com" in u for u in urls)

    @patch.object(ZapposScraper, "fetch_html")
    def test_returns_empty_on_fetch_failure(self, mock_fetch, scraper):
        mock_fetch.return_value = None
        urls = scraper.get_catalog_urls(
            "https://www.zappos.com/c/shoes", max_pages=1
        )
        assert urls == []

    @patch.object(ZapposScraper, "fetch_html")
    def test_deduplicates_across_pages(self, mock_fetch, scraper, catalog_soup):
        """When the same products appear on multiple pages, deduplicate them."""
        # Return the same catalog HTML for both pages
        mock_fetch.return_value = catalog_soup
        # With max_pages=2 and the same HTML returned for both pages,
        # we expect the products to appear only once
        urls = scraper.get_catalog_urls(
            "https://www.zappos.com/c/shoes", max_pages=2
        )
        assert len(urls) == len(set(urls)), "URLs should be deduplicated"
