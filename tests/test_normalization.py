"""Tests for the normalization module."""

import pytest
from app.normalization.normalizer import Normalizer


@pytest.fixture
def normalizer():
    return Normalizer()


class TestBrokerNormalization:
    def test_angel_broking_to_angel_one(self, normalizer):
        assert normalizer.normalize_broker("angel broking") == "Angel One"

    def test_angelone_to_angel_one(self, normalizer):
        assert normalizer.normalize_broker("angelone") == "Angel One"

    def test_kite_to_zerodha(self, normalizer):
        assert normalizer.normalize_broker("kite") == "Zerodha"

    def test_already_canonical(self, normalizer):
        assert normalizer.normalize_broker("Zerodha") == "Zerodha"

    def test_unknown_broker(self, normalizer):
        assert normalizer.normalize_broker("Unknown Broker") == "Unknown Broker"


class TestCategoryNormalization:
    def test_fno_alias(self, normalizer):
        assert normalizer.normalize_category("FnO") == "F&O"

    def test_f_and_o_alias(self, normalizer):
        assert normalizer.normalize_category("F and O") == "F&O"

    def test_options_trading_alias(self, normalizer):
        assert normalizer.normalize_category("Options Trading") == "F&O"

    def test_technical_analyst_alias(self, normalizer):
        assert normalizer.normalize_category("Technical Analyst") == "Technical Analysis"

    def test_sip_to_mutual_funds(self, normalizer):
        assert normalizer.normalize_category("SIP") == "Mutual Funds"

    def test_day_trading_to_intraday(self, normalizer):
        assert normalizer.normalize_category("Day Trading") == "Intraday"

    def test_valid_category_unchanged(self, normalizer):
        assert normalizer.normalize_category("Equity") == "Equity"


class TestLanguageNormalization:
    def test_hindi_script(self, normalizer):
        assert normalizer.normalize_language("हिन्दी") == "Hindi"

    def test_hinglish_to_mixed(self, normalizer):
        assert normalizer.normalize_language("Hinglish") == "Mixed"

    def test_tamil_script(self, normalizer):
        assert normalizer.normalize_language("தமிழ்") == "Tamil"

    def test_valid_language_unchanged(self, normalizer):
        assert normalizer.normalize_language("English") == "English"


class TestCreatorTypeNormalization:
    def test_teacher_to_educator(self, normalizer):
        assert normalizer.normalize_creator_type("Teacher") == "Educator"

    def test_finfluencer_to_influencer(self, normalizer):
        assert normalizer.normalize_creator_type("Finfluencer") == "Influencer"

    def test_day_trader_to_trader(self, normalizer):
        assert normalizer.normalize_creator_type("Day Trader") == "Trader"

    def test_sub_broker_to_representative(self, normalizer):
        assert normalizer.normalize_creator_type("Sub Broker") == "Broker Representative"


class TestURLNormalization:
    def test_removes_protocol(self, normalizer):
        result = normalizer.normalize_url("https://www.example.com/page/")
        assert result == "example.com/page"

    def test_removes_www(self, normalizer):
        result = normalizer.normalize_url("http://www.test.com")
        assert result == "test.com"

    def test_removes_trailing_slash(self, normalizer):
        result = normalizer.normalize_url("https://site.com/")
        assert result == "site.com"

    def test_lowercases(self, normalizer):
        result = normalizer.normalize_url("https://SITE.COM/Page")
        assert result == "site.com/page"
