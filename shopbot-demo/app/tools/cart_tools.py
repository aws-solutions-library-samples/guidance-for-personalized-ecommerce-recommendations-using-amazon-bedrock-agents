"""購物車相關工具 - 4個工具"""
import json
from typing import Optional
from langchain_core.tools import tool


def _load_users():
    """載入用戶數據"""
    with open("data/users.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users):
    """保存用戶數據"""
    with open("data/users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def _load_products():
    """載入商品數據（使用 products_display.json，與前端一致）"""
    with open("data/products_display.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        return data["products"]  # 返回 products 數組


@tool
def add_to_cart(user_id: str, product_id: str, quantity: int = 1) -> str:
    """
    添加商品到購物車

    Args:
        user_id: 用戶ID
        product_id: 商品ID
        quantity: 數量，默認1

    Returns:
        str: JSON格式的操作結果

    示例:
        - add_to_cart("user_001", "P001", 2) → 添加2個商品P001到購物車
    """
    users = _load_users()

    if user_id not in users:
        return json.dumps({
            "success": False,
            "error": f"用戶 {user_id} 不存在"
        }, ensure_ascii=False)

    # 檢查商品是否存在
    products = _load_products()
    product = next((p for p in products if p["id"] == product_id), None)
    if not product:
        return json.dumps({
            "success": False,
            "error": f"商品 {product_id} 不存在"
        }, ensure_ascii=False)

    # 檢查商品是否已在購物車中
    cart = users[user_id]["cart"]
    existing_item = next((item for item in cart if item["product_id"] == product_id), None)

    if existing_item:
        # 更新數量
        existing_item["quantity"] += quantity
    else:
        # 添加新商品
        cart.append({
            "product_id": product_id,
            "quantity": quantity,
            "added_at": "2026-03-02T10:00:00Z"  # Mock timestamp
        })

    _save_users(users)

    return json.dumps({
        "success": True,
        "message": f"已添加 {quantity} 個 {product.get('title', product.get('name', '商品'))} 到購物車",
        "cart_count": len(cart)
    }, ensure_ascii=False, indent=2)


@tool
def get_cart(user_id: str) -> str:
    """
    獲取用戶的購物車內容

    Args:
        user_id: 用戶ID

    Returns:
        str: JSON格式的購物車內容，包含商品詳情和總價

    示例:
        - get_cart("user_001") → 獲取用戶購物車
    """
    users = _load_users()

    if user_id not in users:
        return json.dumps({
            "success": False,
            "error": f"用戶 {user_id} 不存在"
        }, ensure_ascii=False)

    cart = users[user_id]["cart"]

    if not cart:
        return json.dumps({
            "success": True,
            "cart": [],
            "total_items": 0,
            "total_price": 0
        }, ensure_ascii=False)

    # 獲取商品詳情
    products = _load_products()
    cart_items = []
    total_price = 0

    for item in cart:
        product = next((p for p in products if p["id"] == item["product_id"]), None)
        if product:
            item_total = product["price"] * item["quantity"]
            cart_items.append({
                "product_id": product["id"],
                "name": product.get('title', product.get('name', '商品')),
                "price": product["price"],
                "quantity": item["quantity"],
                "subtotal": item_total
            })
            total_price += item_total

    return json.dumps({
        "success": True,
        "cart": cart_items,
        "total_items": len(cart_items),
        "total_price": round(total_price, 2)
    }, ensure_ascii=False, indent=2)


@tool
def remove_from_cart(user_id: str, product_id: str) -> str:
    """
    從購物車中移除商品

    Args:
        user_id: 用戶ID
        product_id: 商品ID

    Returns:
        str: JSON格式的操作結果
    """
    users = _load_users()

    if user_id not in users:
        return json.dumps({
            "success": False,
            "error": f"用戶 {user_id} 不存在"
        }, ensure_ascii=False)

    cart = users[user_id]["cart"]
    original_len = len(cart)

    # 移除商品
    users[user_id]["cart"] = [item for item in cart if item["product_id"] != product_id]

    if len(users[user_id]["cart"]) == original_len:
        return json.dumps({
            "success": False,
            "error": f"商品 {product_id} 不在購物車中"
        }, ensure_ascii=False)

    _save_users(users)

    return json.dumps({
        "success": True,
        "message": f"已從購物車移除商品 {product_id}",
        "cart_count": len(users[user_id]["cart"])
    }, ensure_ascii=False, indent=2)


@tool
def checkout(user_id: str) -> str:
    """
    結賬（清空購物車並添加到購買歷史）

    Args:
        user_id: 用戶ID

    Returns:
        str: JSON格式的訂單信息

    示例:
        - checkout("user_001") → 結賬並生成訂單
    """
    users = _load_users()

    if user_id not in users:
        return json.dumps({
            "success": False,
            "error": f"用戶 {user_id} 不存在"
        }, ensure_ascii=False)

    cart = users[user_id]["cart"]

    if not cart:
        return json.dumps({
            "success": False,
            "error": "購物車為空"
        }, ensure_ascii=False)

    # 計算總價
    products = _load_products()
    total_price = 0
    order_items = []

    for item in cart:
        product = next((p for p in products if p["id"] == item["product_id"]), None)
        if product:
            item_total = product["price"] * item["quantity"]
            order_items.append({
                "product_id": product["id"],
                "name": product.get('title', product.get('name', '商品')),
                "price": product["price"],
                "quantity": item["quantity"],
                "subtotal": item_total
            })
            total_price += item_total

    # 生成訂單
    order_id = f"ORDER_{len(users[user_id]['purchase_history']) + 1:04d}"
    order = {
        "order_id": order_id,
        "items": order_items,
        "total_price": round(total_price, 2),
        "order_date": "2026-03-02T10:00:00Z",  # Mock timestamp
        "status": "completed"
    }

    # 添加到購買歷史
    users[user_id]["purchase_history"].append(order)

    # 清空購物車
    users[user_id]["cart"] = []

    _save_users(users)

    return json.dumps({
        "success": True,
        "message": "訂單已生成",
        "order": order
    }, ensure_ascii=False, indent=2)
