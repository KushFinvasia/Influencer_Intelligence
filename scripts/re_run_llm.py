import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, update
from app.database.session import async_session_factory
from app.models.database import Creator, PlatformProfile
from app.schemas.creator import RawProfile, EnrichedProfile
from app.pipelines.discovery import DiscoveryPipeline
from app.services.creator_service import CreatorService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def re_run_llm():
    pipeline = DiscoveryPipeline()
    session_factory = async_session_factory

    async with session_factory() as db:
        service = CreatorService(db)
        # Fetch all creators to ensure they are fully enriched with the new keys
        creators_res = await db.execute(select(Creator))
        creators = creators_res.scalars().all()
        
        logger.info(f"Found {len(creators)} creators needing LLM enrichment.")

        for creator in creators:
            logger.info(f"Processing creator: {creator.name} ({creator.id})")
            
            # Fetch Platform Profile
            pp_res = await db.execute(
                select(PlatformProfile).where(PlatformProfile.creator_id == creator.id)
            )
            pp = pp_res.scalar_one_or_none()

            raw_profile = RawProfile(
                platform=pp.platform if pp else "unknown",
                platform_user_id=pp.platform_user_id if pp else "",
                username=pp.username if pp else creator.name,
                display_name=pp.display_name if pp else creator.name,
                bio=pp.bio if pp else "",
                description=pp.description if pp else "",
                followers=pp.followers if pp else 0,
            )

            llm_input = pipeline.preprocessor.prepare_llm_input(raw_profile)
            
            classification = await pipeline._run_llm_classification(
                llm_input=llm_input,
                rule_brokers=[],
                service=service,
                db=db,
                profile=raw_profile
            )

            if classification:
                creator.primary_category = classification.primary_category
                
                # Check for is_financial_creator on creator model. If it doesn't exist, skip it.
                if hasattr(creator, 'is_financial_creator'):
                    creator.is_financial_creator = classification.is_financial_creator
                if hasattr(creator, 'relevance_score'):
                    creator.relevance_score = classification.relevance_score
                
                if classification.is_financial_creator is False:
                    logger.warning(f"Creator {creator.name} marked as NON-financial by LLM.")
                    creator.needs_review = True
                    creator.review_reason = "Failed LLM relevance gatekeeper"

            await db.commit()
            
            logger.info("Sleeping for 5 seconds to avoid Groq rate limits...")
            await asyncio.sleep(5)
            
        logger.info("LLM re-enrichment complete.")

if __name__ == "__main__":
    asyncio.run(re_run_llm())
