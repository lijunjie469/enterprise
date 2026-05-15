"""
Enterprise QA System — FastAPI Application
智能企业问答系统主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import uvicorn
import os

from app.routers.qa_router import router as qa_router

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
for handler in logger.handlers[:]:
    logger.removeHandler(handler)
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

app = FastAPI(
    title="Enterprise QA System",
    description="企业智能问答助手 — 支持结构化数据查询和知识库检索",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(qa_router, prefix="/api/v1")

# Serve frontend static files
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_frontend():
        from fastapi.responses import FileResponse
        return FileResponse(os.path.join(frontend_path, "index.html"))


@app.get("/health")
async def root():
    return {"status": "ok", "service": "Enterprise QA System", "version": "1.0.0"}


if __name__ == "__main__":
    from app.core.config import settings
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=1,
        reload=True,
    )
