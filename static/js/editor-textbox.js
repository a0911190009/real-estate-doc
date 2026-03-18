/**
 * 不動產說明書編輯器 — 文字框模組
 * 功能：拖曳移動、縮放、雙擊編輯、刪除
 *
 * 設計原則：
 * - 事件只綁定一次到 textbox-layer（事件委派）
 * - 選取/取消選取只更新 CSS class，不重新渲染整個頁面
 * - 拖曳位置使用 % 儲存，與畫布縮放無關
 */

// ─── 拖曳狀態 ───
const _drag = {
    active: false,
    boxId: null,
    startMouseX: 0,
    startMouseY: 0,
    startBoxXPct: 0,
    startBoxYPct: 0,
};

// ─── 縮放狀態 ───
const _resize = {
    active: false,
    boxId: null,
    startMouseX: 0,
    startMouseY: 0,
    startWPct: 0,
    startHPct: 0,
};

// ─── 是否已綁定事件（防止重複） ───
let _eventsInitialized = false;

// ════════════════════════════════════════════════
// 初始化（只執行一次）
// ════════════════════════════════════════════════

function initTextboxEvents() {
    if (_eventsInitialized) return;
    _eventsInitialized = true;

    const layer = document.getElementById("textbox-layer");

    // ── 滑鼠按下（開始拖曳 or 縮放 or 選取） ──
    layer.addEventListener("mousedown", (e) => {
        const boxEl = e.target.closest(".textbox");

        // 點擊畫布空白區域：取消選取並退出編輯
        if (!boxEl) {
            _deselectAll();
            return;
        }

        const boxId = boxEl.dataset.boxId;

        // 縮放把手被按下
        if (e.target.classList.contains("resize-handle")) {
            e.preventDefault();
            e.stopPropagation();
            _startResize(boxId, e);
            return;
        }

        // 若目前框正在編輯中：退出編輯模式，選取框，但不啟動拖曳
        // （第一次點擊退出編輯，第二次點擊才能拖曳）
        const content = boxEl.querySelector(".textbox-content");
        if (content.contentEditable === "true") {
            _exitEdit();
            _selectBox(boxId);
            return;
        }

        e.preventDefault();
        _selectBox(boxId);
        _startDrag(boxId, e);
    });

    // ── 雙擊進入編輯模式 ──
    layer.addEventListener("dblclick", (e) => {
        const boxEl = e.target.closest(".textbox");
        if (!boxEl) return;
        e.preventDefault();
        _enterEdit(boxEl.dataset.boxId);
    });

    // ── 全局滑鼠移動 ──
    document.addEventListener("mousemove", _onMouseMove);

    // ── 全局滑鼠釋放 ──
    document.addEventListener("mouseup", _onMouseUp);

    // ── 鍵盤：ESC 離開編輯，Delete 刪除選取框 ──
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            _exitEdit();
        }
        if ((e.key === "Delete" || e.key === "Backspace") && editorState.selectedBoxId) {
            const active = document.querySelector(".textbox-content[contenteditable='true']");
            if (!active) {
                deleteTextbox(editorState.selectedBoxId);
            }
        }
    });

    // 注意：bg-image 被 textbox-layer 蓋住，無法直接偵測點擊
    // 點擊畫布空白的取消選取邏輯已移到 textbox-layer 的 mousedown 中（!boxEl 分支）
}

// ════════════════════════════════════════════════
// 選取 / 取消選取
// ════════════════════════════════════════════════

function _selectBox(boxId) {
    if (editorState.selectedBoxId === boxId) return;

    // 離開舊的編輯模式
    if (editorState.selectedBoxId) {
        _exitEdit();
    }

    // 移除舊的 selected 樣式
    document.querySelectorAll(".textbox.selected").forEach(el => {
        el.classList.remove("selected");
    });

    // 加上新的 selected 樣式
    const boxEl = document.querySelector(`[data-box-id="${boxId}"]`);
    if (boxEl) boxEl.classList.add("selected");

    editorState.selectedBoxId = boxId;
    updatePropsPanel();
}

