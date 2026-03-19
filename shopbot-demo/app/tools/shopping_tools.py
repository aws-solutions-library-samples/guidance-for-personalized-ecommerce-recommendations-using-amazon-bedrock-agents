"""商品相關工具 - 3個核心工具"""
import json
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool


def _load_products():
    """載入商品數據（使用 products_display.json，與前端一致）"""
    with open("data/products_display.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        return data["products"]  # 返回 products 數組


@tool
def search_products(
    query: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    搜索商品

    Args:
        query: 搜索關鍵詞（可選，模糊匹配商品名稱、品牌）
        category: 商品類別（可選，如 "bags", "shoes", "electronics"）
        color: 顏色（可選）
        price_range: 價格範圍（可選，如 {"min": 100, "max": 200}）
        limit: 返回結果數量限制，默認10

    Returns:
        str: JSON格式的商品列表

    示例:
        - search_products(query="粉色背包") → 搜索粉色背包
        - search_products(category="electronics", price_range={"min": 200, "max": 400})
    """
    products = _load_products()
    results = []

    for product in products:
        # 關鍵詞匹配（支持 title, category, description）
        if query:
            query_lower = query.lower()
            title = product.get("title", product.get("name", "")).lower()
            category = product.get("category", "").lower()
            description = product.get("description", "").lower()

            if query_lower not in title and query_lower not in category and query_lower not in description:
                continue

        results.append(product)

    # 限制返回數量
    results = results[:limit]

    return json.dumps({
        "success": True,
        "count": len(results),
        "products": results
    }, ensure_ascii=False, indent=2)


@tool
def get_product_details(product_id: str) -> str:
    """
    獲取單個商品的詳細信息

    Args:
        product_id: 商品ID（如 "P001"）

    Returns:
        str: JSON格式的商品詳情

    示例:
        - get_product_details("P001") → 獲取 P001 的詳細信息
    """
    products = _load_products()

    for product in products:
        if product["id"] == product_id:
            return json.dumps({
                "success": True,
                "product": product
            }, ensure_ascii=False, indent=2)

    return json.dumps({
        "success": False,
        "error": f"商品 {product_id} 不存在"
    }, ensure_ascii=False)


@tool
def get_products_batch(product_ids: list[str]) -> str:
    """
    批量獲取多個商品的詳細信息（推薦用於商品對比）

    Args:
        product_ids: 商品ID列表（如 ["P001", "P002", "P003"]）

    Returns:
        str: JSON格式的商品列表

    示例:
        - get_products_batch(["P001", "P002"]) → 批量獲取兩個商品信息用於對比

    注意:
        - 這個工具比逐個調用 get_product_details 更高效
        - 適合用於商品對比場景
        - Agent 拿到數據後自己分析和對比
    """
    products = _load_products()
    results = []
    not_found = []

    for product_id in product_ids:
        found = False
        for product in products:
            if product["id"] == product_id:
                results.append(product)
                found = True
                break
        if not found:
            not_found.append(product_id)

    return json.dumps({
        "success": True,
        "count": len(results),
        "products": results,
        "not_found": not_found if not_found else None
    }, ensure_ascii=False, indent=2)
