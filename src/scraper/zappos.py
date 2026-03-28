"""
zappos.py — Scraper implementation for Zappos.com.

Zappos is a major footwear retailer (owned by Amazon) with a well-structured
product pages and consistent HTML markup.

Product URL format:
  https://www.zappos.com/p/<brand-model-slug>/product/<product_id>

Catalog URL format:
  https://www.zappos.com/c/<category-slug>          (e.g. mens-running-shoes)
  https://www.zappos.com/c/<category-slug>?p=<N>    (paginated)

Images are served from img.zappos.com and available in multiple sizes.
We upgrade thumbnail tokens to request the largest available version.

NOTE: Zappos renders some data via JavaScript. The selectors here target
the server-side rendered HTML (SSR) which includes essential product data
in meta tags and structured data even before JS executes. If Zappos changes
their SSR output, update the fallback selectors in each _extract_* method.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.scraper.base_scraper import BaseScraper, ShoeData


class ZapposScraper(BaseScraper):
    """Scraper for Zappos.com shoe listings.

    Implements the full BaseScraper interface for Zappos.
    Rate limit default: 2 s between requests (Zappos terms of service).
    """

    @property
    def site_name(self) -> str:
        return "zappos"

    @property
    def base_url(self) -> str:
        return "https://www.zappos.com"

    # ------------------------------------------------------------------
    # Core abstract method implementations
    # ------------------------------------------------------------------

    def scrape_product(self, url: str) -> ShoeData:
        """Scrape a single Zappos product page.

        Args:
            url: Full Zappos product URL, e.g.:
                 https://www.zappos.com/p/nike-air-max-90/product/8005382

        Returns:
            ShoeData populated from the page.

        Raises:
            RuntimeError: If the page cannot be fetched.
        """
        self.logger.info("🔍 Scraping product: %s", url)
        soup = self.fetch_html(url)
        if soup is None:
            raise RuntimeError(f"Failed to fetch Zappos product page: {url}")

        external_id = self._extract_product_id(url)
        brand = self._extract_brand(soup)

        return ShoeData(
            brand=brand,
            model_name=self._extract_model(soup, brand),
            external_site=self.site_name,
            external_id=external_id,
            category=self._extract_category(soup),
            gender=self._extract_gender(soup, url),
            colorway=self._extract_colorway(soup),
            price=self._extract_price(soup),
            description=self._extract_description(soup),
            product_url=url,
            image_urls=self._extract_image_urls(soup),
            raw_metadata={"source_url": url, "scraper": self.site_name},
        )

    def get_catalog_urls(
        self, category_url: str, max_pages: int = 1
    ) -> list[str]:
        """Return product URLs from a Zappos category page.

        Handles Zappos' ?p=N pagination automatically.

        Args:
            category_url: e.g. https://www.zappos.com/c/mens-running-shoes
            max_pages: How many result pages to traverse (default 1).

        Returns:
            Deduplicated list of product page URLs.
        """
        product_urls: list[str] = []
        seen: set[str] = set()
        current_url = category_url

        for page_num in range(1, max_pages + 1):
            self.logger.info(
                "📄 Fetching catalog page %d/%d: %s",
                page_num,
                max_pages,
                current_url,
            )
            soup = self.fetch_html(current_url)
            if soup is None:
                self.logger.warning(
                    "⚠️  Could not fetch catalog page %d — stopping.", page_num
                )
                break

            page_urls = self._extract_catalog_product_urls(soup)
            new_urls = [u for u in page_urls if u not in seen]
            product_urls.extend(new_urls)
            seen.update(new_urls)

            self.logger.info(
                "   Found %d new products on page %d (total: %d)",
                len(new_urls),
                page_num,
                len(product_urls),
            )

            if page_num < max_pages:
                next_url = self._find_next_page_url(
                    soup, current_url, page_num + 1
                )
                if not next_url:
                    self.logger.info(
                        "ℹ️  No next page found — stopping at page %d", page_num
                    )
                    break
                current_url = next_url

        self.logger.info(
            "✅ Catalog scan complete — %d total products", len(product_urls)
        )
        return product_urls

    # ------------------------------------------------------------------
    # Extraction helpers — Zappos-specific HTML selectors
    # ------------------------------------------------------------------

    def _extract_product_id(self, url: str) -> str:
        """Extract the Zappos numeric product ID from the URL.

        Supports:
          /p/<slug>/product/<id>
          /product/<id>

        Args:
            url: Zappos product URL.

        Returns:
            Product ID string (digits only).
        """
        match = re.search(r"/product/(\d+)", url)
        if match:
            return match.group(1)
        # Fallback: last path segment
        return urlparse(url).path.rstrip("/").split("/")[-1]

    def _extract_brand(self, soup: BeautifulSoup) -> str:
        """Extract the shoe brand name from the product page.

        Attempts (in order):
          1. <span itemprop="brand">
          2. data-brand attribute on product container
          3. Second-to-last breadcrumb link
          4. "Unknown"
        """
        # 1. Schema.org brand markup
        brand_tag = soup.find("span", itemprop="brand")
        if brand_tag:
            return brand_tag.get_text(strip=True)

        # 2. data-brand attribute
        brand_el = soup.find(attrs={"data-brand": True})
        if brand_el:
            return brand_el["data-brand"]

        # 3. Breadcrumb: Home > Shoes > <Brand> > <Model>
        breadcrumb_links = soup.select(
            "nav[aria-label='breadcrumb'] a, ol.breadcrumb a"
        )
        if len(breadcrumb_links) >= 2:
            return breadcrumb_links[-2].get_text(strip=True)

        return "Unknown"

    def _extract_model(self, soup: BeautifulSoup, brand: str) -> str:
        """Extract the shoe model name.

        Zappos H1 titles are typically "Brand ModelName [Colorway]".
        We strip the brand prefix to isolate the model.

        Args:
            soup: Parsed product page.
            brand: Already-extracted brand name.

        Returns:
            Model name string.
        """
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
            # Strip brand from start (case-insensitive)
            if brand and brand.lower() != "unknown":
                if title.lower().startswith(brand.lower()):
                    return title[len(brand):].strip()
            return title

        # Fallback: og:title meta tag
        og_title = soup.find("meta", property="og:title")
        if og_title:
            content = og_title.get("content", "").strip()
            if brand and content.lower().startswith(brand.lower()):
                return content[len(brand):].strip()
            return content

        return "Unknown Model"

    def _extract_category(self, soup: BeautifulSoup) -> str:
        """Extract the product category from the last breadcrumb link.

        Returns lowercase category string (e.g. "running", "casual").
        """
        breadcrumb_links = soup.select(
            "nav[aria-label='breadcrumb'] a, ol.breadcrumb a"
        )
        if breadcrumb_links:
            return breadcrumb_links[-1].get_text(strip=True).lower()
        return ""

    def _extract_gender(self, soup: BeautifulSoup, url: str) -> str:
        """Infer gender from the URL path or page content.

        Returns: "mens" | "womens" | "kids" | "unisex"
        """
        url_lower = url.lower()
        if any(kw in url_lower for kw in ("/mens", "men-", "-mens-", "-men-")):
            return "mens"
        if any(kw in url_lower for kw in ("/womens", "women-", "-womens-", "-women-")):
            return "womens"
        if any(kw in url_lower for kw in ("/kids", "boys", "girls", "children")):
            return "kids"

        # Page content fallback
        gender_text = soup.find(
            string=re.compile(r"\b(men'?s|women'?s|kids|boys|girls)\b", re.I)
        )
        if gender_text:
            t = gender_text.lower()
            if "women" in t:
                return "womens"
            if "men" in t:
                return "mens"
            if any(k in t for k in ("kid", "boy", "girl")):
                return "kids"

        return "unisex"

    def _extract_colorway(self, soup: BeautifulSoup) -> str:
        """Extract the selected colorway / color description.

        Tries multiple Zappos markup patterns.
        """
        # 1. data-selected-color attribute
        color_el = soup.find(attrs={"data-selected-color": True})
        if color_el:
            return color_el["data-selected-color"]

        # 2. "Color: X" label pattern
        color_label = soup.find(
            string=re.compile(r"^(color|colour)\s*:", re.I)
        )
        if color_label and color_label.parent:
            sibling = color_label.parent.find_next_sibling()
            if sibling:
                return sibling.get_text(strip=True)

        # 3. Title suffix "...in White/Black"
        h1 = soup.find("h1")
        if h1:
            match = re.search(r"\bin\s+(.+)$", h1.get_text(strip=True), re.I)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract the current selling price as a float.

        Tries schema.org markup, data attributes, og:price, and text fallback.
        """
        # 1. Schema.org price
        price_el = soup.find("span", itemprop="price")
        if price_el:
            raw = price_el.get("content") or price_el.get_text(strip=True)
            result = self._parse_price(raw)
            if result is not None:
                return result

        # 2. data-price attribute
        dp_el = soup.find(attrs={"data-price": True})
        if dp_el:
            result = self._parse_price(dp_el["data-price"])
            if result is not None:
                return result

        # 3. og:price:amount meta
        og_price = soup.find("meta", property="og:price:amount")
        if og_price:
            result = self._parse_price(og_price.get("content", ""))
            if result is not None:
                return result

        # 4. First "$XX.XX" pattern on page
        price_text = soup.find(string=re.compile(r"\$\d+\.?\d*"))
        if price_text:
            return self._parse_price(str(price_text))

        return None

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract the product description text."""
        # 1. itemprop="description"
        desc_el = soup.find(itemprop="description")
        if desc_el:
            return desc_el.get_text(separator=" ", strip=True)

        # 2. Zappos-specific data-test attribute
        desc_el = soup.find("div", attrs={"data-test": "product-description"})
        if desc_el:
            return desc_el.get_text(separator=" ", strip=True)

        # 3. og:description fallback
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            return og_desc.get("content", "").strip()

        return ""

    def _extract_image_urls(self, soup: BeautifulSoup) -> list[str]:
        """Extract all product image URLs, upgrading them to the largest size.

        Collects images from:
          - og:image meta tag
          - <img> tags with img.zappos.com src
          - srcset attributes

        Args:
            soup: Parsed product page.

        Returns:
            Deduplicated list of upgraded image URLs.
        """
        urls: list[str] = []
        seen: set[str] = set()

        def add(raw_url: str) -> None:
            """Upgrade and add a URL if not already seen."""
            if not raw_url or raw_url in seen:
                return
            upgraded = self._upgrade_zappos_image_url(raw_url)
            if upgraded not in seen:
                urls.append(upgraded)
                seen.add(upgraded)
            seen.add(raw_url)

        # 1. Primary og:image
        og_img = soup.find("meta", property="og:image")
        if og_img:
            add(og_img.get("content", ""))

        # 2. Gallery <img> tags from img.zappos.com
        for img in soup.find_all("img", src=re.compile(r"img\.zappos\.com")):
            add(img.get("src", ""))

        # 3. srcset entries
        for img in soup.find_all("img", srcset=True):
            for part in img.get("srcset", "").split(","):
                candidate = part.strip().split(" ")[0]
                if "zappos" in candidate:
                    add(candidate)

        return urls

    def _extract_catalog_product_urls(self, soup: BeautifulSoup) -> list[str]:
        """Extract product page URLs from a Zappos catalog/search results page.

        Matches hrefs that follow the pattern: /p/<slug>/product/<id>
        """
        urls: list[str] = []
        seen: set[str] = set()

        for a_tag in soup.find_all(
            "a", href=re.compile(r"/p/.+/product/\d+")
        ):
            href = a_tag.get("href", "")
            # Strip query params — we want the canonical product URL
            clean = href.split("?")[0]
            full_url = urljoin(self.base_url, clean)
            if full_url not in seen:
                urls.append(full_url)
                seen.add(full_url)

        return urls

    def _find_next_page_url(
        self,
        soup: BeautifulSoup,
        current_url: str,
        next_page: int,
    ) -> Optional[str]:
        """Find or construct the URL for the next results page.

        Tries (in order):
          1. <link rel="next"> tag
          2. Anchor with text "Next"
          3. Append / replace ?p=N query parameter

        Args:
            soup: Current page soup.
            current_url: URL of the page just fetched.
            next_page: The page number to navigate to.

        Returns:
            URL of the next page, or None if pagination is exhausted.
        """
        # 1. rel="next" link tag
        next_link = soup.find("link", rel="next")
        if next_link:
            href = next_link.get("href", "")
            if href:
                return urljoin(self.base_url, href)

        # 2. Visible "Next" button / link
        next_btn = soup.find("a", string=re.compile(r"^\s*next\s*$", re.I))
        if next_btn:
            href = next_btn.get("href", "")
            if href:
                return urljoin(self.base_url, href)

        # 3. Build URL with ?p=N (strip existing p= first)
        base, _, query = current_url.partition("?")
        # Remove existing p= param
        params = re.sub(r"(?:^|&)p=\d+", "", query).strip("&")
        new_param = f"p={next_page}"
        if params:
            return f"{base}?{params}&{new_param}"
        return f"{base}?{new_param}"

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _upgrade_zappos_image_url(url: str) -> str:
        """Replace size tokens in a Zappos image URL with a large-size version.

        Zappos CDN uses tokens like:
          SR38,50        → SR600,600   (resize to WxH)
          _SX90_         → _SX600_     (Amazon-style width token)
          90x90          → 600x600     (WxH in path segment)

        Args:
            url: Raw Zappos image URL.

        Returns:
            URL pointing to a larger version of the same image.
        """
        url = re.sub(r"SR\d+,\d+", "SR600,600", url)
        url = re.sub(r"_SX\d+_", "_SX600_", url)
        url = re.sub(r"\b(\d{2,3})x(\d{2,3})\b", "600x600", url)
        return url

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        """Parse a price string into a float.

        Handles formats like "$89.95", "89.95", "89", "USD 89.95".

        Args:
            text: Raw price text.

        Returns:
            Float price, or None if unparseable.
        """
        match = re.search(r"\d[\d,]*\.?\d*", str(text).replace(",", ""))
        if match:
            try:
                return float(match.group().replace(",", ""))
            except ValueError:
                pass
        return None
