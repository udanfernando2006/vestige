import json
import os
import re
from openai import OpenAI
from bs4 import BeautifulSoup, Comment

SEMANTIC_SYSTEM_PROMPT = """You are a highly precise, data-focused extraction engine. Your only task is to convert raw semantic text layout data into structured JSON matching the requested schema. Do not write explanations, markdown syntax code blocks around the JSON object, or conversational replies. Return ONLY raw JSON."""

SEMANTIC_USER_PROMPT = """Target Book Title: "{target_title}"

Task: Read the following semantic HTML context and extract specific details for this target book.

Rules:
1. Only extract data that directly belongs to the main book profile.
2. Completely ignore surrounding site furniture (sidebars, footer links, header menus, payment installment plans, share buttons, tags, or categories).
3. Price: Extract the exact raw text for the price including currency symbols (e.g., "LKR 3,303.00", "රු 2,995.00").
4. Stock Status: Extract the precise stock state (e.g., "In stock", "Out of Stock", "Sold Out").
5. Description: Extract ONLY the narrative book summary / blurb text. Format this string into clean markdown paragraphs (using standard newlines). Exclude titles, authors, prices, or store notices from this block. Keep it focused and descriptive.
6. ISBN (CRITICAL VALUE LINKING):
   - Locate the exact 10 or 13-digit commercial identifier on the page. If both are present, prioritize the 13-digit ISBN.
   - Look sequentially: It will appear directly inside the text node immediately following a label like "ISBN-13:", "ISBN:", "ISBN 10:", or "SKU:".
   - Example sequence: If you see "<li><strong>ISBN-13:</strong> 978...</li>", the sequence of numbers after the tag is the value. Capture it explicitly.
   - If you see scientific notation (like 9.78147E+12), convert it back into full text digits. If completely absent, return null.

Expected JSON Schema:
{{
  "price": "string or null",
  "stock_status": "string or null",
  "description": "string or null (formatted as clean markdown paragraphs)",
  "isbn": "string or null"
}}

HTML Content:
{cleaned_html}"""


SELECTOR_SYSTEM_PROMPT = """You are an advanced web-scraping metadata generator. Your sole function is to analyze raw HTML DOM structures and output a clean, compliant JSON extraction map tailored for a custom BeautifulSoup scraping pipeline. 

You must strictly output raw JSON matching the requested schema. Do not write markdown blocks, explanations, or code commentary."""

SELECTOR_USER_PROMPT = """Target Book Title: "{target_title}"

Task: Analyze the provided HTML context and generate the exact JSON selection criteria required to extract target fields for this book profile.

Target Fields to Extract:
- "title"
- "price"
- "availability"
- "isbn"
- "description"

Extraction Rulebook:
1. CSS Selectors Strategy:
   - For standard layout wrappers, use the "selector" key with a valid CSS selector string suitable for BeautifulSoup's `soup.select_one()`.
   - If an element uses multiple classes, chain them using periods without spaces.
   - Avoid unstable, heavily auto-generated platform classes if structural class names are available.

2. Price Target Isolation (CRITICAL):
   - Locate the primary retail purchase price container for the book.
   - NEVER target secondary promotional pricing, credit card discount schedules, bank partnership rates, or installment plans (e.g., Koko, Mintpay, or payment installment preview widgets).
   - If a selector contains text like "payment", "installment", "preview", "card", or "discount", it is WRONG. Skip it and find the standalone retail price wrapper.

3. Framework Resiliency Rules (CRITICAL FOR DYNAMIC HASHES):
   - Modern JS Frameworks (Next.js, Nuxt, React) append unique production compilation hashes to classes (e.g., class="ProductInner_productinnerwrap_price__gttmW").
   - NEVER match against these temporary trailing suffixes. Instead, instantly switch to a CSS partial attribute wildcard identifier (`*=`).
   - Example: Instead of writing `div.ProductInner_productinnerwrap_price__gttmW`, you MUST output `div[class*='ProductInner_productinnerwrap_price']`.

4. Target Containers Directly:
   - Do NOT append unverified structural layout tags like `strong`, `span`, or `b` to the end of a selector unless that component explicitly wraps the target text exclusively inside the layout tree.

5. Text-Lookup Fallback Strategy ("find_by_text"):
   - If a target field (especially "isbn") lives in a complex data grid or specification table with inner layout noise (like structural SVGs, inline spans, or icons), do NOT use rigid nth-child rules.
   - Use the text-lookup fallback format to track the semantic label directly:
     "find_by_text": ["tag_name_wrapping_text", "Exact/Sub-String Label Text"]
     "then_next": "target_value_tag_name"
   - Priority Constraint for ISBN: If both an "ISBN" (10-digit) and "ISBN 13" (13-digit) label are available, ALWAYS explicitly target the "ISBN 13" option to capture clean standard commercial records.
   - Example for <tr><th><svg></svg><span>ISBN 13</span></th><td>: 978...</td></tr>:
     "find_by_text": ["span", "ISBN 13"], "then_next": "td"
   - Try looking for simpler elements which house the same ISBN, so that the selector is not dependent on the presence of specific structural tags. For instance, if the page has a clean <li>ISBN 13: 978...</li> element, prefer that with "find_by_text": ["li", "ISBN 13"] and no "then_next" traversal. Or if another element with a class has the ISBN, target that with a direct "selector" strategy.

6. Extraction Behavior Flags:
   - For the "price" field, append `"direct_text": true` to capture only its immediate inner string value.
   - For the "description" field, always include `"preserve_semantics": true`.

Expected JSON Structure Output:
{{
  "selectors": {{
    "title": {{ "selector": "string" }},
    "price": {{ "selector": "string", "direct_text": true }},
    "availability": {{ "selector": "string" }},
    "isbn": {{ "find_by_text": ["tag", "text"], "then_next": "tag" }},
    "description": {{ "selector": "string", "preserve_semantics": true }}
  }}
}}

If a field is entirely absent from the HTML context, return its field value configuration block as null.

HTML Content:
{cleaned_html}"""

