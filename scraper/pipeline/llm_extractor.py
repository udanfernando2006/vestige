import os
import re
import csv

import torch

from bs4 import BeautifulSoup, Comment
from transformers import AutoTokenizer, AutoModelForQuestionAnswering

class Extractor:
    def __init__(self, url: str):
        self._url = url
        os.environ["DISABLE_SAFETENSORS_CONVERSION"] = "1"

        # Load MarkupLM model directly
        model_name = "microsoft/markuplm-base"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForQuestionAnswering.from_pretrained(model_name, use_safetensors=False)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def clean_html(self, html: str):
        soup = BeautifulSoup(html, 'lxml')

        tags_to_remove = ['script', 'style', 'nav', 'footer', 'header']
        for tag in tags_to_remove:
            for element in soup.find_all(tag):
                element.decompose()

        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.decompose()

        return soup

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
            current = element
            depth = 0
            while current and getattr(current, "name", None) and current.name not in ("[document]", "html", "body"):
                selector_part = current.name

                element_id = current.get("id")
                if element_id:
                    selector_part += f"#{element_id}"

                classes = current.get("class") or []
                if classes:
                    selector_part += "." + ".".join(classes)

                path_parts.append(selector_part)
                current = current.parent
                depth += 1

            path_parts.reverse()

            nodes.append(
                {
                    "text": text,
                    "dom_path": " > ".join(path_parts),
                    "element": element,
                    "tag_name": element.name,
                    "element_id": element.get("id"),
                    "classes": element.get("class") or [],
                    "depth": depth,  # Track how deep in the DOM
                }
            )

        fields = nodes[0].keys()

        # with open("output.csv", "w", newline="", encoding="utf-8") as file:
        #     writer = csv.DictWriter(file, fieldnames=fields)
        #     writer.writeheader()
        #     writer.writerows(nodes)


        return nodes

    def classify_price_node(self, cleaned_html):
        nodes = self.extract_text_nodes(cleaned_html)
        return self._classify_node(nodes, kind="price")


    def classify_stock_node(self, cleaned_html):
        nodes = self.extract_text_nodes(cleaned_html)
        return self._classify_node(nodes, kind="stock")

    def derive_selector(self, dom_path):
        if not dom_path:
            return None

        selector_parts = []

        for part in dom_path.split(" > "):
            if not part:
                continue

            tag_part = part
            class_parts = []
            element_id = None

            if "#" in tag_part:
                tag_part, element_id = tag_part.split("#", 1)

            if "." in tag_part:
                tag_name, *class_parts = tag_part.split(".")
            else:
                tag_name = tag_part

            selector = tag_name

            if element_id:
                selector += f"#{self._escape_css_identifier(element_id)}"

            for class_name in class_parts:
                selector += f".{self._escape_css_identifier(class_name)}"

            selector_parts.append(selector)

        return " > ".join(selector_parts)

    def validate_selectors(self, price_selector, stock_selector):
        pass

    def cache_selectors(self, pair_id, price_selector, stock_selector):
        pass

    def _classify_node(self, nodes, kind):
        if not nodes:
            return {
                "selector": None,
                "confidence": 0.0,
                "reason": "no_text_nodes",
            }

        if kind == "price":
            keywords = ("price", "amount", "lkr", "rs", "rupee", "buy")
        else:
            keywords = ("stock", "available", "availability", "sold out", "out of stock", "in stock", "pre-order")

        best_node = None
        best_score = 0.0
        min_depth = float('inf')

        for node in nodes:
            text = node["text"].lower()
            score = 0.0

            if kind == "price":
                if any(keyword in text for keyword in keywords):
                    score += 0.6
                if any(character.isdigit() for character in text):
                    score += 0.25
                if any(symbol in text for symbol in ("$", "€", "£", "rs", "lkr")):
                    score += 0.15
                
                # Prefer larger numbers (main prices > installment prices)
                try:
                    numbers = re.findall(r'[\d,]+\.?\d*', text)
                    if numbers:
                        parsed_nums = [float(n.replace(',', '')) for n in numbers]
                        if parsed_nums and max(parsed_nums) > 2000:  # Main prices typically > 2000
                            score += 0.2
                except:
                    pass
                
                # Penalize installment-style text (contains "x", "installment", "with", etc)
                installment_keywords = ('x ', 'installment', 'with ', 'monthly', 'emi', 'plan')
                if any(keyword in text for keyword in installment_keywords):
                    score -= 0.5  # Strong penalty for installment text
                
                # Strong bonus for pure price patterns: currency + number, short text
                if re.search(r'rs\.?\s*[\d,]+.*\d', text, re.IGNORECASE) and len(text) < 40:  
                    score += 0.3  # Stronger bonus for pure price format
                
                # Strongly prefer prices in shallower DOM (main product area)
                node_depth = node.get("depth", float('inf'))
                if node_depth < min_depth or (node_depth == min_depth and score > best_score):
                    depth_bonus = max(0, (25 - node_depth) * 0.01)  # ~0.25 bonus at depth 0
                    score += depth_bonus
            else:
                if any(keyword in text for keyword in keywords):
                    score += 0.75
                if text in ("in stock", "out of stock", "available", "sold out", "pre-order"):
                    score += 0.25

            if score > best_score:
                best_score = score
                best_node = node
                min_depth = node.get("depth", float('inf'))

        if not best_node or best_score < 0.5:
            return {
                "selector": None,
                "confidence": best_score,
                "reason": "low_confidence",
            }

        selector = self.derive_selector(best_node["dom_path"])

        return {
            "selector": selector,
            "confidence": best_score,
            "answer": best_node["text"],
        }

    def _result(self, question, cleaned_html):
        """Helper to run MarkupLM QA and extract results."""
        html_string = str(cleaned_html)
        
        # Tokenize question and context
        inputs = self.tokenizer.encode_plus(
            question,
            html_string,
            return_tensors="pt",
            max_length=512,
            truncation=True
        ).to(self.device)
        
        # Get predictions
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Extract answer span
        start_scores = outputs.start_logits
        end_scores = outputs.end_logits
        
        start_index = torch.argmax(start_scores)
        end_index = torch.argmax(end_scores) + 1
        
        answer_ids = inputs["input_ids"][0][start_index:end_index]
        answer = self.tokenizer.decode(answer_ids)
        
        # Calculate confidence (higher logit = higher confidence)
        confidence = (start_scores.max().item() + end_scores.max().item()) / 2
        
        if confidence < 0.5:
            return {
                "selector": None,
                "confidence": confidence,
                "reason": "low_confidence"
            }
        
        # Map text position to element
        element = self._find_element_by_text_position(
            cleaned_html,
            start_index.item(),
            end_index.item()
        )
        
        if not element:
            return {
                "selector": None,
                "confidence": 0.0,
                "reason": "element_not_found"
            }
        
        selector = self._element_to_selector(element)
        
        return {
            "selector": selector,
            "confidence": confidence,
            "answer": answer
        }

    def _find_element_by_text_position(self, soup, start_pos, end_pos):
        """Given start/end character positions, find the containing element."""
        
        html_string = str(soup)
        answer_text = html_string[start_pos:end_pos]
        
        # Find all elements containing this text
        for element in soup.find_all(string=True):
            if answer_text in str(element):
                # Found it! Return the parent element (not the text node)
                return element.parent
        
        return None

    def _element_to_selector(self, element):
        """Convert a BeautifulSoup element to a CSS selector."""
        path_parts = []
        current = element
        
        while current and current.name:
            if current.name in ("[document]", "html", "body"):
                break

            selector_part = current.name
            
            # Add class
            if current.get('class'):
                classes = ' '.join(current.get('class'))
                selector_part += f".{'.'.join(self._escape_css_identifier(class_name) for class_name in current.get('class'))}"
            
            # Add id if present
            if current.get('id'):
                selector_part += f"#{self._escape_css_identifier(current.get('id'))}"
            
            path_parts.append(selector_part)
            current = current.parent
        
        path_parts.reverse()
        return " > ".join(path_parts)

    def _escape_css_identifier(self, value):
        escaped = value.replace('\\', '\\\\')
        for character in (':', '.', '#', '[', ']', '(', ')', '/', '%', ' '):
            escaped = escaped.replace(character, f'\\{character}')
        return escaped