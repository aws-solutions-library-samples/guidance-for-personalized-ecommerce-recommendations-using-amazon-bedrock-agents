"""ShopBot 工具集合"""
from app.tools.shopping_tools import (
    search_products,
    get_product_details,
    get_products_batch,
)
from app.tools.cart_tools import (
    add_to_cart,
    get_cart,
    remove_from_cart,
    checkout,
)
from app.tools.other_tools import (
    get_purchase_history,
    get_wishlist,
    add_to_wishlist,
    remove_from_wishlist,
    get_user_preferences,
    get_price_history,
    set_price_alert,
    get_product_reviews,
)
from app.tools.context_tools import (
    archive_previous_conversation,
)


# 所有 ShopBot 工具列表
ALL_SHOPBOT_TOOLS = [
    # 商品相关 (3个)
    search_products,
    get_product_details,
    get_products_batch,

    # 购物车 (4个)
    add_to_cart,
    get_cart,
    remove_from_cart,
    checkout,

    # 购买历史 (1个)
    get_purchase_history,

    # 愿望清单 (3个)
    get_wishlist,
    add_to_wishlist,
    remove_from_wishlist,

    # 用户偏好 (2个)
    get_user_preferences,

    # 价格追踪 (2个)
    get_price_history,
    set_price_alert,

    # 评论 (1个)
    get_product_reviews,

    # Context 管理 (1个)
    archive_previous_conversation,
]

__all__ = [
    "ALL_SHOPBOT_TOOLS",
    "search_products",
    "get_product_details",
    "get_products_batch",
    "add_to_cart",
    "get_cart",
    "remove_from_cart",
    "checkout",
    "get_purchase_history",
    "get_wishlist",
    "add_to_wishlist",
    "remove_from_wishlist",
    "get_user_preferences",
    "get_price_history",
    "set_price_alert",
    "get_product_reviews",
    "archive_previous_conversation",
]
