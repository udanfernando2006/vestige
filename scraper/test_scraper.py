import asyncio
from pipeline.scraper import Scraper
import json
from dataclasses import asdict

async def scrape_with_limit(semaphore, pair):
    print("URL:", pair['url'])
    async with semaphore:
        scraper = Scraper(headless=True, wait_time=2)  # New instance per request
        return await scraper.scrape(pair['url'], pair['selectors'], pair.get('wait_selectors'))

async def main():
    CONCURRENT_SCRAPERS = 5   # Max 5 concurrent
    semaphore = asyncio.Semaphore(CONCURRENT_SCRAPERS)
    
    pairs = [
        {
            'url': 
         'https://jeyabookcentre.com/item/75242-the-last-wish?srsltid=AfmBOoq0kjNyIWejlHCi2lFKboz48AyTO-7XHfzT01s_FneKvcGsQHz5',
          'selectors': {
        'title': {
            'selector': 'h1.text-3xl.font-bold.text-gray-900.mb-2'
        },
        'price': {
            'selector': 'span.text-xl.font-bold.text-gray-900',
            'direct_text': True,
            'extract_numeric': True
        },
        'availability': {
            'selector': 'span.text-sm.text-green-600.font-semibold'
        },
        'isbn': {
            'find_by_text': ('dt', 'ISBN'),
            'then_next': 'dd'
        },
        'description': {
            'selector': 'div.text-gray-700',
            'preserve_semantics': True
        }
    }
    },
    {
        'url': 
        'https://www.sarasavi.lk/product/the-witcher---the-last-wish-147323106x',
        'wait_selectors': 
        ['.ProductInner_productbox_details_price_discount__WKWSB'],
        'selectors': {
            'title': {
                'selector': 'h1.section-heading'
            },
            'price': {
                'selector': '.ProductInner_productbox_details_price_discount__WKWSB',
                'extract_numeric': True
            },
            'availability': {
                'selector': '.ProductInner_productinnerwrap_stock__VBeJJ'
            },
            'isbn': {
                'find_by_text': ('span', 'ISBN 13'),
                'then_next': 'td',
                'extract_numeric': True
            },
            'description': {
                'selector': '.para--black',
                'preserve_semantics': True
            }
        }
    },
    {
        'url': 
        'https://jumpbooks.lk/product/the-last-wish-reissue-introducing-the-witcher-now-a-major-netflix-show/',
        'selectors': {
            'title': {
                'selector': 'h1.product-title'
            },
            'price': {
                'selector': 'p.price > span:nth-child(1)',
                'extract_numeric': True
            },
            'availability': {
                'selector': '.stock'
            },
            'isbn': {
                'selector': '.sku'
            },
            'description': {
                'selector': '.a-expander-partial-collapse-content',
                'preserve_semantics': True
            }
        }
    }
    ]
    
    results = await asyncio.gather(
        *[scrape_with_limit(semaphore, pair) for pair in pairs]
    )
    return results

if __name__ == "__main__":
    results = asyncio.run(main())
    print(json.dumps([asdict(result) for result in results], indent=2, default=str))