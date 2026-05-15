from typing import Optional, Any, List
from pydantic import BaseModel, Field


class QARequest(BaseModel):
    question: str = Field(..., description="用户自然语言问题", min_length=1)
    user_id: Optional[str] = Field(None, description="用户ID")


class SourceInfo(BaseModel):
    type: str = Field(..., description="数据源类型: database / knowledge_base")
    detail: str = Field(..., description="来源详情")
    content: str = Field("", description="来源内容摘要")


class QAResponseData(BaseModel):
    answer: str = Field(..., description="回答内容")
    sources: List[SourceInfo] = Field(default_factory=list, description="信息来源")
    data: Optional[Any] = Field(None, description="原始查询结果")


class ApiResponse(BaseModel):
    status: int = Field(200, description="状态码")
    message: str = Field("success", description="响应信息")
    data: Optional[Any] = Field(None, description="响应数据")

    model_config = {
        "from_attributes": True,
        "arbitrary_types_allowed": True,
    }
