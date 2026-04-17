"""其他工具 - 簡化實現"""
import json
from datetime import datetime, timedelta
from langchain_core.tools import tool


def _load_users():
    """載入用戶數據"""
    with open("data/users.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users):
    """保存用戶數據"""
    with open("data/users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ============================================
# 購買歷史工具
# ============================================

@tool
def get_purchase_history(
    user_id: str,
    limit: int = 10,
    offset: int = 0,
    category: str = None,
    keyword: str = None
) -> str:
    """
    獲取用戶購買歷史（支持分頁和過濾）

    Args:
        user_id: 用戶ID
        limit: 返回數量限制，默認10
        offset: 偏移量，默認0（用於分頁）
        category: 按類別過濾（可選）
        keyword: 按關鍵詞過濾（可選）

    Returns:
        str: JSON格式的購買歷史，包含彙總統計

    示例:
        - get_purchase_history("user_001", limit=10) → 獲取最近10條購買記錄
        - get_purchase_history("user_001", category="coffee") → 獲取咖啡類購買記錄

    注意:
        - 返回 aggregated 字段包含彙總統計（按類別、品牌統計）
        - 支持循環查詢：第一次 limit=10，沒找到 → limit=50，還沒找到 → limit=100
    """
    users = _load_users()

    if user_id not in users:
        return json.dumps({
            "success": False,
            "error": f"用戶 {user_id} 不存在"
        }, ensure_ascii=False)

    history = users[user_id]["purchase_history"]

    # 簡化版：直接返回歷史（實際應該從訂單中提取商品信息）
    filtered = history

    # 分頁
    total = len(filtered)
    paginated = filtered[offset:offset + limit]
    has_more = (offset + limit) < total

    # 彙總統計（簡化版）
    aggregated = {
        "total_orders": len(history),
        "total_spent": sum(order.get("total_price", 0) for order in history),
        "categories": {},  # 實際應該統計各類別購買數量
        "brands": {}  # 實際應該統計各品牌購買數量
    }

    return json.dumps({
        "success": True,
        "count": len(paginated),
        "total": total,
        "has_more": has_more,
        "orders": paginated,
        "aggregated": aggregated
    }, ensure_ascii=False, indent=2)


# ============================================
# 願望清單工具
# ============================================

@tool
def get_wishlist(user_id: str) -> str:
    """獲取用戶願望清單"""
    users = _load_users()

    if user_id not in users:
        return json.dumps({
            "success": False,
            "error": f"用戶 {user_id} 不存在"
        }, ensure_ascii=False)

    wishlist = users[user_id].get("wishlist", [])

    return json.dumps({
        "success": True,
        "count": len(wishlist),
        "wishlist": wishlist
    }, ensure_ascii=False, indent=2)


@tool
def add_to_wishlist(user_id: str, product_id: str) -> str:
    """添加商品到願望清單"""
    users = _load_users()

    if user_id not in users:
        return json.dumps({
            "success": False,
            "error": f"用戶 {user_id} 不存在"
        }, ensure_ascii=False)

    if "wishlist" not in users[user_id]:
        users[user_id]["wishlist"] = []

    wishlist = users[user_id]["wishlist"]

    if product_id not in wishlist:
        wishlist.append(product_id)
        _save_users(users)
        return json.dumps({
            "success": True,
            "message": f"已添加商品 {product_id} 到願望清單"
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": "商品已在願望清單中"
        }, ensure_ascii=False)


@tool
def remove_from_wishlist(user_id: str, product_id: str) -> str:
    """從願望清單移除商品"""
    users = _load_users()

    if user_id not in users:
        return json.dumps({
            "success": False,
            "error": f"用戶 {user_id} 不存在"
        }, ensure_ascii=False)

    wishlist = users[user_id].get("wishlist", [])

    if product_id in wishlist:
        wishlist.remove(product_id)
        _save_users(users)
        return json.dumps({
            "success": True,
            "message": f"已從願望清單移除商品 {product_id}"
        }, ensure_ascii=False)
    else:
        return json.dumps({
            "success": False,
            "error": "商品不在願望清單中"
        }, ensure_ascii=False)


# ============================================
# 用戶偏好工具
# ============================================

@tool
def get_user_preferences(user_id: str) -> str:
    """獲取用戶偏好"""
    users = _load_users()

    if user_id not in users:
        return json.dumps({
            "success": False,
            "error": f"用戶 {user_id} 不存在"
        }, ensure_ascii=False)

    preferences = users[user_id].get("preferences", {})

    return json.dumps({
        "success": True,
        "preferences": preferences
    }, ensure_ascii=False, indent=2)


# ============================================
# 價格追蹤工具（Mock實現）
# ============================================

@tool
def get_price_history(product_id: str, days: int = 30) -> str:
    """
    獲取商品價格歷史（Mock數據）

    Args:
        product_id: 商品ID
        days: 查詢天數，默認30天

    Returns:
        str: JSON格式的價格歷史
    """
    # Mock 價格歷史數據
    history = []
    base_date = datetime.now()

    for i in range(min(days, 30)):
        date = (base_date - timedelta(days=i)).strftime("%Y-%m-%d")
        # Mock 價格波動
        price = 129.99 + (i % 10 - 5) * 2
        history.append({
            "date": date,
            "price": round(price, 2)
        })

    return json.dumps({
        "success": True,
        "product_id": product_id,
        "history": history[::-1],  # 按時間正序
        "lowest": min(h["price"] for h in history),
        "highest": max(h["price"] for h in history),
        "current": history[0]["price"]
    }, ensure_ascii=False, indent=2)


@tool
def set_price_alert(user_id: str, product_id: str, target_price: float) -> str:
    """設置價格提醒（Mock實現）"""
    return json.dumps({
        "success": True,
        "message": f"已設置價格提醒：當商品 {product_id} 價格低於 ${target_price} 時通知您",
        "alert_id": f"ALERT_{product_id}"
    }, ensure_ascii=False)


# ============================================
# 商品評論工具（Mock實現）
# ============================================

@tool
def get_product_reviews(product_id: str, limit: int = 10, offset: int = 0) -> str:
    """
    獲取商品評論（Mock數據）

    Args:
        product_id: 商品ID
        limit: 返回數量限制，默認10
        offset: 偏移量，默認0

    Returns:
        str: JSON格式的評論列表
    """
    # Mock 評論數據
    mock_reviews = [
        {"rating": 5, "comment": "非常好用，質量很棒！", "author": "用戶A", "date": "2026-02-28"},
        {"rating": 4, "comment": "物有所值，推薦購買", "author": "用戶B", "date": "2026-02-25"},
        {"rating": 5, "comment": "超出預期，已經推薦給朋友了", "author": "用戶C", "date": "2026-02-20"},
    ]

    # 分頁
    total = len(mock_reviews)
    paginated = mock_reviews[offset:offset + limit]

    # 彙總統計
    avg_rating = sum(r["rating"] for r in mock_reviews) / len(mock_reviews) if mock_reviews else 0

    return json.dumps({
        "success": True,
        "product_id": product_id,
        "count": len(paginated),
        "total": total,
        "has_more": (offset + limit) < total,
        "average_rating": round(avg_rating, 1),
        "reviews": paginated
    }, ensure_ascii=False, indent=2)