function _deselectAll() {
    _exitEdit();
    document.querySelectorAll(".textbox.selected").forEach(el => {
        el.classList.remove("selected");
    });
    editorState.selectedBoxId = null;
    updatePropsPanel();
}

// ════════════════════════════════════════════════
// 拖曳移動
// ════════════════════════════════════════════════

function _startDrag(boxId, e) {
    const layer = document.getElementById("textbox-layer");
    const boxEl = document.querySelector(`[data-box-id="${boxId}"]`);
    const layerRect = layer.getBoundingClientRect();
    const boxRect = boxEl.getBoundingClientRect();

    _drag.active = true;
    _drag.boxId = boxId;
    _drag.startMouseX = e.clientX;
    _drag.startMouseY = e.clientY;
    // 記錄框框目前位置（% 值）
    _drag.startBoxXPct = (boxRect.left - layerRect.left) / layerRect.width;
    _drag.startBoxYPct = (boxRect.top - layerRect.top) / layerRect.height;
}

// ════════════════════════════════════════════════
// 縮放
// ════════════════════════════════════════════════

function _startResize(boxId, e) {
    const layer = document.getElementById("textbox-layer");
    const boxEl = document.querySelector(`[data-box-id="${boxId}"]`);
    const layerRect = layer.getBoundingClientRect();
    const boxRect = boxEl.getBoundingClientRect();

    _resize.active = true;
    _resize.boxId = boxId;
    _resize.startMouseX = e.clientX;
    _resize.startMouseY = e.clientY;
    _resize.startWPct = boxRect.width / layerRect.width;
    _resize.startHPct = boxRect.height / layerRect.height;

    // 同時也選取這個框
    _selectBox(boxId);
}

// ════════════════════════════════════════════════
// 滑鼠移動處理
// ════════════════════════════════════════════════

function _onMouseMove(e) {
    const layer = document.getElementById("textbox-layer");
    if (!layer) return;
    const layerRect = layer.getBoundingClientRect();

    // ── 拖曳中 ──
    if (_drag.active && _drag.boxId) {
        const deltaXPct = (e.clientX - _drag.startMouseX) / layerRect.width;
        const deltaYPct = (e.clientY - _drag.startMouseY) / layerRect.height;

        let newXPct = _drag.startBoxXPct + deltaXPct;
        let newYPct = _drag.startBoxYPct + deltaYPct;

        // 邊界限制（不允許拖到畫布外）
        newXPct = Math.max(0, Math.min(0.99, newXPct));
        newYPct = Math.max(0, Math.min(0.99, newYPct));

        const boxEl = document.querySelector(`[data-box-id="${_drag.boxId}"]`);
        if (boxEl) {
            boxEl.style.left = (newXPct * 100) + "%";
            boxEl.style.top = (newYPct * 100) + "%";
        }
    }

    // ── 縮放中 ──
    if (_resize.active && _resize.boxId) {
        const deltaXPct = (e.clientX - _resize.startMouseX) / layerRect.width;
        const deltaYPct = (e.clientY - _resize.startMouseY) / layerRect.height;

        let newWPct = Math.max(0.05, _resize.startWPct + deltaXPct);  // 最小寬 5%
        let newHPct = Math.max(0.02, _resize.startHPct + deltaYPct);  // 最小高 2%

        const boxEl = document.querySelector(`[data-box-id="${_resize.boxId}"]`);
        if (boxEl) {
            boxEl.style.width = (newWPct * 100) + "%";
            boxEl.style.height = (newHPct * 100) + "%";
        }
    }
}

// ════════════════════════════════════════════════
// 滑鼠釋放：儲存最終位置到 state
// ════════════════════════════════════════════════

