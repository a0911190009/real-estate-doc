/**
 * 不動產說明書編輯器 — 物件庫模組
 * 功能：呼叫後端 proxy API，帶入物件資料到文字框
 */

// ── 欄位對應表（物件庫 API 的欄位 key → 文字框 fieldKey） ──
const FIELD_MAP = {
    address:       "物件地址",
    project_name:  "案名",
    price:         "售價（萬）",
    building_ping: "建坪",
    land_ping:     "地坪",
    case_number:   "委託編號",
    location_area: "區域",
};

// ════════════════════════════════════════════════
// 初始化
// ════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => {
        _bindObjectModal();
    }, 100);
});

function _bindObjectModal() {
    const modal = document.getElementById("object-modal");
    document.getElementById("btn-import-object")?.addEventListener("click", _openObjectModal);
    document.getElementById("object-modal-close")?.addEventListener("click", () => modal.classList.add("hidden"));
    modal.addEventListener("click", e => { if (e.target === modal) modal.classList.add("hidden"); });
}

// ════════════════════════════════════════════════
// 開啟物件清單 Modal
// ════════════════════════════════════════════════

function _openObjectModal() {
    const modal = document.getElementById("object-modal");
    const list  = document.getElementById("object-list");
    list.innerHTML = "<p style='text-align:center;color:#999;padding:16px;'>載入中...</p>";
    modal.classList.remove("hidden");

    fetch("/api/editor/objects")
        .then(r => r.json())
        .then(items => _renderObjectList(items))
        .catch(err => {
            list.innerHTML = `<p style='text-align:center;color:red;padding:16px;'>載入失敗：${err.message}</p>`;
        });
}

function _renderObjectList(items) {
    const list = document.getElementById("object-list");
    list.innerHTML = "";

    if (!items || !items.length) {
        list.innerHTML = "<p style='text-align:center;color:#999;padding:16px;'>物件庫沒有資料（或 LIBRARY_SERVICE_URL 未設定）</p>";
        return;
    }

    items.forEach(obj => {
        const item = document.createElement("div");
        item.className = "object-item";
        const price = obj.price ? `售價 ${obj.price} 萬` : "";
        const ping  = obj.building_ping ? `建坪 ${obj.building_ping}` : "";
        item.innerHTML = `
            <strong>${_esc(obj.project_name || "未命名")}</strong>
            <small>${_esc(obj.address || "地址未設定")}</small>
            <small style="color:#888;">${[price, ping].filter(Boolean).join("　")}</small>
        `;
        item.addEventListener("click", () => _importObject(obj));
        list.appendChild(item);
    });
}

// ════════════════════════════════════════════════
// 帶入物件資料
// ════════════════════════════════════════════════

function _importObject(obj) {
    const page = editorState.pages[editorState.currentPageIndex];
    let filled = 0;

    page.textboxes.forEach(box => {
        if (!box.fieldKey) return;
        // fieldKey 對應到物件的哪個欄位
        const value = obj[box.fieldKey];
        if (value !== undefined && value !== null && value !== "") {
            box.text = String(value);
            // 即時更新 DOM（如果該框正在顯示）
            const el = document.querySelector(`[data-box-id="${box.id}"] .textbox-content`);
            if (el) el.textContent = box.text;
            filled++;
        }
    });

    document.getElementById("object-modal").classList.add("hidden");

    const name = obj.project_name || "此物件";
    if (filled > 0) {
        _toast(`已帶入「${name}」的 ${filled} 個欄位`);
    } else {
        _toast(`「${name}」帶入完成（目前頁面沒有設定欄位對應的文字框）`);
    }
}

// ════════════════════════════════════════════════
// 工具函式
// ════════════════════════════════════════════════

function _esc(str) {
    return String(str).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

// 使用 editor-toolbar.js 的 _toast（或自備備用版）
function _toast(msg) {
    if (typeof window._toast === "function") {
        window._toast(msg);
        return;
    }
    // 備用：直接在工具列的 _toast 定義之前，用 alert
    const el = document.createElement("div");
    el.textContent = msg;
    el.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:6px;font-size:14px;z-index:9999;opacity:0;transition:opacity .3s;";
    document.body.appendChild(el);
    requestAnimationFrame(() => { el.style.opacity = "1"; });
    setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 400); }, 2500);
}
