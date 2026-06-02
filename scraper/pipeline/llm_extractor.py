import json
import os
import re

from openai import OpenAI
from bs4 import BeautifulSoup, Comment

SYSTEM_PROMPT = """You are an expert web scraping engine. Your task is to inspect the provided HTML snippet of an e-commerce product page and determine the single most robust, site-wide resilient CSS selector to target the requested field.

CRITICAL RULES FOR SELECTOR GENERATION:
1. FOCUS ON TARGET ELEMENT AND DESCRIPTIVE CLASSES: Pick selectors that use explicit descriptive class names (e.g., return `.sku`, `.product-title`, or `.product-short-description`). 
2. TARGET THE ROOT CONTAINER FOR COMPLEX FIELDS: For fields like "description", pick the parent wrapper container that holds all description paragraphs (e.g., `.product-short-description`), not an individual paragraph tag inside it.
3. STRIP ALL DYNAMIC & VOLATILE IDENTIFIERS: Never include database numeric IDs (e.g., drop `#product-111805`, `#post-9482`) or temporal real-time flags (e.g., `.outofstock`, `.first`, `.last`).
4. SYNTAX PRECISION: Multi-class tags must be chained with dots and NO SPACES (e.g., `.product-title.product_title.entry-title`).

You must respond STRICTLY with a valid JSON object matching this schema. No explanations, no markdown blocks:
{
  "selector": "GENERIC_CSS_SELECTOR",
  "confidence": 1.00,
  "reason": "Brief technical justification"
}"""

