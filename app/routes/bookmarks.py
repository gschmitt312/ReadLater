import csv
import io
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import aiosqlite

from app.database import get_db
from app.models import BookmarkCreate, BookmarkOut, BookmarkUpdate
from app.utils.metadata import detect_type, fetch_metadata

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


async def _attach_tags(db: aiosqlite.Connection, bookmark_id: int) -> List[str]:
    async with db.execute(
        """
        SELECT t.name FROM tags t
        JOIN bookmark_tags bt ON bt.tag_id = t.id
        WHERE bt.bookmark_id = ?
        ORDER BY t.name
        """,
        (bookmark_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [r["name"] for r in rows]


async def _ensure_tags(db: aiosqlite.Connection, bookmark_id: int, tag_names: List[str]):
    # Remove existing associations
    await db.execute("DELETE FROM bookmark_tags WHERE bookmark_id = ?", (bookmark_id,))
    for name in tag_names:
        name = name.strip().lower()
        if not name:
            continue
        await db.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,))
        async with db.execute("SELECT id FROM tags WHERE name = ?", (name,)) as cur:
            row = await cur.fetchone()
        await db.execute(
            "INSERT OR IGNORE INTO bookmark_tags(bookmark_id, tag_id) VALUES (?, ?)",
            (bookmark_id, row["id"]),
        )


@router.post("/", response_model=BookmarkOut, status_code=201)
async def create_bookmark(payload: BookmarkCreate, db: aiosqlite.Connection = Depends(get_db)):
    url = payload.url.strip()

    # Check for duplicate
    async with db.execute("SELECT id FROM bookmarks WHERE url = ?", (url,)) as cur:
        if await cur.fetchone():
            raise HTTPException(status_code=409, detail="Bookmark already exists")

    kind = detect_type(url)
    title, description, thumbnail = await fetch_metadata(url)

    await db.execute(
        """
        INSERT INTO bookmarks(url, title, description, thumbnail, type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (url, title, description, thumbnail, kind),
    )
    async with db.execute("SELECT last_insert_rowid() AS id") as cur:
        row = await cur.fetchone()
    bookmark_id = row["id"]

    if payload.tags:
        await _ensure_tags(db, bookmark_id, payload.tags)

    await db.commit()
    return await _get_bookmark(db, bookmark_id)


@router.get("/", response_model=List[BookmarkOut])
async def list_bookmarks(
    q: Optional[str] = Query(None, description="Full-text search"),
    tag: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    read: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: aiosqlite.Connection = Depends(get_db),
):
    params: list = []

    if q:
        sql = """
            SELECT b.* FROM bookmarks b
            JOIN bookmarks_fts fts ON fts.rowid = b.id
            WHERE bookmarks_fts MATCH ?
        """
        params.append(q)
    else:
        sql = "SELECT b.* FROM bookmarks b WHERE 1=1"

    if tag:
        sql += """
            AND b.id IN (
                SELECT bt.bookmark_id FROM bookmark_tags bt
                JOIN tags t ON t.id = bt.tag_id
                WHERE t.name = ?
            )
        """
        params.append(tag.lower())

    if type:
        sql += " AND b.type = ?"
        params.append(type)

    if read is not None:
        sql += " AND b.read = ?"
        params.append(1 if read else 0)

    sql += " ORDER BY b.created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()

    result = []
    for row in rows:
        tags = await _attach_tags(db, row["id"])
        result.append(_row_to_out(row, tags))
    return result


@router.get("/export")
async def export_bookmarks(
    fmt: str = Query("json", regex="^(json|csv)$"),
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT * FROM bookmarks ORDER BY created_at DESC") as cur:
        rows = await cur.fetchall()

    data = []
    for row in rows:
        tags = await _attach_tags(db, row["id"])
        data.append({**dict(row), "tags": tags})

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["id", "url", "title", "description", "thumbnail", "type", "read", "tags", "created_at", "updated_at"],
        )
        writer.writeheader()
        for item in data:
            item["tags"] = ",".join(item["tags"])
            item["read"] = bool(item["read"])
            writer.writerow(item)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=readlater.csv"},
        )

    return StreamingResponse(
        iter([json.dumps(data, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=readlater.json"},
    )


@router.get("/{bookmark_id}", response_model=BookmarkOut)
async def get_bookmark(bookmark_id: int, db: aiosqlite.Connection = Depends(get_db)):
    return await _get_bookmark(db, bookmark_id)


@router.patch("/{bookmark_id}", response_model=BookmarkOut)
async def update_bookmark(
    bookmark_id: int,
    payload: BookmarkUpdate,
    db: aiosqlite.Connection = Depends(get_db),
):
    async with db.execute("SELECT id FROM bookmarks WHERE id = ?", (bookmark_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Not found")

    updates = {}
    if payload.title is not None:
        updates["title"] = payload.title
    if payload.description is not None:
        updates["description"] = payload.description
    if payload.read is not None:
        updates["read"] = 1 if payload.read else 0

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [bookmark_id]
        await db.execute(
            f"UPDATE bookmarks SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )

    if payload.tags is not None:
        await _ensure_tags(db, bookmark_id, payload.tags)

    await db.commit()
    return await _get_bookmark(db, bookmark_id)


@router.delete("/{bookmark_id}", status_code=204)
async def delete_bookmark(bookmark_id: int, db: aiosqlite.Connection = Depends(get_db)):
    async with db.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,)) as cur:
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not found")
    await db.commit()


async def _get_bookmark(db: aiosqlite.Connection, bookmark_id: int) -> BookmarkOut:
    async with db.execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    tags = await _attach_tags(db, bookmark_id)
    return _row_to_out(row, tags)


def _row_to_out(row, tags: List[str]) -> BookmarkOut:
    return BookmarkOut(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        description=row["description"],
        thumbnail=row["thumbnail"],
        type=row["type"],
        read=bool(row["read"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        tags=tags,
    )
