import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import async_session
from app.models.job import TranslationResult

logger = logging.getLogger(__name__)
router = APIRouter()

_connections: dict[str, list[WebSocket]] = {}


@router.websocket("/api/ws/jobs/{job_id}")
async def job_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    if job_id not in _connections:
        _connections[job_id] = []
    _connections[job_id].append(websocket)
    try:
        while True:
            async with async_session() as db:
                results = (await db.execute(
                    select(TranslationResult).where(TranslationResult.job_id == uuid.UUID(job_id))
                )).scalars().all()
                status_update = {
                    "type": "status",
                    "results": [
                        {"language": r.language, "status": r.status}
                        for r in results
                    ],
                }
                await websocket.send_text(json.dumps(status_update))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    finally:
        if job_id in _connections:
            _connections[job_id].remove(websocket)
