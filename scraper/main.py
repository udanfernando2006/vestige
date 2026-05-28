import asyncio
from pipeline.scraper import Scraper
import json

async def scrape_with_limit(semaphore, scraper, pair):
    async with semaphore:
        return await scraper.scrape(pair['url'], pair['selectors'])

async def main():
    scraper = Scraper(headless=True, wait_time=2)
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent
    
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
            'direct_text': True
        },
        'availability': {
            'selector': 'span.text-sm.text-green-600.font-semibold'
        },
        'isbn': {
            'find_by_text': ('dt', 'ISBN'),
            'then_next': 'dd'
        },
        'description': {
            'selector': 'div.text-gray-700'
        }
    }
    },
    ]
    
    results = await asyncio.gather(
        *[scrape_with_limit(semaphore, scraper, pair) for pair in pairs]
    )
    return results

if __name__ == "__main__":
    results = asyncio.run(main())
    print(json.dumps(results, indent=2))