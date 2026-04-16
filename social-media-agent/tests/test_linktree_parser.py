"""Tests for the Linktree/link-in-bio parser.

These tests use sample HTML — no network calls needed.
"""

import pytest

from social_agent.research.niche_profiler import extract_linktree, _PLATFORM_PATTERNS


# ── Sample HTML fixtures ───────────────────────────────────────────────────

SAMPLE_LINKTREE_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Alex Tech | Linktree</title>
<meta name="description" content="Developer advocate & content creator">
</head>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "account": {
        "pageTitle": "Alex Tech",
        "username": "alextech",
        "description": "Developer advocate sharing Python tips, AI insights, and career advice.",
        "profilePictureUrl": "https://cdn.linktr.ee/avatar.jpg"
      },
      "links": [
        {"title": "Follow me on Twitter", "url": "https://twitter.com/AlexTech"},
        {"title": "TikTok", "url": "https://tiktok.com/@alextech"},
        {"title": "Instagram", "url": "https://instagram.com/alextech"},
        {"title": "YouTube Channel", "url": "https://youtube.com/@AlexTech"},
        {"title": "My Python Course", "url": "https://mycourse.com/python"},
        {"title": "GitHub", "url": "https://github.com/alextech"},
        {"title": "LinkedIn", "url": "https://linkedin.com/in/alex-tech"}
      ]
    }
  }
}
</script>
</body>
</html>
"""

SAMPLE_PLAIN_HTML = """
<!DOCTYPE html>
<html>
<head><title>Jane Creator</title></head>
<body>
<a href="https://x.com/janecreator">Twitter/X</a>
<a href="https://www.tiktok.com/@jane.creator">My TikToks</a>
<a href="https://www.instagram.com/janecreator">Instagram</a>
<a href="https://youtube.com/c/JaneCreator">YouTube</a>
<a href="https://janecreator.com">My Website</a>
<a href="https://twitch.tv/janecreator">Twitch</a>
</body>
</html>
"""


# ── Tests ──────────────────────────────────────────────────────────────────


class TestLinktreeParser:
    """Test extract_linktree with mocked HTTP responses."""

    def test_extracts_name_from_next_data(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert result["name"] == "Alex Tech"

    def test_extracts_bio_from_next_data(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert "Python" in result["bio"]

    def test_extracts_all_links(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert len(result["links"]) == 7

    def test_classifies_twitter(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert "twitter" in result["platforms"]
        assert "twitter.com/AlexTech" in result["platforms"]["twitter"]

    def test_classifies_tiktok(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert "tiktok" in result["platforms"]

    def test_classifies_instagram(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert "instagram" in result["platforms"]

    def test_classifies_youtube(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert "youtube" in result["platforms"]

    def test_classifies_github(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert "github" in result["platforms"]

    def test_classifies_linkedin(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert "linkedin" in result["platforms"]

    def test_puts_unclassified_in_other_links(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_LINKTREE_HTML))
        result = extract_linktree("https://linktr.ee/alextech")
        assert any("mycourse.com" in link for link in result["other_links"])

    def test_fallback_html_parsing(self, monkeypatch):
        """When there's no __NEXT_DATA__, falls back to extracting hrefs."""
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_PLAIN_HTML))
        result = extract_linktree("https://bio.link/jane")
        assert "twitter" in result["platforms"]
        assert "tiktok" in result["platforms"]
        assert "instagram" in result["platforms"]

    def test_x_dot_com_recognized_as_twitter(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_PLAIN_HTML))
        result = extract_linktree("https://bio.link/jane")
        assert "twitter" in result["platforms"]
        assert "x.com" in result["platforms"]["twitter"]

    def test_handles_network_error_gracefully(self, monkeypatch):
        def raise_error(*args, **kwargs):
            raise ConnectionError("Network down")
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get", raise_error)
        result = extract_linktree("https://linktr.ee/broken")
        assert "error" in result

    def test_extracts_name_from_title_tag_fallback(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_PLAIN_HTML))
        result = extract_linktree("https://bio.link/jane")
        assert result["name"] == "Jane Creator"

    def test_twitch_classified(self, monkeypatch):
        monkeypatch.setattr("social_agent.research.niche_profiler.requests.get",
                            _mock_response(SAMPLE_PLAIN_HTML))
        result = extract_linktree("https://bio.link/jane")
        assert "twitch" in result["platforms"]


class TestPlatformPatterns:
    """Test the regex patterns directly."""

    def test_twitter_patterns(self):
        import re
        for pattern in _PLATFORM_PATTERNS["twitter"]:
            assert re.search(pattern, "https://twitter.com/testuser")
            assert re.search(pattern, "https://x.com/testuser")

    def test_tiktok_patterns(self):
        import re
        for pattern in _PLATFORM_PATTERNS["tiktok"]:
            assert re.search(pattern, "https://tiktok.com/@test.user")

    def test_instagram_patterns(self):
        import re
        for pattern in _PLATFORM_PATTERNS["instagram"]:
            assert re.search(pattern, "https://instagram.com/testuser")

    def test_youtube_patterns(self):
        import re
        patterns = _PLATFORM_PATTERNS["youtube"]
        assert any(re.search(p, "https://youtube.com/@TestChannel") for p in patterns)
        assert any(re.search(p, "https://youtube.com/c/TestChannel") for p in patterns)


# ── Helpers ────────────────────────────────────────────────────────────────


def _mock_response(html_content):
    """Create a mock requests.get that returns the given HTML."""
    def mock_get(*args, **kwargs):
        class MockResp:
            status_code = 200
            text = html_content
            def raise_for_status(self):
                pass
        return MockResp()
    return mock_get
