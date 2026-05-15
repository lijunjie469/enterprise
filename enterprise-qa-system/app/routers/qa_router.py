"""
Enterprise QA Router — HTTP API for the enterprise question-answering system.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, status, Query
from pydantic import BaseModel

from app.schemas.qa import QARequest, QAResponseData, ApiResponse
from app.services.db_service import get_db
from app.services.kb_service import get_kb
from app.services.qa_service import EnterpriseQAService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Enterprise QA"])

# Lazy init the QA service
_qa_service: Optional[EnterpriseQAService] = None


def _get_qa_service() -> EnterpriseQAService:
    global _qa_service
    if _qa_service is None:
        _qa_service = EnterpriseQAService(get_db(), get_kb())
    return _qa_service


@router.post(
    "/qa/query",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    summary="企业智能问答",
    description="输入自然语言问题，返回带来源标注的回答",
)
async def ask_question(request: QARequest):
    """POST query endpoint."""
    start = time.time()
    try:
        qa = _get_qa_service()
        result = qa.answer(request.question)
        elapsed = time.time() - start

        logger.info(f"Q: {request.question} | Intent: {qa.classify_intent(request.question)} | {elapsed:.2f}s")

        return ApiResponse(
            status=200,
            message="success",
            data=result.to_dict(),
        )
    except Exception as e:
        logger.error(f"QA query failed: {e}", exc_info=True)
        return ApiResponse(
            status=500,
            message=f"查询失败: {str(e)}",
            data=None,
        )


@router.get(
    "/qa/ask",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    summary="企业智能问答(GET)",
    description="GET方式的问答接口",
)
async def ask_get(
    q: str = Query(..., description="问题"),
    user_id: Optional[str] = Query(None, description="用户ID"),
):
    """GET query endpoint."""
    start = time.time()
    try:
        qa = _get_qa_service()
        result = qa.answer(q)
        elapsed = time.time() - start

        logger.info(f"Q: {q} | {elapsed:.2f}s")

        return ApiResponse(
            status=200,
            message="success",
            data=result.to_dict(),
        )
    except Exception as e:
        logger.error(f"QA query failed: {e}", exc_info=True)
        return ApiResponse(
            status=500,
            message=f"查询失败: {str(e)}",
            data=None,
        )


@router.get(
    "/qa/health",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    summary="健康检查",
)
async def health_check():
    """Health check endpoint."""
    try:
        db = get_db()
        kb = get_kb()
        emp_count = len(db.execute_query("SELECT COUNT(*) as cnt FROM employees"))
        kb_count = len(kb.documents)
        return ApiResponse(
            status=200,
            message="服务运行正常",
            data={
                "database": "connected",
                "employee_count": emp_count,
                "kb_sections": kb_count,
            },
        )
    except Exception as e:
        return ApiResponse(
            status=500,
            message=f"服务异常: {str(e)}",
            data=None,
        )


@router.get(
    "/qa/tables",
    response_model=ApiResponse,
    status_code=status.HTTP_200_OK,
    summary="获取数据库表信息",
)
async def get_table_info():
    """Return database schema info."""
    try:
        db = get_db()
        info = db.get_table_info()
        return ApiResponse(status=200, message="success", data=info)
    except Exception as e:
        return ApiResponse(
            status=500,
            message=f"获取表信息失败: {str(e)}",
            data=None,
        )
