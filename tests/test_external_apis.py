import importlib
import sys
import types
import unittest


class SteamSearchParsingTests(unittest.TestCase):
    def setUp(self):
        sys.modules.setdefault("pydantic_settings", types.SimpleNamespace(BaseSettings=object))

        fake_models = types.ModuleType("app.models")
        fake_content = types.ModuleType("app.models.content")

        class FakeContentType:
            MUSIC = "music"
            GAME = "game"
            MOVIE = "movie"

        class FakeContentPlatform:
            SPOTIFY = "spotify"
            STEAM = "steam"
            TMDB = "tmdb"
            GOODREADS = "goodreads"

        fake_content.ContentType = FakeContentType
        fake_content.ContentPlatform = FakeContentPlatform
        sys.modules["app.models"] = fake_models
        sys.modules["app.models.content"] = fake_content

        from app.core.external_apis import ExternalAPIClient

        self.client = ExternalAPIClient()
    def test_extracts_titles_from_steam_html_when_details_api_is_unavailable(self):
        html = """
        <div class="search_result_row" data-ds-appid="730">
            <span class="title">Counter-Strike 2</span>
            <div class="search_price">Free</div>
        </div>
        <div class="search_result_row" data-ds-appid="570">
            <span class="title">Dota 2</span>
        </div>
        """

        results = self.client._extract_steam_search_results(html, 5)

        self.assertEqual(results[0]["id"], "730")
        self.assertEqual(results[0]["title"], "Counter-Strike 2")
        self.assertEqual(results[1]["id"], "570")
        self.assertEqual(results[1]["title"], "Dota 2")


if __name__ == "__main__":
    unittest.main()
