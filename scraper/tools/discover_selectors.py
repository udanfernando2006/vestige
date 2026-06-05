import argparse

from browser.session import BrowserSession
from pipeline.scraper import Scraper
from pipeline.crawler import Crawler
from pipeline.llm_extractor import Extractor

def main():
    pass

def build_extractor_config():
    pass

def load_target(pair, id, url, store):
    pass

def fetch_and_trim_html(url, extractor, session=None):
    pass

def validate_selectors(url, price_sel, stock_sel, extractor):
    pass

def commit_to_db(pair_id, price_sel, stock_sel):
    pass