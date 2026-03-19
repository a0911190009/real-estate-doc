/**
 * 不動產說明書編輯器 — 畫布模組
 * 功能：底圖上傳、頁面管理（新增/刪除/切換）、文字框渲染
 */

// ════════════════════════════════════════════════
// 全局狀態
// ════════════════════════════════════════════════
const editorState = {
    pages: [],                   // 所有頁面
    currentPageIndex: 0,         // 目前顯示的頁面索引
    selectedBoxId: null,         // 目前選取的文字框 ID
};

// DOM 快取
const DOM = {};

// ════════════════════════════════════════════════
// 初始化
// ════════════════════════════════════════════════

function initEditor() {
    // 快取 DOM
    DOM.bgImage     = document.getElementById("bg-image");
    DOM.canvasArea  = document.getElementById("canvas-area");
    DOM.textboxLayer = document.getElementById("textbox-layer");
    DOM.pageList    = document.getElementById("page-list");
    DOM.propsEmpty  = document.getElementById("props-empty");
    DOM.propsContent = document.getElementById("props-content");
    DOM.fileBg      = document.getElementById("file-bg");

    // 建立初始空白頁
    editorState.pages = [_newPage(0)];
    editorState.currentPageIndex = 0;

    _bindToolbar();
    updatePageThumbnails();
    renderCurrentPage();
}

// ════════════════════════════════════════════════
// 頁面物件工廠
// ════════════════════════════════════════════════

function _newPage(idx) {
    return {
        pageIndex: idx,
        bgDataUrl: "",   // base64 data URL（預覽用）
        bgServerUrl: "", // 上傳後取得的伺服器 URL
        textboxes: [],
    };
}

/** 取得目前頁面有效的底圖 URL（編輯期間優先用 base64，伺服器 URL 作備用） */
function _bgUrl(page) {
    return page.bgDataUrl || page.bgServerUrl || "";
}

// ════════════════════════════════════════════════
// 頁面操作
// ════════════════════════════════════════════════

function addPage() {
    const page = _newPage(editorState.pages.length);
    editorState.pages.push(page);
    editorState.currentPageIndex = editorState.pages.length - 1;
    editorState.selectedBoxId = null;
    updatePageThumbnails();
    renderCurrentPage();
    updatePropsPanel();
}

function deletePage(pageIndex) {
    if (editorState.pages.length <= 1) {
        alert("至少要保留一個頁面");
        return;
    }
    editorState.pages.splice(pageIndex, 1);
    editorState.pages.forEach((p, i) => { p.pageIndex = i; });
    if (editorState.currentPageIndex >= editorState.pages.length) {
        editorState.currentPageIndex = editorState.pages.length - 1;
    }
    editorState.selectedBoxId = null;
    updatePageThumbnails();
    renderCurrentPage();
    updatePropsPanel();
}

function switchToPage(pageIndex) {
    if (pageIndex === editorState.currentPageIndex) return;
    editorState.currentPageIndex = pageIndex;
    editorState.selectedBoxId = null;
    updatePageThumbnails();
    renderCurrentPage();
    updatePropsPanel();
}

// ════════════════════════════════════════════════
// 底圖上傳
// ════════════════════════════════════════════════

/**
 * 使用者選擇圖檔後呼叫
 * 第一步：用 FileReader 讀成 base64 立刻顯示
 * 第二步：非同步上傳到伺服器取得 URL（存入 bgServerUrl）
 */
function handleBgUpload(file) {
    if (!file) return;
    const page = editorState.pages[editorState.currentPageIndex];

    // 立刻用 base64 顯示
    const reader = new FileReader();
    reader.onload = (e) => {
        page.bgDataUrl = e.target.result;
        renderCurrentPage();
        updatePageThumbnails();

        // 非同步上傳到伺服器
        _uploadBgToServer(file, page);
    };
    reader.onerror = () => alert("讀取圖檔失敗");
    reader.readAsDataURL(file);
}

function _uploadBgToServer(file, page) {
    const formData = new FormData();
    formData.append("image", file);

    fetch("/api/editor/upload-bg", { method: "POST", body: formData })
        .then(r => r.json())
        .then(data => {
            if (data.ok) {
                page.bgServerUrl = data.url;
                // 不切換 DOM.bgImage.src，保留已顯示的 base64 預覽
                // bgServerUrl 只供模板儲存時使用，編輯期間繼續用 base64
            }
        })
        .catch(err => {
            // 上傳失敗不影響使用（仍保有 base64 預覽）
            console.warn("底圖上傳伺服器失敗（本地開發可忽略）:", err.message);
        });
}

