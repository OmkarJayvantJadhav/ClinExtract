import uuid

from src.api.routes.analytics import get_analytics_metrics
from src.db.models.document import Document, DocumentStatus
from src.db.models.extraction import Extraction


async def test_fallback_count_ignores_extractions_without_fallback(db_session, user):
    before = (await get_analytics_metrics(db=db_session, current_user=user))["extraction"]["fallback_count"]

    for fallback in (None, {"original_extractor": "llm", "error": "timeout"}):
        doc = Document(uploader_id=user.id, filename="a.pdf", storage_key=f"k-{uuid.uuid4()}",
                       doc_type="application/pdf", status=DocumentStatus.AUTO_ACCEPTED)
        db_session.add(doc)
        await db_session.flush()
        db_session.add(Extraction(document_id=doc.id, provider="t", fallback_metadata=fallback))
    await db_session.commit()

    after = (await get_analytics_metrics(db=db_session, current_user=user))["extraction"]["fallback_count"]
    assert after - before == 1
