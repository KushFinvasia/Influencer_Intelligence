import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.crawlers.youtube import YouTubeCrawler
from app.crawlers.instagram import InstagramCrawler
from app.schemas.creator import RawProfile

@pytest.fixture
def mock_youtube_service():
    with patch("app.crawlers.youtube.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        yield mock_service

@pytest.mark.asyncio
async def test_youtube_crawler_metrics(mock_youtube_service):
    crawler = YouTubeCrawler()
    crawler._service = mock_youtube_service
    
    # Mock search keywords to avoid actually hitting the API
    async def mock_search_keywords(keywords):
        channel_ids = {"c1", "c2", "c3"}
        metrics = {
            "kw1": {"category": "generic", "results_found": 2, "new_creators": 2},
            "kw2": {"category": "broker", "results_found": 2, "new_creators": 1},
        }
        channel_discovery_map = {
            "c1": [{"term": "kw1", "category": "generic"}],
            "c2": [{"term": "kw1", "category": "generic"}, {"term": "kw2", "category": "broker"}],
            "c3": [{"term": "kw2", "category": "broker"}],
        }
        # Simulate updating _discovered_ids as search_keywords normally would
        crawler._discovered_ids.update(channel_ids)
        return channel_ids, metrics, channel_discovery_map
        
    # Mock _batch_fetch_channels to just return dummy RawProfiles
    async def mock_batch_fetch(c_ids, channel_discovery_map=None):
        profiles = []
        for cid in c_ids:
            profiles.append(
                RawProfile(
                    platform="youtube",
                    platform_user_id=cid,
                    username=f"user_{cid}",
                    discovered_via=channel_discovery_map.get(cid, []) if channel_discovery_map else []
                )
            )
        return profiles

    with patch.object(crawler, "_search_keywords", side_effect=mock_search_keywords), \
         patch.object(crawler, "_batch_fetch_channels", side_effect=mock_batch_fetch):

        keywords = [
            {"term": "kw1", "category": "generic"},
            {"term": "kw2", "category": "broker"}
        ]
        
        profiles, metrics = await crawler.discover(keywords, max_depth=1)
        
        assert len(profiles) == 3
        assert metrics["kw1"]["new_creators"] == 2
        assert metrics["kw2"]["new_creators"] == 1
        
        # Verify discovered_via is properly injected
        c2_profile = next(p for p in profiles if p.platform_user_id == "c2")
        assert len(c2_profile.discovered_via) == 2
        assert {"term": "kw1", "category": "generic"} in c2_profile.discovered_via
        assert {"term": "kw2", "category": "broker"} in c2_profile.discovered_via

@pytest.mark.asyncio
async def test_instagram_crawler_metrics():
    crawler = InstagramCrawler()
    
    async def mock_search_hashtags(hashtags):
        metrics = {
            "kw1": {"category": "generic", "results_found": 2, "new_creators": 2},
            "kw2": {"category": "broker", "results_found": 2, "new_creators": 1},
        }
        profiles = [
            RawProfile(
                platform="instagram",
                platform_user_id="u1",
                username="u1",
                discovered_via=[{"term": "kw1", "category": "generic"}]
            ),
            RawProfile(
                platform="instagram",
                platform_user_id="u2",
                username="u2",
                discovered_via=[{"term": "kw1", "category": "generic"}, {"term": "kw2", "category": "broker"}]
            ),
            RawProfile(
                platform="instagram",
                platform_user_id="u3",
                username="u3",
                discovered_via=[{"term": "kw2", "category": "broker"}]
            ),
        ]
        return profiles, metrics

    with patch.object(crawler, "_search_hashtags_profiles", side_effect=mock_search_hashtags), \
         patch.object(crawler, "_fetch_profiles", return_value=[]):

        keywords = [
            {"term": "kw1", "category": "generic"},
            {"term": "kw2", "category": "broker"}
        ]
        
        profiles, metrics = await crawler.discover(keywords, max_depth=1)
        
        assert len(profiles) == 3
        assert metrics["kw1"]["new_creators"] == 2
        assert metrics["kw2"]["new_creators"] == 1
        
        u2_profile = next(p for p in profiles if p.platform_user_id == "u2")
        assert len(u2_profile.discovered_via) == 2
        assert {"term": "kw2", "category": "broker"} in u2_profile.discovered_via