// ════════════════════════════════════════════════
// 渲染
// ════════════════════════════════════════════════

/**
 * 渲染當前頁面（換頁或載入模板時呼叫）
 * 注意：選取/取消選取不需要呼叫這個函式，改用 CSS class 直接操作
 */
function renderCurrentPage() {
    const page = editorState.pages[editorState.currentPageIndex];
    const url = _bgUrl(page);

    if (url) {
        DOM.bgImage.src = url;
        DOM.bgImage.style.display = "block";
        // 清除無底圖時設的固定尺寸，讓畫布自適應圖片
        DOM.canvasArea.style.width = "";
        DOM.canvasArea.style.height = "";
    } else {
        DOM.bgImage.src = "";
        DOM.bgImage.style.display = "none";
        // 沒有底圖時給畫布一個預設大小（A4 比例）
        DOM.canvasArea.style.width  = "595px";
        DOM.canvasArea.style.height = "842px";
    }

    // 清空並重建文字框層
    DOM.textboxLayer.innerHTML = "";
    page.textboxes.forEach(box => _appendTextboxEl(box));

    // 恢復選取狀態
    if (editorState.selectedBoxId) {
        const el = document.querySelector(`[data-box-id="${editorState.selectedBoxId}"]`);
        if (el) el.classList.add("selected");
    }
}

/**
 * 建立單個文字框 DOM 並加入 textbox-layer
 */
function _appendTextboxEl(box) {
    const boxEl = document.createElement("div");
    boxEl.className = "textbox";
    boxEl.dataset.boxId  = box.id;
    boxEl.dataset.fieldKey = box.fieldKey || "";

    boxEl.style.left   = (box.xPct * 100) + "%";
    boxEl.style.top    = (box.yPct * 100) + "%";
    boxEl.style.width  = (box.wPct * 100) + "%";
    boxEl.style.height = (box.hPct * 100) + "%";

    // 文字內容區
    const content = document.createElement("div");
    content.className = "textbox-content";
    content.contentEditable = "false";
    content.textContent = box.text || "";
    content.style.fontFamily = box.fontFamily || "Arial, sans-serif";
    content.style.fontSize   = (box.fontSizePt || 14) + "pt";
    content.style.color      = box.color || "#000000";

    // 縮放把手
    const handle = document.createElement("div");
    handle.className = "resize-handle";

    boxEl.appendChild(content);
    boxEl.appendChild(handle);

    // 欄位標籤（只在有 fieldKey 時顯示）
    if (box.fieldKey) {
        const tag = document.createElement("span");
        tag.className = "field-tag";
        tag.textContent = box.fieldKey;
        boxEl.appendChild(tag);
    }

    DOM.textboxLayer.appendChild(boxEl);
    return boxEl;
}

// ════════════════════════════════════════════════
// 新增文字框
// ════════════════════════════════════════════════

function addTextbox() {
    const page = editorState.pages[editorState.currentPageIndex];

    const box = {
        id:           "box-" + Date.now(),
        xPct:         0.1,
        yPct:         0.1,
        wPct:         0.3,
        hPct:         0.05,
        fontFamily:   "Arial, sans-serif",
        fontSizePt:   14,
        color:        "#000000",
        text:         "文字框",
        fieldKey:     "",
    };

    page.textboxes.push(box);

    // 直接加入 DOM（不整頁重渲染）
    const el = _appendTextboxEl(box);
    el.classList.add("selected");
    editorState.selectedBoxId = box.id;
    updatePropsPanel();
}

// ════════════════════════════════════════════════
// 頁面縮略圖
// ════════════════════════════════════════════════

function updatePageThumbnails() {
    DOM.pageList.innerHTML = "";
    editorState.pages.forEach((page, idx) => {
        const thumb = document.createElement("div");
        thumb.className = "page-thumb";
        if (idx === editorState.currentPageIndex) thumb.classList.add("active");

        const url = _bgUrl(page);
        if (url) {
            const img = document.createElement("img");
            img.src = url;
            thumb.appendChild(img);
        } else {
            thumb.style.cssText = "display:flex;align-items:center;justify-content:center;font-size:12px;color:#aaa;";
            thumb.textContent = `頁 ${idx + 1}`;
        }

        const label = document.createElement("div");
        label.style.cssText = "font-size:11px;text-align:center;color:#666;padding:2px 0;";
        label.textContent = `頁 ${idx + 1}`;
        thumb.appendChild(label);

        thumb.addEventListener("click", () => switchToPage(idx));
        thumb.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            if (confirm(`確定要刪除第 ${idx + 1} 頁嗎？`)) deletePage(idx);
        });

        DOM.pageList.appendChild(thumb);
    });
}

