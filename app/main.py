from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.routes.bookmarks import router as bookmarks_router
from app.routes.tags import router as tags_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="ReadLater", version="1.0.0", lifespan=lifespan)

app.include_router(bookmarks_router)
app.include_router(tags_router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def serve_ui():
    return FileResponse("static/index.html")
