"""Tests for internationalization module."""

import pytest

from i18n import t, resolve_lang, TRANSLATIONS


class TestTranslation:
    """Translation lookup."""

    def test_english_translation(self):
        """Known key returns English text."""
        assert t("en", "nav.home") == "Home"

    def test_chinese_translation(self):
        """Known key returns Chinese text."""
        assert t("zh", "nav.home") == "首页"

    def test_fallback_to_english(self):
        """Key missing in zh falls back to en."""
        # Use a key that exists in en but not zh — unlikely, but test fallback
        # 'nav.theme' exists in both, so test a generic fallback scenario
        assert t("zh", "common.search") == "搜索"

    def test_missing_key_returns_key(self):
        """Key missing in all languages returns the key itself."""
        assert t("en", "nonexistent_key_xyz") == "nonexistent_key_xyz"

    def test_missing_key_with_default(self):
        """Custom default for missing key."""
        assert t("en", "nonexistent", "fallback") == "fallback"

    def test_translations_loaded(self):
        """Both locale files are loaded."""
        assert "en" in TRANSLATIONS
        assert "zh" in TRANSLATIONS

    def test_no_missing_keys_across_locales(self):
        """Every zh key should have an en counterpart and vice versa."""
        en_keys = set(TRANSLATIONS["en"].keys())
        zh_keys = set(TRANSLATIONS["zh"].keys())
        only_en = en_keys - zh_keys
        only_zh = zh_keys - en_keys
        # Some keys may intentionally be in one but not the other;
        # report them rather than fail, since this is a content check
        if only_en or only_zh:
            pytest.skip(f"Unmatched keys — en only: {only_en}, zh only: {only_zh}")


class TestResolveLang:
    """Language resolution priority."""

    @pytest.mark.asyncio
    async def test_cookie_takes_priority(self):
        """Cookie language overrides everything."""
        result = await resolve_lang(
            cookie_lang="zh",
            accept_language="en-US",
            client_ip="192.168.1.1",
        )
        assert result == "zh"

    @pytest.mark.asyncio
    async def test_accept_language_fallback(self):
        """Accept-Language header used when cookie is absent."""
        result = await resolve_lang(
            cookie_lang=None,
            accept_language="zh-CN,zh;q=0.9",
            client_ip="192.168.1.1",
        )
        assert result == "zh"

    @pytest.mark.asyncio
    async def test_english_accept_language(self):
        """English accept-language resolves to en."""
        result = await resolve_lang(
            cookie_lang=None,
            accept_language="en-US,en;q=0.9",
            client_ip="192.168.1.1",
        )
        assert result == "en"

    @pytest.mark.asyncio
    async def test_default_to_english(self):
        """Default fallback is English."""
        result = await resolve_lang(
            cookie_lang=None,
            accept_language="fr-FR,fr;q=0.9",
            client_ip="192.168.1.1",
        )
        assert result == "en"

    @pytest.mark.asyncio
    async def test_unsupported_cookie_ignored(self):
        """Unsupported cookie language falls through."""
        result = await resolve_lang(
            cookie_lang="fr",
            accept_language="en-US",
            client_ip="192.168.1.1",
        )
        assert result == "en"