// ════════════════════════════════════════════════
// 屬性面板
// ════════════════════════════════════════════════

function updatePropsPanel() {
    const hasSelection = !!editorState.selectedBoxId;
    DOM.propsEmpty.style.display   = hasSelection ? "none" : "block";
    DOM.propsContent.style.display = hasSelection ? "flex" : "none";

    if (hasSelection) {
        // 同步屬性面板值（editor-toolbar.js 處理）
        if (typeof syncPropsPanel === "function") syncPropsPanel();
    }
}

// ════════════════════════════════════════════════
// 工具列事件
// ════════════════════════════════════════════════

function _bindToolbar() {
    document.getElementById("btn-back")?.addEventListener("click", () => {
        if (confirm("離開編輯器？所有未儲存的變更將丟失。")) window.location.href = "/";
    });
    document.getElementById("btn-upload-bg")?.addEventListener("click", () => DOM.fileBg.click());
    DOM.fileBg.addEventListener("change", (e) => {
        if (e.target.files.length) handleBgUpload(e.target.files[0]);
    });
    document.getElementById("btn-add-box")?.addEventListener("click", addTextbox);
    document.getElementById("btn-add-page")?.addEventListener("click", addPage);
}

// ════════════════════════════════════════════════
// 序列化 / 還原（供 editor-storage.js 使用）
// ════════════════════════════════════════════════

/**
 * 匯出所有頁面數據（模板格式，不含文字內容）
 */
function exportPagesAsTemplate() {
    return editorState.pages.map(page => ({
        pageIndex:  page.pageIndex,
        bgServerUrl: page.bgServerUrl || "",
        textboxes:  page.textboxes.map(box => ({
            id:          box.id,
            xPct:        box.xPct,
            yPct:        box.yPct,
            wPct:        box.wPct,
            hPct:        box.hPct,
            fontFamily:  box.fontFamily,
            fontSizePt:  box.fontSizePt,
            color:       box.color,
            fieldKey:    box.fieldKey,
            placeholder: box.text,  // 模板用 placeholder 存預設文字
        })),
    }));
}

/**
 * 匯出所有頁面的填寫內容（只含文字）
 */
function exportPagesAsFill() {
    return editorState.pages.map(page => ({
        pageIndex: page.pageIndex,
        textbox_values: Object.fromEntries(
            page.textboxes.map(box => [box.id, box.text || ""])
        ),
    }));
}

/**
 * 從模板 JSON 還原頁面結構（文字框位置/字型，不含內容）
 * pages: [{pageIndex, bgServerUrl, textboxes:[...]}]
 */
function importFromTemplate(pages) {
    editorState.pages = pages.map(p => ({
        pageIndex:   p.pageIndex,
        bgDataUrl:   "",
        bgServerUrl: p.bgServerUrl || "",
        textboxes:   (p.textboxes || []).map(box => ({
            id:          box.id || ("box-" + Date.now() + Math.random()),
            xPct:        box.xPct,
            yPct:        box.yPct,
            wPct:        box.wPct,
            hPct:        box.hPct,
            fontFamily:  box.fontFamily || "Arial, sans-serif",
            fontSizePt:  box.fontSizePt || 14,
            color:       box.color || "#000000",
            text:        box.placeholder || "",
            fieldKey:    box.fieldKey || "",
        })),
    }));
    editorState.currentPageIndex = 0;
    editorState.selectedBoxId = null;
    updatePageThumbnails();
    renderCurrentPage();
    updatePropsPanel();
}

/**
 * 套用填寫內容（覆蓋各框的 text）
 * fillPages: [{pageIndex, textbox_values:{boxId:text}}]
 */
function applyFillData(fillPages) {
    fillPages.forEach(fp => {
        const page = editorState.pages.find(p => p.pageIndex === fp.pageIndex);
        if (!page) return;
        Object.entries(fp.textbox_values || {}).forEach(([id, text]) => {
            const box = page.textboxes.find(b => b.id === id);
            if (box) box.text = text;
        });
    });
    renderCurrentPage();
}

/**
 * 取得當前選取的框（供外部模組使用）
 */
function getCurrentSelectedBox() {
    const page = editorState.pages[editorState.currentPageIndex];
    return page?.textboxes.find(b => b.id === editorState.selectedBoxId) || null;
}

// ════════════════════════════════════════════════
// 啟動
// ════════════════════════════════════════════════
document.addEventListener("DOMContentLoaded", initEditor);