function _onMouseUp(e) {
    const layer = document.getElementById("textbox-layer");
    if (!layer) return;
    const layerRect = layer.getBoundingClientRect();

    // 拖曳結束：更新 state
    if (_drag.active && _drag.boxId) {
        const boxEl = document.querySelector(`[data-box-id="${_drag.boxId}"]`);
        if (boxEl) {
            const boxRect = boxEl.getBoundingClientRect();
            const box = _findBox(_drag.boxId);
            if (box) {
                box.xPct = (boxRect.left - layerRect.left) / layerRect.width;
                box.yPct = (boxRect.top - layerRect.top) / layerRect.height;
            }
        }
        _drag.active = false;
        _drag.boxId = null;
    }

    // 縮放結束：更新 state
    if (_resize.active && _resize.boxId) {
        const boxEl = document.querySelector(`[data-box-id="${_resize.boxId}"]`);
        if (boxEl) {
            const boxRect = boxEl.getBoundingClientRect();
            const box = _findBox(_resize.boxId);
            if (box) {
                box.wPct = boxRect.width / layerRect.width;
                box.hPct = boxRect.height / layerRect.height;
            }
        }
        _resize.active = false;
        _resize.boxId = null;
    }
}

// ════════════════════════════════════════════════
// 編輯模式
// ════════════════════════════════════════════════

function _enterEdit(boxId) {
    _selectBox(boxId);

    const boxEl = document.querySelector(`[data-box-id="${boxId}"]`);
    if (!boxEl) return;
    const content = boxEl.querySelector(".textbox-content");
    if (!content) return;

    content.contentEditable = "true";
    content.focus();

    // 全選文字（方便直接覆蓋輸入）
    const range = document.createRange();
    range.selectNodeContents(content);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
}

function _exitEdit() {
    const editingEl = document.querySelector(".textbox-content[contenteditable='true']");
    if (!editingEl) return;

    // 儲存文字到 state
    const boxEl = editingEl.closest(".textbox");
    if (boxEl) {
        const box = _findBox(boxEl.dataset.boxId);
        if (box) {
            box.text = editingEl.textContent;
        }
    }

    editingEl.contentEditable = "false";
    editingEl.blur();
}

// ════════════════════════════════════════════════
// 公開 API
// ════════════════════════════════════════════════

/**
 * 刪除文字框
 */
function deleteTextbox(boxId) {
    _exitEdit();
    const page = editorState.pages[editorState.currentPageIndex];
    const idx = page.textboxes.findIndex(b => b.id === boxId);
    if (idx === -1) return;

    page.textboxes.splice(idx, 1);
    editorState.selectedBoxId = null;

    // 直接從 DOM 移除，不需要重新渲染整頁
    const boxEl = document.querySelector(`[data-box-id="${boxId}"]`);
    if (boxEl) boxEl.remove();

    updatePropsPanel();
}

/**
 * 更新文字框屬性（即時更新 DOM 和 state）
 */
function updateTextboxProperty(boxId, property, value) {
    const box = _findBox(boxId);
    if (!box) return;

    box[property] = value;

    const boxEl = document.querySelector(`[data-box-id="${boxId}"]`);
    if (!boxEl) return;
    const content = boxEl.querySelector(".textbox-content");

    switch (property) {
        case "fontFamily":
            if (content) content.style.fontFamily = value;
            break;
        case "fontSizePt":
            if (content) content.style.fontSize = value + "pt";
            break;
        case "color":
            if (content) content.style.color = value;
            break;
        case "text":
            if (content) content.textContent = value;
            break;
        case "fieldKey":
            boxEl.dataset.fieldKey = value;
            let tag = boxEl.querySelector(".field-tag");
            if (value) {
                if (!tag) {
                    tag = document.createElement("span");
                    tag.className = "field-tag";
                    boxEl.appendChild(tag);
                }
                tag.textContent = value;
                tag.style.display = "";
            } else {
                if (tag) tag.style.display = "none";
            }
            break;
    }
}

/**
 * 選取指定文字框（外部呼叫）
 */
function selectTextbox(boxId) {
    _selectBox(boxId);
}

// ════════════════════════════════════════════════
// 工具函式
// ════════════════════════════════════════════════

function _findBox(boxId) {
    const page = editorState.pages[editorState.currentPageIndex];
    return page ? page.textboxes.find(b => b.id === boxId) : null;
}

// ─── 覆蓋 getCurrentSelectedBox（editor-canvas.js 中定義） ───
window.getCurrentSelectedBox = function() {
    return _findBox(editorState.selectedBoxId);
};

// ─── 在 DOMContentLoaded 後初始化 ───
document.addEventListener("DOMContentLoaded", () => {
    setTimeout(initTextboxEvents, 50);
});