class Extractor:
    def __init__(self, config: dict):
        self.engine = config.get("engine", "local") # 'local' or 'cloud'
        self.api_base = config.get("api_base", "http://localhost:11434/v1")
        self.api_key = config.get("api_key", "ollama")
        self.model_name = config.get("model_name", "qwen2.5-coder:3b")

        self.client = OpenAI(base_url=self.api_base, api_key=self.api_key)

    # def clean_html(self, html: str) -> str:
    #     soup = BeautifulSoup(html, 'lxml')
        
    #     # Decompose baseline technical components
    #     tags_to_remove = ['script', 'style', 'nav', 'footer', 'header', 'svg', 'iframe', 'noscript', 'dialog', 'form']
    #     for tag in tags_to_remove:
    #         for element in soup.find_all(tag):
    #             element.decompose()
        
    #     # Target global utility layouts precisely
    #     global_structural_elements = [
    #         'div#header', 'div#footer', '.site-header', '.site-footer', 
    #         '.top-bar', '.main-navigation', '.footer-widgets', '#sidebar-menu',
    #         '.top-banner-fixed', '.bg-gray-900', '.cookie-notice', '#cookie-law-info-bar'
    #     ]
    #     for sel in global_structural_elements:
    #         for element in soup.select(sel):
    #             element.decompose()

    #     # Remove recommendation blocks to avoid card contamination
    #     cross_sell_identifiers = [
    #         '.related', '.upsells', '.cross-sells', '#related-products', 
    #         '.product-carousel', '.related-products', '.recommended-products',
    #         '.up-sells', '.product_carousel'
    #     ]
    #     for identifier in cross_sell_identifiers:
    #         for element in soup.select(identifier):
    #             element.decompose()

    #     comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    #     for comment in comments:
    #         comment.decompose()

    #     core_element = None
    #     if soup.find('main'):
    #         core_element = soup.find('main')
    #     elif soup.find(id=re.compile(r'^(main|content|primary|app-root)$', re.IGNORECASE)):
    #         core_element = soup.find(id=re.compile(r'^(main|content|primary|app-root)$', re.IGNORECASE))
    #     elif soup.find(class_=re.compile(r'(main-content|page-content|product-detail)', re.IGNORECASE)):
    #         core_element = soup.find(class_=re.compile(r'(main-content|page-content|product-detail)', re.IGNORECASE))
        
    #     if core_element:
    #         soup = core_element

    #     void_elements = {'img', 'input', 'hr', 'br', 'meta', 'link'}
        
    #     # Loop bottom-up multiple times to clear progressively emptied parent containers
    #     while True:
    #         mutated = False
    #         # Find all elements inside our targeted tree
    #         for tag in soup.find_all(True):
    #             # Skip globally protected structural elements
    #             if tag.name in void_elements:
    #                 continue
                    
    #             # Check if the tag has absolutely no text or functional child data left
    #             raw_text = tag.get_text(strip=True)
    #             has_protected_child = any(child.name in void_elements for child in tag.find_all(True))
                
    #             if not raw_text and not has_protected_child:
    #                 tag.decompose()
    #                 mutated = True
    #                 break  # Break out to refresh soup tracking context
                    
    #         if not mutated:
    #             break
            
    #     if self.engine == "local":
    #         # STRIP ATTRIBUTES: Local models need raw semantic layout to save VRAM 
    #         # and avoid keyword distraction.
    #         for tag in soup.find_all(True):
    #             tag.attrs = {}
            
    #         print(len(str(soup)))
    #         # print(str(soup.prettify())[:6000])

    #         return soup.get_text(separator=" ", strip=True)
    #     else:
    #         # KEEP ATTRIBUTES: Cloud models need `class` and `id` tags 
    #         # so they can generate accurate CSS selectors.
    #         allowed_attrs = ['class', 'id']
    #         for tag in soup.find_all(True):
    #             tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed_attrs}
    #     print(len(str(soup)))
    #     print(str(soup)[:6000])
    #     return str(soup)

    def clean_html(self, html: str) -> str:
        soup = BeautifulSoup(html, 'lxml')
        
        # 1. Eliminate heavy operational components
        tags_to_remove = ['script', 'style', 'nav', 'footer', 'header', 'svg', 'iframe', 'noscript', 'dialog', 'form']
        for tag in tags_to_remove:
            for element in soup.find_all(tag):
                element.decompose()
        
        # 2. Extract the main layout area immediately
        core_element = None
        if soup.find('main'):
            core_element = soup.find('main')
        elif soup.find(id=re.compile(r'^(main|content|primary)$', re.IGNORECASE)):
            core_element = soup.find(id=re.compile(r'^(main|content|primary)$', re.IGNORECASE))
            
        if core_element:
            soup = BeautifulSoup(str(core_element), 'lxml')

        # 3. Target and remove heavy sidebar components inside main
        # This completely wipes out the massive list of categories and filters!
        # FUTURE DATABASE TABLE???
        noise_selectors = [
            'aside', '.sidebar', '#sidebar', '.widget-area', 
            '.related', '.upsells', '.cross-sells', '.product-carousel',
            '.woocommerce-tabs', '#reviews', '.social-share', '.cookie-notice'
        ]
        for selector in noise_selectors:
            for element in soup.select(selector):
                element.decompose()

        # 4. Engine-Specific Formatting Layer
        if self.engine == "local":
            # Strip all attributes to avoid token weight inflation
            for tag in soup.find_all(True):
                tag.attrs = {}
            
            # Return straight string representation to retain the native indentation lines
            # that small models use as positional anchors
            print(len(str(soup)))
            print(soup.prettify()[:6000])
            return str(soup)
            
        else:
            allowed_attrs = ['class', 'id']
            for tag in soup.find_all(True):
                tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed_attrs}

        print(len(str(soup)))
        return str(soup)

    def extract_details(self, cleaned_html: str, target_title: str) -> dict:
        user_content = SEMANTIC_USER_PROMPT.format(
            target_title=target_title,
            cleaned_html=cleaned_html
        )

        return self._call_llm(user_content, SEMANTIC_SYSTEM_PROMPT)


    
    def extract_selectors(self, cleaned_html: str, target_title: str) -> dict:
        user_content = SELECTOR_USER_PROMPT.format(
            target_title=target_title,
            cleaned_html=cleaned_html
        )
        raw_response = self._call_llm(user_content, SELECTOR_SYSTEM_PROMPT)

        if "error" in raw_response:
            return raw_response

        return raw_response.get("selectors", {})

    def _call_llm(self, user_content: str, system_prompt: str) -> dict:
        try:
            kwargs = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.0,
            }

            if self.model_name != "openrouter/free":
                kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**kwargs)
            
            if not response or getattr(response, "choices", None) is None:
                err_msg = "OpenRouter routing constraint failure (choices field is missing/None)."
                if hasattr(response, "error") and response.error:
                    err_msg = f"OpenRouter Backend Error: {response.error}"
                return {"error": err_msg}
                
            if len(response.choices) == 0:
                return {"error": "OpenRouter returned an empty choices selection array."}
            
            resolved_model = getattr(response, 'model', 'Unknown Fallback Model')
            print(f"📡 OpenRouter Router Resolved to: {resolved_model}")
                
            raw_content = response.choices[0].message.content
            if not raw_content:
                return {"error": "Model executed but returned an empty response string."}
                
            raw_content = raw_content.strip()

            if raw_content.startswith("```"):
                lines = raw_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_content = "\n".join(lines).strip()

            return json.loads(raw_content)
        
        except Exception as e:
            return {"error": f"LLM Request Failure: {e}"}