"""Tests for the contact extractor module."""

import pytest
from app.extractors.contact import ContactExtractor


@pytest.fixture
def extractor():
    return ContactExtractor()


class TestEmailExtraction:
    def test_basic_email(self, extractor):
        contacts = extractor.extract(bio="Contact me at test@gmail.com")
        assert "test@gmail.com" in contacts.emails

    def test_multiple_emails(self, extractor):
        contacts = extractor.extract(
            bio="Email: work@company.in or personal@gmail.com"
        )
        assert len(contacts.emails) == 2

    def test_no_false_positive_image_extension(self, extractor):
        contacts = extractor.extract(bio="image@logo.png")
        assert len(contacts.emails) == 0

    def test_email_in_description(self, extractor):
        contacts = extractor.extract(
            description="Business inquiries: biz@example.org"
        )
        assert "biz@example.org" in contacts.emails


class TestPhoneExtraction:
    def test_indian_phone_with_country_code(self, extractor):
        contacts = extractor.extract(bio="Call +91 9876543210")
        assert "+919876543210" in contacts.phones

    def test_indian_phone_without_code(self, extractor):
        contacts = extractor.extract(bio="WhatsApp: 9876543210")
        assert "+919876543210" in contacts.phones

    def test_phone_with_dashes(self, extractor):
        contacts = extractor.extract(bio="Ph: 98765-43210")
        assert "+919876543210" in contacts.phones

    def test_invalid_phone_rejected(self, extractor):
        contacts = extractor.extract(bio="PIN: 123456")
        assert len(contacts.phones) == 0


class TestSocialLinkClassification:
    def test_telegram_link(self, extractor):
        contacts = extractor.extract(
            bio="Join https://t.me/stockgroup"
        )
        assert len(contacts.telegram) == 1

    def test_whatsapp_link(self, extractor):
        contacts = extractor.extract(
            bio="WhatsApp: https://wa.me/919876543210"
        )
        assert len(contacts.whatsapp) == 1

    def test_linkedin_link(self, extractor):
        contacts = extractor.extract(
            bio="Connect: https://linkedin.com/in/johndoe"
        )
        assert len(contacts.linkedin) == 1

    def test_twitter_link(self, extractor):
        contacts = extractor.extract(
            bio="Follow https://x.com/trader123"
        )
        assert len(contacts.twitter) == 1

    def test_linktree_link(self, extractor):
        contacts = extractor.extract(
            bio="All links: https://linktr.ee/myprofile"
        )
        assert len(contacts.linktree) == 1

    def test_discord_link(self, extractor):
        contacts = extractor.extract(
            bio="Discord: https://discord.gg/invite123"
        )
        assert len(contacts.discord) == 1


class TestWebsiteExtraction:
    def test_generic_website(self, extractor):
        contacts = extractor.extract(
            bio="Visit https://mywebsite.com/trading"
        )
        assert len(contacts.website) == 1

    def test_links_parameter(self, extractor):
        contacts = extractor.extract(
            links=["https://mysite.com", "https://t.me/channel"]
        )
        assert len(contacts.website) == 1
        assert len(contacts.telegram) == 1


class TestCombinedExtraction:
    def test_full_profile(self, extractor):
        contacts = extractor.extract(
            bio="Trader | Email: trade@gmail.com | +91 9876543210",
            description="Join our Telegram: https://t.me/stocktips",
            links=[
                "https://linktr.ee/mytree",
                "https://linkedin.com/in/trader",
            ],
        )
        assert len(contacts.emails) == 1
        assert len(contacts.phones) == 1
        assert len(contacts.telegram) == 1
        assert len(contacts.linktree) == 1
        assert len(contacts.linkedin) == 1
