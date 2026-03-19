"""Pydantic 數據模型"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):
    """聊天請求"""
    message: str = Field(..., description="用戶消息（前端應在點擊商品後自動拼接商品信息）")
    user_id: str = Field(..., description="用戶 ID")
    session_id: Optional[str] = Field(None, description="會話 ID（可選，不提供則自動生成）")
    current_product_context: Optional[str] = Field(None, description="已廢棄，保留用於向後兼容。請在 message 中直接拼接商品信息")


class ChatResponse(BaseModel):
    """聊天響應"""
    message: str = Field(..., description="AI 響應")
    session_id: str = Field(..., description="會話 ID")
    user_id: str = Field(..., description="用戶 ID")
    current_product_context: Optional[str] = Field(None, description="已廢棄，保留用於向後兼容")


class HistoryResponse(BaseModel):
    """歷史記錄響應"""
    session_id: str
    messages: List[dict]
    user_id: str


class UserPreferences(BaseModel):
    """用戶偏好"""
    favorite_brands: Optional[List[str]] = None
    favorite_categories: Optional[List[str]] = None
    price_range: Optional[dict] = None
