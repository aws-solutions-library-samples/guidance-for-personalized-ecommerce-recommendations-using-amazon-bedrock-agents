/**
 * ShopBot 前端應用
 * 功能：商品展示、聊天交互、推薦問題生成
 */

// ============================================
// 全局狀態
// ============================================

const APP_STATE = {
    userId: null,
    sessionId: null,
    products: [],
    pendingProductClick: null,  // 暂存用户点击的商品 {id, title, timestamp}
    apiBaseUrl: `${window.location.protocol}//${window.location.hostname}:8000`  // 動態獲取 FastAPI 後端地址
};

// ============================================
// 工具函數
// ============================================

/**
 * 生成唯一 ID
 */
function generateId() {
    return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * 格式化價格
 */
function formatPrice(price) {
    return `¥${price.toFixed(2)}`;
}

/**
 * 獲取標籤樣式
 */
function getTagClass(tag) {
    const tagMap = {
        '熱銷': 'tag-hot',
        '新品': 'tag-new',
        '推薦': 'tag-recommend',
        '高端': 'bg-gradient-to-r from-yellow-400 to-orange-500',
        '收藏': 'bg-gradient-to-r from-indigo-500 to-purple-500',
        '辦公': 'bg-gradient-to-r from-blue-400 to-cyan-500'
    };
    return tagMap[tag] || 'bg-gray-500';
}

/**
 * 滾動到聊天底部
 */
function scrollToBottom() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ============================================
// API 調用
// ============================================

/**
 * 載入商品列表
 */
async function loadProducts() {
    try {
        const response = await fetch(`${APP_STATE.apiBaseUrl}/api/products`);
        const data = await response.json();
        APP_STATE.products = data.products;
        renderProducts(data.products);
    } catch (error) {
        console.error('載入商品失敗:', error);
        showError('無法載入商品列表');
    }
}

/**
 * 獲取商品推薦問題
 */
async function getSuggestedQuestions(productId) {
    try {
        const response = await fetch(`${APP_STATE.apiBaseUrl}/api/suggested-questions/${productId}`);
        const data = await response.json();
        return data.questions;
    } catch (error) {
        console.error('獲取推薦問題失敗:', error);
        return [];
    }
}

/**
 * 發送消息到 ShopBot（使用 stream API）
 */
async function sendMessage(message) {
    try {
        const response = await fetch(`${APP_STATE.apiBaseUrl}/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: APP_STATE.userId,
                session_id: APP_STATE.sessionId,
                message: message
                // 不再需要 current_product_context 字段
            })
        });

        if (!response.ok) {
            throw new Error('發送消息失敗');
        }

        return response.body;
    } catch (error) {
        console.error('發送消息失敗:', error);
        throw error;
    }
}

/**
 * 處理流式響應
 */
async function handleStreamResponse(stream) {
    const reader = stream.getReader();
    const decoder = new TextDecoder();

    let botMessageDiv = null;
    let botMessageText = '';

    console.log('開始處理流式響應...');

    while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = line.slice(6);

                if (data === '[DONE]') {
                    continue;
                }

                try {
                    const parsed = JSON.parse(data);

                    // 處理不同類型的消息
                    if (parsed.type === 'content' || parsed.type === 'token') {
                        // 提取實際文本內容
                        let textContent = '';

                        // 處理不同格式的 content
                        if (typeof parsed.content === 'string') {
                            // 簡單字符串
                            textContent = parsed.content;
                        } else if (Array.isArray(parsed.content)) {
                            // 數組格式 [{"type": "text", "text": "...", "index": 0}]
                            textContent = parsed.content
                                .filter(item => item.type === 'text')
                                .map(item => item.text)
                                .join('');
                        } else if (parsed.content && parsed.content.text) {
                            // 對象格式 {"type": "text", "text": "..."}
                            textContent = parsed.content.text;
                        }

                        // 追加 token/content
                        botMessageText += textContent;

                        // 如果還沒有創建消息框，創建一個
                        if (!botMessageDiv) {
                            botMessageDiv = addBotMessage('');
                        }

                        // 更新消息內容
                        const textElement = botMessageDiv.querySelector('.message-text');
                        textElement.textContent = botMessageText;
                        scrollToBottom();
                    }
                    else if (parsed.type === 'tool_start') {
                        // 顯示工具調用開始
                        console.log('工具調用開始:', parsed.tool);
                    }
                    else if (parsed.type === 'tool_end') {
                        // 顯示工具調用結束
                        console.log('工具調用結束:', parsed.tool);
                    }
                    else if (parsed.type === 'done') {
                        // 流結束
                        console.log('流式響應完成');
                    }
                    else if (parsed.type === 'error') {
                        showError(parsed.error || parsed.content || '未知錯誤');
                    }
                } catch (e) {
                    console.error('解析響應失敗:', e, 'Raw data:', data);
                }
            }
        }
    }

    // 如果沒有收到任何內容，顯示錯誤
    if (!botMessageText) {
        console.error('未收到任何響應內容');
        showError('ShopBot 沒有返回任何響應，請檢查後端服務');
    }

    return botMessageText;
}

// ============================================
// UI 渲染
// ============================================

/**
 * 渲染商品列表
 */
function renderProducts(products) {
    const grid = document.getElementById('productsGrid');
    grid.innerHTML = '';

    products.forEach(product => {
        const card = createProductCard(product);
        grid.appendChild(card);
    });
}

/**
 * 創建商品卡片
 */
function createProductCard(product) {
    const card = document.createElement('div');
    card.className = 'product-card bg-white rounded-2xl overflow-hidden shadow-sm hover:shadow-xl';
    card.dataset.productId = product.id;

    // 計算折扣
    const discount = Math.round((1 - product.price / product.original_price) * 100);

    card.innerHTML = `
        <!-- 商品图片 -->
        <div class="relative h-56 overflow-hidden bg-gray-100">
            <img
                src="images/${product.image_placeholder}"
                alt="${product.title}"
                class="w-full h-full object-cover"
                onerror="this.onerror=null; this.parentElement.innerHTML='<div class=\\'image-placeholder h-56 flex items-center justify-center\\'><span class=\\'text-6xl opacity-20\\'>${product.title.charAt(0)}</span></div>';"
            />
            ${product.tags.map(tag => `
                <span class="${getTagClass(tag)} text-white text-xs px-2 py-1 rounded-lg absolute top-3 left-3 font-medium shadow-lg">
                    ${tag}
                </span>
            `).join('')}
            ${discount > 0 ? `
                <span class="bg-red-500 text-white text-xs px-2 py-1 rounded-lg absolute top-3 right-3 font-bold shadow-lg">
                    -${discount}%
                </span>
            ` : ''}
        </div>

        <!-- 商品信息 -->
        <div class="p-5">
            <div class="text-xs text-gray-500 mb-1">${product.category}</div>
            <h3 class="text-base font-bold text-gray-800 mb-2 line-clamp-2">${product.title}</h3>
            <p class="text-sm text-gray-600 mb-3 line-clamp-2">${product.description}</p>

            <!-- 特性标签 -->
            <div class="flex flex-wrap gap-1 mb-3">
                ${product.features.slice(0, 3).map(feature => `
                    <span class="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">${feature}</span>
                `).join('')}
            </div>

            <!-- 价格和评分 -->
            <div class="flex items-end justify-between mb-3">
                <div>
                    <div class="text-2xl font-bold text-red-500">${formatPrice(product.price)}</div>
                    ${product.original_price > product.price ? `
                        <div class="text-xs text-gray-400 line-through">${formatPrice(product.original_price)}</div>
                    ` : ''}
                </div>
                <div class="text-right">
                    <div class="text-sm text-yellow-500 font-bold">⭐ ${product.rating}</div>
                    <div class="text-xs text-gray-500">${product.reviews_count} 评价</div>
                </div>
            </div>

            <!-- 庫存 -->
            <div class="text-xs text-gray-500 mb-3">
                庫存: ${product.stock} 件
            </div>

            <!-- 按鈕 -->
            <button class="w-full py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg font-medium hover:from-purple-600 hover:to-pink-600 transition text-sm">
                點擊諮詢 ShopBot
            </button>
        </div>
    `;

    // 添加点击事件
    card.addEventListener('click', () => handleProductClick(product));

    return card;
}

/**
 * 處理商品點擊事件
 */
async function handleProductClick(product) {
    console.log('點擊商品:', product.id);

    // 暂存点击信息（不立即发送）
    APP_STATE.pendingProductClick = {
        id: product.id,
        title: product.title,
        timestamp: Date.now()
    };

    // 高亮選中的商品卡片
    document.querySelectorAll('.product-card').forEach(card => {
        card.classList.remove('ring-4', 'ring-purple-500');
    });
    document.querySelector(`[data-product-id="${product.id}"]`).classList.add('ring-4', 'ring-purple-500');

    // 在聊天界面显示点击信息（仅前端展示，不发送给后端）
    addUserMessage(`[查看商品] ${product.title}`);

    // 獲取推薦問題
    const questions = await getSuggestedQuestions(product.id);

    // 顯示推薦問題和 Bot 提示（仅前端展示，不触发 Agent）
    if (questions.length > 0) {
        displaySuggestedQuestions(questions);
        addBotMessage(`我看到您對「${product.title}」感興趣！以下是一些常見問題，點擊即可諮詢：`);
    } else {
        addBotMessage(`您好！我看到您對「${product.title}」感興趣。有什麼想了解的嗎？`);
    }
}

/**
 * 顯示推薦問題
 */
function displaySuggestedQuestions(questions) {
    const area = document.getElementById('suggestedQuestionsArea');
    const container = document.getElementById('suggestedQuestions');

    container.innerHTML = '';

    questions.forEach(question => {
        const chip = document.createElement('button');
        chip.className = 'question-chip text-xs bg-white border-2 border-purple-300 text-purple-700 px-3 py-2 rounded-full hover:bg-purple-50 font-medium';
        chip.textContent = question;

        chip.addEventListener('click', () => {
            handleQuestionClick(question);
        });

        container.appendChild(chip);
    });

    area.classList.remove('hidden');
}

/**
 * 處理推薦問題點擊
 */
function handleQuestionClick(question) {
    // 隱藏推薦問題區域
    document.getElementById('suggestedQuestionsArea').classList.add('hidden');

    // 發送問題
    handleSendMessage(question);
}

/**
 * 添加用戶消息
 */
function addUserMessage(text) {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-item flex items-start gap-3 justify-end';
    messageDiv.innerHTML = `
        <div class="bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-2xl rounded-tr-none px-4 py-3 max-w-[80%]">
            <p class="text-sm">${text}</p>
        </div>
        <div class="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center flex-shrink-0">
            <span class="text-sm">👤</span>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

/**
 * 添加 Bot 消息
 */
function addBotMessage(text) {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-item flex items-start gap-3';
    messageDiv.innerHTML = `
        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center flex-shrink-0">
            <span class="text-white text-sm">🤖</span>
        </div>
        <div class="bg-gray-100 rounded-2xl rounded-tl-none px-4 py-3 max-w-[80%]">
            <p class="text-sm text-gray-800 message-text">${text}</p>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

/**
 * 添加載入消息
 */
function addLoadingMessage() {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-item flex items-start gap-3 loading-message';
    messageDiv.innerHTML = `
        <div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center flex-shrink-0">
            <span class="text-white text-sm">🤖</span>
        </div>
        <div class="bg-gray-100 rounded-2xl rounded-tl-none px-4 py-3">
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv;
}

/**
 * 移除載入消息
 */
function removeLoadingMessage() {
    const loadingMessage = document.querySelector('.loading-message');
    if (loadingMessage) {
        loadingMessage.remove();
    }
}

/**
 * 顯示錯誤消息
 */
function showError(message) {
    const errorText = message || '發生未知錯誤';
    console.error('ShopBot 錯誤:', errorText);
    addBotMessage(`❌ ${errorText}`);
}

// ============================================
// 事件處理
// ============================================

/**
 * 處理發送消息
 */
async function handleSendMessage(messageText = null) {
    const input = document.getElementById('messageInput');
    let message = messageText || input.value.trim();

    if (!message) return;

    // 清空輸入框
    if (!messageText) {
        input.value = '';
    }

    // 如果有待发送的商品点击信息，自动拼接
    let finalMessage = message;
    if (APP_STATE.pendingProductClick) {
        finalMessage = `查看商品：${APP_STATE.pendingProductClick.title}（${APP_STATE.pendingProductClick.id}）\n\n${message}`;

        // 用完即清空
        APP_STATE.pendingProductClick = null;
    }

    // 添加用戶消息（显示原始消息）
    addUserMessage(message);

    // 添加載入消息
    const loadingMsg = addLoadingMessage();

    try {
        // 發送拼接后的消息
        const stream = await sendMessage(finalMessage);

        // 移除載入消息
        removeLoadingMessage();

        // 處理流式響應
        await handleStreamResponse(stream);

    } catch (error) {
        removeLoadingMessage();
        showError('發送消息失敗，請稍後重試');
    }
}

/**
 * 清空聊天記錄
 */
function clearChat() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = `
        <div class="message-item flex items-start gap-3">
            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center flex-shrink-0">
                <span class="text-white text-sm">🤖</span>
            </div>
            <div class="bg-gray-100 rounded-2xl rounded-tl-none px-4 py-3 max-w-[80%]">
                <p class="text-sm text-gray-800">您好！我是 ShopBot 智能購物助手。點擊右側商品，我會為您生成相關問題，幫助您更好地了解商品。</p>
            </div>
        </div>
    `;

    // 隱藏推薦問題
    document.getElementById('suggestedQuestionsArea').classList.add('hidden');

    // 清空待发送的商品点击信息
    APP_STATE.pendingProductClick = null;

    // 重新生成 session ID
    APP_STATE.sessionId = generateId();
}

// ============================================
// 初始化
// ============================================

/**
 * 初始化應用
 */
async function initApp() {
    console.log('ShopBot 應用啟動...');

    // 生成用戶 ID 和會話 ID
    APP_STATE.userId = 'user_001';  // 固定為 user_001 用於 demo
    APP_STATE.sessionId = generateId();

    // 顯示用戶 ID
    document.getElementById('userId').textContent = APP_STATE.userId;

    // 載入商品
    await loadProducts();

    // 綁定事件
    document.getElementById('sendButton').addEventListener('click', () => handleSendMessage());
    document.getElementById('messageInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSendMessage();
        }
    });
    document.getElementById('clearChat').addEventListener('click', clearChat);

    console.log('ShopBot 應用初始化完成');
}

// 頁面載入完成後初始化
document.addEventListener('DOMContentLoaded', initApp);
