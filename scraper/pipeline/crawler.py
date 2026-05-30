

class Crawler:

    def __init__(self):
        pass

    def build_search_url(self, base_url, query):
        pass
    
    def fetch_search_results(self, search_url):
        pass

    def extract_candidate_links(self, html):
        pass

    def score_candidates(self, links, isbn, title):
        pass

    def validate_product_page(self, url, isbn):
        pass

    def mark_not_listed(self, pair_id):
        pass