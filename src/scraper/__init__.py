"""
src/scraper — Gaitway shoe scraper package.

Contains:
  base_scraper.py  — Abstract BaseScraper + ShoeData dataclass
  zappos.py        — ZapposScraper (first retailer implementation)
"""
from src.scraper.base_scraper import BaseScraper, ShoeData
from src.scraper.zappos import ZapposScraper

__all__ = ["BaseScraper", "ShoeData", "ZapposScraper"]
