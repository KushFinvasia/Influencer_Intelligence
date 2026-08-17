"""Re-enrich all creators in the database with updated broker detection rules and video descriptions."""

import asyncio
import json
import logging
import re
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, delete
from app.config.settings import get_settings, get_brokers_config
from app.extractors.contact import ContactExtractor
from app.extractors.transcript import VideoTranscriptExtractor
from app.database.session import async_session_factory
from app.models.database import (
    Creator,
    PlatformProfile,
    SocialLink,
    BrokerAssociation,
)
from app.schemas.creator import RawProfile, ContactInfo, BrokerInfo
from app.services.enrichment import EnrichmentEngine
from app.crawlers.youtube import YouTubeCrawler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

URL_REGEX = re.compile(r"https?://[^\s<>\"'\)]+", re.IGNORECASE)


async def re_enrich_all():
    session_factory = async_session_factory
    enricher = EnrichmentEngine()
    contact_extractor = ContactExtractor()
    transcript_extractor = VideoTranscriptExtractor()
    yt_crawler = YouTubeCrawler()

    async with session_factory() as db:
        # 1. Fetch all creators and their platform profiles
        creators_res = await db.execute(select(Creator))
        creators = creators_res.scalars().all()
        logger.info("Found %d creators in database to re-enrich", len(creators))

        for creator in creators:
            logger.info("Processing creator #%d: %s", creator.id, creator.name)

            # Get platform profiles
            pp_res = await db.execute(
                select(PlatformProfile).where(PlatformProfile.creator_id == creator.id)
            )
            pps = pp_res.scalars().all()
            pp = pps[0] if pps else None

            links = []
            recent_titles = []
            video_descs = []
            video_ids = []

            for p_profile in pps:
                if p_profile.platform == "youtube" and p_profile.platform_user_id:
                    try:
                        # Fetch recent videos to get up-to-date description links and transcripts
                        videos = await yt_crawler.fetch_content(p_profile.platform_user_id, max_items=5)
                    for v in videos:
                        if v.video_id:
                            video_ids.append(v.video_id)
                        if v.title:
                            recent_titles.append(v.title)
                        if v.description:
                            video_descs.append(v.description)
                            for url in URL_REGEX.findall(v.description):
                                clean_u = url.rstrip(".,;)\"'>")
                                if clean_u not in links:
                                    links.append(clean_u)
                    
                    # Direct spoken language detection via transcripts
                    if video_ids:
                        t_lang = transcript_extractor.detect_channel_language(video_ids, max_videos=3)
                        if t_lang:
                            creator.primary_language = t_lang.primary_language
                            creator.language_confidence = t_lang.confidence
                            logger.info(" -> Spoken language from transcripts: %s (%.2f)", t_lang.primary_language, t_lang.confidence)
                except Exception as e:
                    logger.warning("Could not fetch videos for %s: %s", pp.platform_user_id, e)

            # Build combined description
            full_desc = (pp.description or "") if pp else ""
            if video_descs:
                full_desc += "\n" + "\n".join(video_descs)

            raw_profile = RawProfile(
                platform=pp.platform if pp else "youtube",
                platform_user_id=pp.platform_user_id if pp else "",
                username=pp.username if pp else creator.name,
                display_name=pp.display_name if pp else creator.name,
                bio=pp.bio if pp else "",
                description=full_desc,
                followers=pp.followers if pp else None,
                recent_video_titles=recent_titles,
                recent_video_descriptions=video_descs[:5],
                links=links,
            )

            # 1. Extract contacts and social links from bio, description, and last 5 video descriptions
            contacts = contact_extractor.extract(
                bio=raw_profile.bio or "",
                description=raw_profile.description or "",
                video_descriptions=raw_profile.recent_video_descriptions[:5],
                links=raw_profile.links,
            )

            # 2. Detect brokers with updated rules
            broker_detections = enricher.detect_brokers(raw_profile, contacts)

            # 3. Update Creator basic contact fields if found
            if contacts.emails and not creator.email:
                creator.email = contacts.emails[0]
            if contacts.phones and not creator.phone:
                creator.phone = contacts.phones[0]
            if contacts.website and not creator.website:
                creator.website = contacts.website[0]

            # 4. Refresh Broker Associations
            # Delete old associations for this creator to clear false positives
            await db.execute(
                delete(BrokerAssociation).where(BrokerAssociation.creator_id == creator.id)
            )

            for b in broker_detections:
                db.add(
                    BrokerAssociation(
                        creator_id=creator.id,
                        broker_name=b.broker_name,
                        relationship_type=b.relationship_type.value if b.relationship_type else "mention_only",
                        confidence=b.confidence,
                        detection_method=b.detection_method.value,
                        evidence=b.evidence,
                        evidence_urls=b.evidence_urls,
                    )
                )

            # 5. Upsert Social Links
            await db.execute(
                delete(SocialLink).where(SocialLink.creator_id == creator.id)
            )

            link_map = {
                "email": [(e, e) for e in contacts.emails],
                "phone": [(p, p) for p in contacts.phones],
                "telegram": [(u, u) for u in contacts.telegram],
                "whatsapp": [(u, u) for u in contacts.whatsapp],
                "linkedin": [(u, u) for u in contacts.linkedin],
                "twitter": [(u, u) for u in contacts.twitter],
                "facebook": [(u, u) for u in contacts.facebook],
                "discord": [(u, u) for u in contacts.discord],
                "website": [(u, u) for u in contacts.website],
                "linktree": [(u, u) for u in contacts.linktree],
                "beacons": [(u, u) for u in contacts.beacons],
            }

            for platform_key, entries in link_map.items():
                for url, val in entries:
                    db.add(
                        SocialLink(
                            creator_id=creator.id,
                            platform=platform_key,
                            url=url,
                            value=val,
                        )
                    )

            detected_names = [b.broker_name for b in broker_detections]
            logger.info(" -> Creator #%d [%s]: Detected Brokers: %s", creator.id, creator.name, detected_names or "None")

        await db.commit()
        logger.info("Successfully re-enriched all creators in database!")


if __name__ == "__main__":
    asyncio.run(re_enrich_all())
