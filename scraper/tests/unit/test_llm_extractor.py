import json

import pytest
from bs4 import BeautifulSoup
from unittest.mock import MagicMock

from pipeline.llm_extractor import Extractor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_extractor(**overrides) -> Extractor:
    config = {
        "api_base": "http://test.invalid/v1",
        "model_name": "test-model",
        "engine": "full",
    }
    config.update(overrides)
    return Extractor(config)


def _mock_response(content: str, model: str = "test-model-resolved") -> MagicMock:
    """Builds a MagicMock shaped like an OpenAI ChatCompletion response."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    response.model = model
    return response


SAMPLE_HTML = """
<html>
  <body>
    <main id="content">
      <div class="price-wrap" data-testid="price" id="price-123">
        <span>LKR 1,500.00</span>
      </div>
    </main>
  </body>
</html>
"""


# ---------------------------------------------------------------------------
# __init__ — config validation
# ---------------------------------------------------------------------------


class TestExtractorInit:
    def test_missing_api_base_raises(self):
        with pytest.raises(ValueError):
            Extractor({"model_name": "test-model"})

    def test_missing_model_name_raises(self):
        with pytest.raises(ValueError):
            Extractor({"api_base": "http://test.invalid/v1"})

    def test_missing_both_raises(self):
        with pytest.raises(ValueError):
            Extractor({})

    def test_valid_config_does_not_raise(self):
        extractor = _make_extractor()
        assert extractor.api_base == "http://test.invalid/v1"
        assert extractor.model_name == "test-model"

    def test_api_key_defaults_when_omitted(self):
        extractor = _make_extractor()
        assert extractor.api_key == "not-needed"

    def test_api_key_defaults_when_empty_string(self):
        # Regression test: os.environ.get(..., "") used to defeat this default,
        # since dict.get(key, default) only falls back on a *missing* key, not
        # a present-but-falsy one.
        extractor = _make_extractor(api_key="")
        assert extractor.api_key == "not-needed"

    def test_api_key_uses_explicit_value_when_provided(self):
        extractor = _make_extractor(api_key="sk-real-key")
        assert extractor.api_key == "sk-real-key"

    def test_engine_defaults_to_stripped(self):
        extractor = Extractor({"api_base": "http://test.invalid/v1", "model_name": "x"})
        assert extractor.engine == "stripped"


# ---------------------------------------------------------------------------
# clean_html — engine branching and structural cleanup
# ---------------------------------------------------------------------------


class TestCleanHtml:
    def test_stripped_engine_removes_all_attributes(self):
        extractor = _make_extractor(engine="stripped")
        cleaned = extractor.clean_html(SAMPLE_HTML)
        soup = BeautifulSoup(cleaned, "lxml")
        for tag in soup.find_all(True):
            assert tag.attrs == {}

    def test_full_engine_keeps_class_and_id_values(self):
        extractor = _make_extractor(engine="full")
        cleaned = extractor.clean_html(SAMPLE_HTML)
        soup = BeautifulSoup(cleaned, "lxml")
        price_div = soup.find(id="price-123")
        assert price_div is not None
        assert price_div.get("class") == ["price-wrap"]

    def test_full_engine_strips_non_allowlisted_attributes(self):
        extractor = _make_extractor(engine="full")
        cleaned = extractor.clean_html(SAMPLE_HTML)
        soup = BeautifulSoup(cleaned, "lxml")
        for tag in soup.find_all(True):
            assert "data-testid" not in tag.attrs

    def test_removes_script_and_style_tags(self):
        html = (
            "<html><body><script>alert(1)</script>"
            "<style>.x{color:red}</style><p>Price LKR 1,500</p></body></html>"
        )
        extractor = _make_extractor()
        cleaned = extractor.clean_html(html)
        assert "<script" not in cleaned
        assert "<style" not in cleaned
        assert "1,500" in cleaned

    def test_removes_sidebar_noise(self):
        html = """
        <html><body>
          <main>
            <div class="price">LKR 1,500.00</div>
            <aside class="sidebar"><p>Related products</p></aside>
          </main>
        </body></html>
        """
        extractor = _make_extractor()
        cleaned = extractor.clean_html(html)
        assert "Related products" not in cleaned
        assert "1,500.00" in cleaned

    def test_extracts_main_content_only(self):
        # promo-banner sits outside <main> and isn't in tags_to_remove or
        # noise_selectors — its disappearance can only be explained by the
        # main-content extraction step, not the other cleanup steps.
        html = """
        <html><body>
          <div class="promo-banner">Buy 2 get 1 free sitewide</div>
          <main><div class="price">LKR 1,500.00</div></main>
        </body></html>
        """
        extractor = _make_extractor()
        cleaned = extractor.clean_html(html)
        assert "1,500.00" in cleaned
        assert "Buy 2 get 1 free" not in cleaned


# ---------------------------------------------------------------------------
# _call_llm / _attempt — retry behavior, parsing, malformed responses
# ---------------------------------------------------------------------------


class TestCallLlm:
    def test_returns_parsed_json_on_success(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response(
            json.dumps({"price": "LKR 1,500.00"})
        )
        result = extractor._call_llm("some html", "system prompt")
        assert result == {"price": "LKR 1,500.00"}

    def test_strips_markdown_code_fences(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        fenced = "```json\n" + json.dumps({"price": "LKR 1,500.00"}) + "\n```"
        extractor.client.chat.completions.create.return_value = _mock_response(fenced)
        result = extractor._call_llm("some html", "system prompt")
        assert result == {"price": "LKR 1,500.00"}

    def test_json_mode_requested_on_first_attempt(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response(
            json.dumps({"price": "x"})
        )
        extractor._call_llm("html", "prompt")
        _, kwargs = extractor.client.chat.completions.create.call_args
        assert kwargs.get("response_format") == {"type": "json_object"}

    def test_retries_without_json_mode_when_first_attempt_raises(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        # First call (json_mode=True) raises — simulates a backend that
        # rejects the response_format param. Second call (json_mode=False)
        # succeeds.
        extractor.client.chat.completions.create.side_effect = [
            Exception("response_format not supported"),
            _mock_response(json.dumps({"price": "LKR 1,500.00"})),
        ]
        result = extractor._call_llm("some html", "system prompt")
        assert result == {"price": "LKR 1,500.00"}
        assert extractor.client.chat.completions.create.call_count == 2

    def test_returns_error_dict_when_both_attempts_fail(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.side_effect = Exception("backend down")
        result = extractor._call_llm("some html", "system prompt")
        assert "error" in result

    def test_empty_choices_array_returns_error(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        response = MagicMock()
        response.choices = []
        extractor.client.chat.completions.create.return_value = response
        result = extractor._call_llm("some html", "system prompt")
        assert "error" in result

    def test_none_choices_returns_error(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        response = MagicMock()
        response.choices = None
        extractor.client.chat.completions.create.return_value = response
        result = extractor._call_llm("some html", "system prompt")
        assert "error" in result

    def test_empty_content_string_returns_error(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response("")
        result = extractor._call_llm("some html", "system prompt")
        assert "error" in result


# ---------------------------------------------------------------------------
# extract_selectors / extract_details — prompt formatting passthrough
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# classify_stock_status — short-text-only LLM fallback, no HTML/engine involved
# ---------------------------------------------------------------------------


class TestClassifyStockStatus:
    def test_true_response_returns_true(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response("TRUE")
        assert extractor.classify_stock_status("Low stock: 4 left") is True

    def test_false_response_returns_false(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response("FALSE")
        assert extractor.classify_stock_status("Currently unavailable-ish") is False

    def test_response_is_case_insensitive(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response("true")
        assert extractor.classify_stock_status("some text") is True

    def test_unknown_response_returns_none(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response(
            "UNKNOWN"
        )
        assert extractor.classify_stock_status("ambiguous text") is None

    def test_unexpected_content_returns_none(self):
        # Neither TRUE nor FALSE appears anywhere in the response
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response(
            "I cannot determine this."
        )
        assert extractor.classify_stock_status("some text") is None

    def test_empty_content_returns_none(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response("")
        assert extractor.classify_stock_status("some text") is None

    def test_none_choices_returns_none(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        response = MagicMock()
        response.choices = None
        extractor.client.chat.completions.create.return_value = response
        assert extractor.classify_stock_status("some text") is None

    def test_empty_choices_array_returns_none(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        response = MagicMock()
        response.choices = []
        extractor.client.chat.completions.create.return_value = response
        assert extractor.classify_stock_status("some text") is None

    def test_exception_returns_none_not_raise(self):
        # Mirrors _call_llm's resilience: a broke/unreachable backend here
        # must fall through to None (letting the caller keep the existing
        # ERROR status) rather than propagate and crash the pipeline run.
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.side_effect = Exception("backend down")
        assert extractor.classify_stock_status("some text") is None

    def test_uses_configured_model_name(self):
        extractor = _make_extractor(model_name="my-direct-model")
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response("TRUE")
        extractor.classify_stock_status("some text")
        _, kwargs = extractor.client.chat.completions.create.call_args
        assert kwargs["model"] == "my-direct-model"

    def test_raw_text_passed_through_to_prompt(self):
        extractor = _make_extractor()
        extractor.client = MagicMock()
        extractor.client.chat.completions.create.return_value = _mock_response("TRUE")
        extractor.classify_stock_status("Low stock: 4 left")
        _, kwargs = extractor.client.chat.completions.create.call_args
        user_message = kwargs["messages"][1]["content"]
        assert "Low stock: 4 left" in user_message


class TestExtractWrappers:
    def test_extract_selectors_returns_selectors_key_contents(self, monkeypatch):
        extractor = _make_extractor()
        monkeypatch.setattr(
            extractor,
            "_call_llm",
            lambda *args, **kwargs: {"selectors": {"price": {"selector": ".price"}}},
        )
        result = extractor.extract_selectors("<html></html>", "Some Book")
        assert result == {"price": {"selector": ".price"}}

    def test_extract_selectors_passes_through_error(self, monkeypatch):
        extractor = _make_extractor()
        monkeypatch.setattr(
            extractor, "_call_llm", lambda *args, **kwargs: {"error": "boom"}
        )
        result = extractor.extract_selectors("<html></html>", "Some Book")
        assert result == {"error": "boom"}

    def test_extract_details_passes_fields_through_to_prompt(self, monkeypatch):
        extractor = _make_extractor()
        captured = {}

        def fake_call_llm(user_content, system_prompt):
            captured["user_content"] = user_content
            return {"price": "LKR 1,500.00"}

        monkeypatch.setattr(extractor, "_call_llm", fake_call_llm)
        result = extractor.extract_details(
            "<html></html>", "Some Book", fields=["price"]
        )
        assert result == {"price": "LKR 1,500.00"}
        assert "price" in captured["user_content"]
