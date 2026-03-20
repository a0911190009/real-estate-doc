/**
 * 不動產說明書編輯器 — 物件庫模組
 * 功能：
 *  1. 啟動時自動從物件庫 API 載入所有欄位，填入「欄位對應」下拉選單
 *  2. 帶入物件資料到文字框
 */

// ── 預設欄位清單（物件庫無法連線時的備援） ──
const DEFAULT_FIELDS = [
    { key: "address",       label: "地址" },
    { key: "project_name",  label: "案名" },
    { key: "price",         label: "售價" },
    { key: "building_ping", label: "建坪" },
    { key: "land_ping",     label: "地坪" },
    { key: "case_number",   label: "委託編號" },
    { key: "location_area", label: "區域" },
];

// ── 不顯示在欄位下拉的系統欄位（物件庫內部用） ──
const SKIP_KEYS = new Set(["id", "user_id", "created_at", "updated_at", "deleted", "_id"]);

// ════════════════════════════════════════════════
// 初始化
// ════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => {
        _bindObjectModal();
        _loadFieldsIntoDropdown();  // 自動載入物件庫欄位
    }, 150);
});

function _bindObjectModal() {
    const modal = document.getElementById("object-modal");
    document.getElementById("btn-import-object")?.addEventListener("click", _openObjectModal);
    document.getElementById("object-modal-close")?.addEventListener("click", () => modal.classList.add("hidden"));
    modal.addEventListener("click", e => { if (e.target === modal) modal.classList.add("hidden"); });
}

// ════════════════════════════════════════════════
// 動態載入欄位清單到「欄位對應」下拉選單
// ════════════════════════════════════════════════

/**
 * 呼叫物件庫 API，取得所有可用欄位，填入 #prop-field-key 下拉選單
 * 如果 API 失敗，使用預設欄位清單
 */
function _loadFieldsIntoDropdown() {
    fetch("/api/editor/objects")
        .then(r => r.json())
        .then(items => {
            if (!items || !items.length) {
                // 物件庫空的：用預設欄位
                _populateFieldDropdown(DEFAULT_FIELDS);
                return;
            }

            // 從所有物件取出所有 key，合併去重
            const allKeys = new Set();
            items.forEach(obj => {
                Object.keys(obj).forEach(k => {
                    if (!SKIP_KEYS.has(k)) allKeys.add(k);
                });
            });

            // 轉成 [{key, label}] 格式（label 用 key 本身，已是中文就直接顯示）
            const fields = Array.from(allKeys).map(k => ({ key: k, label: k }));
            _populateFieldDropdown(fields);
        })
        .catch(() => {
            // 物件庫未設定或連線失敗：靜默使用預設欄位
            _populateFieldDropdown(DEFAULT_FIELDS);
        });
}

/**
 * 填入 #prop-field-key 選單
 * fields: [{key, label}]
 */
function _populateFieldDropdown(fields) {
    const sel = document.getElementById("prop-field-key");
    if (!sel) return;

    // 保留目前選取值
    const currentVal = sel.value;

    // 清空並重建（保留「無」選項）
    sel.innerHTML = '<option value="">（無）</option>';
    fields.forEach(f => {
        const opt = document.createElement("option");
        opt.value = f.key;
        opt.textContent = f.label;
        sel.appendChild(opt);
    });

    // 恢復選取值（若仍存在的話）
    if (currentVal) sel.value = currentVal;
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
        // 嘗試常見的標題欄位名稱
        const title = obj.project_name || obj.案名 || obj.物件名稱 || obj.name || "未命名";
        const addr  = obj.address || obj.地址 || obj.物件地址 || "";
        const price = obj.price ? `售價 ${obj.price} 萬` : (obj.售價 ? `售價 ${obj.售價}` : "");
        const ping  = obj.building_ping ? `建坪 ${obj.building_ping}` : (obj.建坪 ? `建坪 ${obj.建坪}` : "");
        item.innerHTML = `
            <strong>${_esc(title)}</strong>
            <small>${_esc(addr || "地址未設定")}</small>
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
        // fieldKey 對應到物件的哪個欄位（直接用 key 查）
        const value = obj[box.fieldKey];
        if (value !== undefined && value !== null && value !== "") {
            box.text = String(value);
            // 即時更新 DOM
            const el = document.querySelector(`[data-box-id="${box.id}"] .textbox-content`);
            if (el) el.textContent = box.text;
            filled++;
        }
    });

    document.getElementById("object-modal").classList.add("hidden");

    const title = obj.project_name || obj.案名 || obj.物件名稱 || "此物件";
    if (filled > 0) {
        _toast(`已帶入「${title}」的 ${filled} 個欄位`);
    } else {
        _toast(`「${title}」帶入完成（目前頁面沒有設定欄位對應的文字框）`);
    }
}

// ════════════════════════════════════════════════
// 工具函式
// ════════════════════════════════════════════════

function _esc(str) {
    return String(str).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function _toast(msg) {
    const el = document.createElement("div");
    el.textContent = msg;
    el.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:6px;font-size:14px;z-index:9999;opacity:0;transition:opacity .3s;";
    document.body.appendChild(el);
    requestAnimationFrame(() => { el.style.opacity = "1"; });
    setTimeout(() => { el.style.opacity = "0"; setTimeout(() => el.remove(), 400); }, 2500);
}
