

class DBWriter:

    def __init__(self):
        pass
    
    def sync_config(self, config):
        pass

    def get_active_pairs(self):
        pass

    def get_store(self, store_id):
        pass

    def get_last_snapshot(self, pair_id):
        pass

    def write_snapshot(self, pair_id, result):
        pass

    def update_pair_status(self, pair_id, status):
        pass

    def update_pair_selectors(self, pair_id, price_sel, stock_sel):
        pass

    def update_store_search_template(self, store_id, search_url_template):
        pass

    def clear_pair_selectors(self, pair_id):
        pass

    def get_history(self, isbn, limit):
        pass


