from fastapi import APIRouter, Depends
from typing import List
import aiosqlite

from app.database import get_db

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("/", response_model=List[str])
async def list_tags(db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute(
        """
        SELECT t.name, COUNT(bt.bookmark_id) AS cnt
        FROM tags t
        JOIN bookmark_tags bt ON bt.tag_id = t.id
        GROUP BY t.id
        ORDER BY cnt DESC, t.name
        """
    ) as cur:
        rows = await cur.fetchall()
    return [r["name"] for r in rows]
