import json
import os
from openai import OpenAI
from bs4 import BeautifulSoup, Comment

SYSTEM_PROMPT = """You are a highly precise, data-focused extraction engine. Your only task is to convert raw semantic text layout data into structured JSON matching the requested schema. Do not write explanations, markdown syntax code blocks around the JSON object, or conversational replies. Return ONLY raw JSON."""

USER_PROMPT_TEMPLATE = """Target Book Title: "{target_title}"

Task: Read the following semantic HTML context and extract specific details for this target book.

Rules:
1. Only extract data that directly belongs to the main book profile.
2. Completely ignore surrounding site furniture (sidebars, footer links, header menus, payment installment plans, share buttons, tags, or categories).
3. Price: Extract the exact raw text for the price including currency symbols (e.g., "LKR 3,303.00", "රු 2,995.00").
4. Stock Status: Extract the precise stock state (e.g., "In stock", "Out of Stock", "Sold Out").
5. Description: Extract ONLY the narrative book summary / blurb text. Format this string into clean markdown paragraphs (using standard newlines). Exclude titles, authors, prices, or store notices from this block. Keep it focused and descriptive.
6. ISBN: Extract the standard 10 or 13 digit numerical ISBN. If you see scientific notation (like 9.78147E+12), expand it or locate the raw text digits instead of leaving it truncated. If no clean digit code is found, return null.

Expected JSON Schema:
{{
  "price": "string or null",
  "stock_status": "string or null",
  "description": "string or null (formatted as clean markdown paragraphs)",
  "isbn": "string or null"
}}

HTML Content:
{cleaned_html}"""

class Extractor:
    def __init__(self, url: str):
        self._url = url
        self.api_base = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("LLM_API_KEY", "ollama")
        self.model_name = os.getenv("LLM_MODEL_NAME", "qwen2.5-coder:3b")
        self.client = OpenAI(base_url=self.api_base, api_key=self.api_key)

    def clean_html(self, html: str) -> str:
        soup = BeautifulSoup(html, 'lxml')
        
        # Decompose baseline technical components
        tags_to_remove = ['script', 'style', 'nav', 'footer', 'header', 'svg', 'iframe', 'noscript', 'dialog', 'form']
        for tag in tags_to_remove:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Target global utility layouts precisely
        global_structural_elements = [
            'div#header', 'div#footer', '.site-header', '.site-footer', 
            '.top-bar', '.main-navigation', '.footer-widgets', '#sidebar-menu',
            '.top-banner-fixed', '.bg-gray-900'
        ]
        for sel in global_structural_elements:
            for element in soup.select(sel):
                element.decompose()

        # Remove recommendation blocks to avoid card contamination
        cross_sell_identifiers = [
            '.related', '.upsells', '.cross-sells', '#related-products', 
            '.product-carousel', '.related-products', '.recommended-products',
            '.up-sells', '.product_carousel'
        ]
        for identifier in cross_sell_identifiers:
            for element in soup.select(identifier):
                element.decompose()

        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment.decompose()
            
        # Return cleaned text-dense output minimizing token footprint
        return soup.get_text(separator=" ", strip=True)

    def extract_details(self, cleaned_html: str, target_title: str) -> dict:
        user_content = USER_PROMPT_TEMPLATE.format(
            target_title=target_title,
            cleaned_html=cleaned_html
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content.strip())
        except Exception as e:
            return {
                "error": f"Extraction failure: {e}",
                "price": None,
                "stock_status": None,
                "description": None,
                "isbn": None
            }