/**
 * 不動產說明書編輯器 — 存儲模組
 * 模板 CRUD、填寫內容 CRUD、LocalStorage 自動存檔
 */

// ════════════════════════════════════════════════
// 模板 API
// ════════════════════════════════════════════════

function saveTemplateToServer(data) {
    return fetch("/api/editor/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    }).then(r => r.json());
}

function loadTemplateListFromServer(callback) {
    fetch("/api/editor/templates")
        .then(r => r.json())
        .then(callback)
        .catch(err => { console.error("載入模板清單失敗:", err); callback([]); });
}

function loadTemplateFromServer(id, callback) {
    fetch(`/api/editor/templates/${id}`)
        .then(r => r.json())
        .then(callback)
        .catch(err => { console.error("載入模板失敗:", err); callback(null); });
}

function deleteTemplateFromServer(id) {
    return fetch(`/api/editor/templates/${id}`, { method: "DELETE" }).then(r => r.json());
}

// ════════════════════════════════════════════════
// 填寫內容 API
// ════════════════════════════════════════════════

function saveFillToServer(data) {
    return fetch("/api/editor/fills", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    }).then(r => r.json());
}

function loadFillListFromServer(callback) {
    fetch("/api/editor/fills")
        .then(r => r.json())
        .then(callback)
        .catch(err => { console.error("載入填寫清單失敗:", err); callback([]); });
}

function loadFillFromServer(id, callback) {
    fetch(`/api/editor/fills/${id}`)
        .then(r => r.json())
        .then(callback)
        .catch(err => { console.error("載入填寫內容失敗:", err); callback(null); });
}

function deleteFillFromServer(id) {
    return fetch(`/api/editor/fills/${id}`, { method: "DELETE" }).then(r => r.json());
}

// ════════════════════════════════════════════════
// LocalStorage 自動存檔（備用）
// ════════════════════════════════════════════════

const _LS_KEY = "editor-autosave";

function _autoSave() {
    try {
        const data = {
            pages: exportPagesAsTemplate(),
            timestamp: Date.now(),
        };
        localStorage.setItem(_LS_KEY, JSON.stringify(data));
    } catch (e) {
        // localStorage 已滿就跳過
    }
}

function _restoreAutoSave() {
    try {
        const raw = localStorage.getItem(_LS_KEY);
        if (!raw) return false;
        const data = JSON.parse(raw);
        if (!data.pages || !data.pages.length) return false;
        const dt = new Date(data.timestamp).toLocaleString("zh-TW");
        if (!confirm(`偵測到上次未儲存的編輯（${dt}），要復原嗎？`)) return false;
        importFromTemplate(data.pages);
        return true;
    } catch (e) {
        return false;
    }
}

// 啟動自動存檔
document.addEventListener("DOMContentLoaded", () => {
    // 30 秒自動存一次
    setInterval(_autoSave, 30000);
});