class Extractor:
    def __init__(self, url: str):
        self._url = url
        
        # Configure LLM Connection
        # Defaulting to local Ollama (Qwen3.5:4b or Llama3) 
        # Easily overridden via environment variables for AWS/Azure deployment
        self.api_base = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("LLM_API_KEY", "ollama")
        self.model_name = os.getenv("LLM_MODEL_NAME", "qwen2.5-coder:3b")

        self.client = OpenAI(base_url=self.api_base, api_key=self.api_key)


    def clean_html(self, html: str):
        soup = BeautifulSoup(html, 'lxml')

        tags_to_remove = ['script', 'style', 'nav', 'footer', 'header', 'svg', 'iframe', 'noscript']
        for tag in tags_to_remove:
            for element in soup.find_all(tag):
                element.decompose()

        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.decompose()

        return soup
    
    def query_selector_from_html(self, cleaned_soup, target_field_name: str) -> dict:
        """
        Passes the structured element HTML directly to the LLM, giving it full 
        structural context to infer the cleanest CSS selectors.
        """
        # Isolate the core product block to minimize token footprint
        product_container = cleaned_soup.find(['main', 'div'], class_=lambda c: c and any(p in c for p in ['product', 'shop-container']))
        
        # Fallback to the whole cleaned soup if specific container wrapper isn't found
        html_context = str(product_container) if product_container else str(cleaned_soup)
        
        # Build the user prompt requesting the specific field selector
        user_content = f"Analyze this HTML layout and find the best site-wide resilient CSS selector for the field: '{target_field_name}'\n\nHTML Content:\n{html_context}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.0,
                response_format={"type": "json_object"} # Forces clean JSON output if supported by model engine
            )
            
            result = json.loads(response.choices[0].message.content.strip())
            return result
        except Exception as e:
            return {"selector": None, "confidence": 0.0, "reason": f"LLM parsing failed: {e}"}

    def extract_text_nodes(self, cleaned_html, container=None):
        if cleaned_html is None:
            return []

        nodes = []

        for text_node in cleaned_html.find_all(string=True):
            if isinstance(text_node, Comment):
                continue

            text = text_node.strip()
            if not text:
                continue

            element = text_node.parent
            if element is None or not getattr(element, "name", None):
                continue

            # Skip text nodes in secondary sections (related products, recommendations, etc)
            secondary_keywords = ['related', 'recommendation', 'upsell', 'you-may-like', 'similar', 'bundle', 'carousel', 'footer']
            parent = element
            skip = False
            depth = 0
            for _ in range(15):  # Check up to 15 levels
                if parent is None:
                    break
                parent_classes = parent.get("class", [])
                parent_id = parent.get("id", "")
                combined = f"{parent_id} {' '.join(parent_classes)}".lower()
                if any(keyword in combined for keyword in secondary_keywords):
                    skip = True
                    break
                parent = parent.parent
                depth += 1
            
            if skip:
                continue

            path_parts = []
            selector_parts = []
            current = element
            depth = 0
            while current and getattr(current, "name", None) and current.name not in ("[document]", "html", "body"):
                id_attr = current.get("id")
                class_attr = current.get("class") or []

                path_part = current.name
                if id_attr:
                    path_part += f"#{id_attr}"
                if class_attr:
                    path_part += "." + ".".join(class_attr)
                path_parts.append(path_part)

                selector_part = current.name
                if id_attr:
                    selector_part += f"#{self._escape_css_identifier(id_attr)}"
                for cls in class_attr:
                    selector_part += f".{self._escape_css_identifier(cls)}"
                selector_parts.append(selector_part)

                current = current.parent
                depth += 1

            path_parts.reverse()
            selector_parts.reverse()
            dom_path = " > ".join(path_parts)
            clean_selector = " > ".join(selector_parts)

            nodes.append(
                {
                    "text": text,
                    "dom_path": dom_path,
                    "tag_name": element.name,
                    "selector": self.derive_selector(dom_path),
                    "depth": depth,  # Track how deep in the DOM
                }
            )

        # fields = nodes[0].keys()
        # 
        # with open("output.csv", "w", newline="", encoding="utf-8") as file:
        #     writer = csv.DictWriter(file, fieldnames=fields)
        #     writer.writeheader()
        #     writer.writerows(nodes)


        return nodes
    
    def _query_llm(self, target_type: str, candidates: list):
        """Sends clean candidate nodes to the LLM to make the final contextual choice."""
        if not candidates:
            return {"selector": None, "confidence": 0.0, "reason": "no_candidates"}

        # Serialize the candidate pool for the LLM
        candidate_pool = ""
        for idx, item in enumerate(candidates):
            candidate_pool += f"Index: {idx} | Tag: <{item['tag_name']}> | Text: '{item['text']}'\n"

        prompt = f"""
You are an expert web scraping engine. Choose which DOM element index holds the primary product {target_type} of the main item.

Candidates:
{candidate_pool}

Respond strictly in valid JSON format with:
- "selected_index": (integer, the index of the chosen item, or null if none match)
- "confidence": (float between 0.0 and 1.0)
- "reasoning": (string, brief reason)
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"} 
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Map the LLM's selected index back to our original candidate selector
            selected_idx = result.get("selected_index")
            if selected_idx is not None and isinstance(selected_idx, int) and 0 <= selected_idx < len(candidates):
                chosen_candidate = candidates[selected_idx]
                return {
                    "selector": chosen_candidate["selector"],
                    "confidence": result.get("confidence", 0.0),
                    "answer": chosen_candidate["text"],
                    "reasoning": result.get("reasoning", "")
                }
            else:
                return {"selector": None, "confidence": 0.0, "reason": "llm_rejected_all_candidates"}

        except Exception as e:
            print(f"LLM Processing Error: {e}")
            return {"selector": None, "confidence": 0.0, "reason": "llm_exception"}


    def classify_title_node(self, cleaned_html):
        nodes = self.extract_text_nodes(cleaned_html)
        # Filter: Look for text in headings or prominent short text fields
        candidates = [n for n in nodes if n['tag_name'] in ['h1', 'h2', 'span'] and 3 < len(n['text']) < 150]
        candidates = sorted(candidates, key=lambda x: x['depth'])[:15]

        # print(len(candidates))
        # print(len(max(candidates, key=lambda x: len(x['text']))['text']))
        # print(len(min(candidates, key=lambda x: len(x['text']))['text']))
        # print(json.dumps(candidates, indent=2))

        # return {"selector": None, "confidence": 0.0, "reason": "llm_rejected_all_candidates"}

        return self._query_llm("TITLE (Main name of the product book)", candidates)
    
    def classify_price_node(self, cleaned_html):
        nodes = self.extract_text_nodes(cleaned_html)
        candidates = [n for n in nodes if any(char.isdigit() for char in n['text'])]
        candidates = sorted(candidates, key=lambda x: x['depth'])[:20]

        # print(len(candidates))
        # print(len(max(candidates, key=lambda x: len(x['text']))['text']))
        # print(len(min(candidates, key=lambda x: len(x['text']))['text']))
        # print(json.dumps(candidates, indent=2))

        # return {"selector": None, "confidence": 0.0, "reason": "llm_rejected_all_candidates"}

        return self._query_llm("PRICE (The main buying price currency/amount)", candidates)


    def classify_stock_node(self, cleaned_html):
        nodes = self.extract_text_nodes(cleaned_html)
        stock_keywords = ["stock", "available", "availability", "sold out", "out of stock", "in stock", "pre-order", "add to cart"]
        candidates = [n for n in nodes if any(kw in n['text'].lower() for kw in stock_keywords)]
        candidates = sorted(candidates, key=lambda x: x['depth'])[:15]

        # print(len(candidates))
        # print(len(max(candidates, key=lambda x: len(x['text']))['text']))
        # print(len(min(candidates, key=lambda x: len(x['text']))['text']))
        # print(json.dumps(candidates, indent=2))

        # return {"selector": None, "confidence": 0.0, "reason": "llm_rejected_all_candidates"}

        return self._query_llm("AVAILABILITY STATUS (e.g., 'In Stock', 'Out of Stock')", candidates)
    
    def classify_description_node(self, cleaned_html):
        nodes = self.extract_text_nodes(cleaned_html)
        # Filter: Long paragraph content representing the summary
        candidates = [n for n in nodes if len(n['text']) > 80 and n['tag_name'] in ['p', 'div', 'span']]
        candidates = sorted(candidates, key=lambda x: x['depth'])[:10]

        # print(len(candidates))
        # print(len(max(candidates, key=lambda x: len(x['text']))['text']))
        # print(len(min(candidates, key=lambda x: len(x['text']))['text']))
        # print(json.dumps(candidates, indent=2))

        # return {"selector": None, "confidence": 0.0, "reason": "llm_rejected_all_candidates"}
    
        return self._query_llm("DESCRIPTION (Main descriptive body paragraph of the product)", candidates)
    
    def classify_isbn_node(self, cleaned_html):
        nodes = self.extract_text_nodes(cleaned_html)
        # Filter: Contains sequences of digits typical for 10 or 13-digit ISBN numbers
        candidates = [n for n in nodes if re.search(r'\d{9,14}', n['text'].replace('-', '')) or 'isbn' in n['text'].lower()]
        candidates = sorted(candidates, key=lambda x: x['depth'])[:15]

        # print(len(candidates))
        # print(len(max(candidates, key=lambda x: len(x['text']))['text']))
        # print(len(min(candidates, key=lambda x: len(x['text']))['text']))
        # print(json.dumps(candidates, indent=2))

        # return {"selector": None, "confidence": 0.0, "reason": "llm_rejected_all_candidates"}

        return self._query_llm("ISBN / SKU identifier code", candidates)

    def derive_selector(self, dom_path):
        if not dom_path:
            return None

        # Split the path into individual steps
        parts = dom_path.split(" > ")
        if not parts:
            return None
            
        # Target element is always the last item in the path
        target_part = parts[-1]
        
        # Helper to parse tag, ID, and classes from a single path string element
        def parse_part(part_str):
            tag = part_str
            element_id = None
            classes = []
            
            if "#" in tag:
                tag, element_id = tag.split("#", 1)
            if "." in tag:
                tag_name, *classes = tag.split(".")
            else:
                tag_name = tag
                
            return tag_name, element_id, classes

        target_tag, target_id, target_classes = parse_part(target_part)

        # Volatile utility classes to filter out
        volatile_classes = {
            'col', 'col-fit', 'row', 'mb-0', 'form-minimal', 'summary',
            'outofstock', 'instock', 'first', 'last', 'product-type-simple'
        }
        
        # Filter target classes
        clean_target_classes = [
            c for c in target_classes 
            if c not in volatile_classes and not c.startswith("post-") and not c.startswith("product_cat-")
        ]

        # 1. High Preference: If the target has a clean, reliable ID, use just that
        if target_id and not re.search(r'\d{4,}', target_id):
            return f"#{self._escape_css_identifier(target_id)}"

        # 2. High Preference: If the target has explicit unique classes, use them directly
        if clean_target_classes:
            # Join multiple classes with dots (e.g., .product-title.product_title.entry-title)
            return "".join(f".{self._escape_css_identifier(c)}" for c in clean_target_classes)

        # 3. Fallback: Target element is bare (e.g. "span" or "strong"), so look at the immediate parent
        if len(parts) > 1:
            parent_part = parts[-2]
            parent_tag, parent_id, parent_classes = parse_part(parent_part)
            
            clean_parent_classes = [
                c for c in parent_classes 
                if c not in volatile_classes and not c.startswith("post-") and not c.startswith("product_cat-")
            ]
            
            # Construct a parent anchor
            parent_selector = parent_tag
            if parent_id and not re.search(r'\d{4,}', parent_id):
                parent_selector = f"#{self._escape_css_identifier(parent_id)}"
            elif clean_parent_classes:
                parent_selector = "".join(f".{self._escape_css_identifier(c)}" for c in clean_parent_classes)
                
            return f"{parent_selector} > {target_tag}"

        # Absolute Fallback: just return the tag name
        return target_tag

    def validate_selectors(self, price_selector, stock_selector):
        pass

    def cache_selectors(self, pair_id, price_selector, stock_selector):
        pass

    def _escape_css_identifier(self, value):
        escaped = value.replace('\\', '\\\\')
        for character in (':', '.', '#', '[', ']', '(', ')', '/', '%', ' '):
            escaped = escaped.replace(character, f'\\{character}')
        return escaped