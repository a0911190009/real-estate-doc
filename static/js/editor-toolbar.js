/**
 * 不動產說明書編輯器 — 工具列模組
 * 功能：字型/字號/顏色/欄位設定、列印預覽、模板存取
 */

// ════════════════════════════════════════════════
// 初始化
// ════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    setTimeout(() => {
        _bindPropsPanel();
        _bindPrintModal();
        _bindTemplateModals();
    }, 100);
});

// ════════════════════════════════════════════════
// 屬性面板
// ════════════════════════════════════════════════

function _bindPropsPanel() {
    // 字型
    document.getElementById("prop-font-family")?.addEventListener("change", e => {
        if (editorState.selectedBoxId)
            updateTextboxProperty(editorState.selectedBoxId, "fontFamily", e.target.value);
    });

    // 字號
    document.getElementById("prop-font-size")?.addEventListener("input", e => {
        const size = parseInt(e.target.value);
        if (editorState.selectedBoxId && !isNaN(size))
            updateTextboxProperty(editorState.selectedBoxId, "fontSizePt", size);
    });

    // 字色
    document.getElementById("prop-color")?.addEventListener("input", e => {
        if (editorState.selectedBoxId)
            updateTextboxProperty(editorState.selectedBoxId, "color", e.target.value);
    });

    // 欄位對應
    document.getElementById("prop-field-key")?.addEventListener("change", e => {
        if (editorState.selectedBoxId)
            updateTextboxProperty(editorState.selectedBoxId, "fieldKey", e.target.value);
    });

    // 刪除框
    document.getElementById("btn-delete-box")?.addEventListener("click", () => {
        if (editorState.selectedBoxId && confirm("確定要刪除此文字框嗎？"))
            deleteTextbox(editorState.selectedBoxId);
    });
}

/**
 * 同步目前選取框的屬性到面板控件（editor-canvas.js 會呼叫）
 */
function syncPropsPanel() {
    const box = getCurrentSelectedBox();
    if (!box) return;
    const el = v => document.getElementById(v);
    if (el("prop-font-family")) el("prop-font-family").value = box.fontFamily || "Arial, sans-serif";
    if (el("prop-font-size"))   el("prop-font-size").value   = box.fontSizePt || 14;
    if (el("prop-color"))       el("prop-color").value       = box.color || "#000000";
    if (el("prop-field-key"))   el("prop-field-key").value   = box.fieldKey || "";
}

// ════════════════════════════════════════════════
// 列印預覽 Modal
// ════════════════════════════════════════════════

function _bindPrintModal() {
    const modal = document.getElementById("print-modal");

    document.getElementById("btn-print")?.addEventListener("click", _openPrintModal);
    document.getElementById("print-modal-close")?.addEventListener("click", () => modal.classList.add("hidden"));
    document.getElementById("btn-print-cancel")?.addEventListener("click", () => modal.classList.add("hidden"));
    document.getElementById("btn-print-execute")?.addEventListener("click", () => window.print());

    // 點 Modal 背景也關閉
    modal.addEventListener("click", e => { if (e.target === modal) modal.classList.add("hidden"); });

    // 留白滑桿
    ["top", "bottom", "left", "right"].forEach(side => {
        const slider = document.getElementById(`margin-${side}`);
        const label  = document.getElementById(`margin-${side}-value`);
        slider?.addEventListener("input", e => {
            if (label) label.textContent = e.target.value;
            document.documentElement.style.setProperty(`--print-margin-${side}`, `${e.target.value}mm`);
            // 同步更新預覽的留白
            const preview = document.querySelector(".print-preview-inner");
            if (preview) {
                preview.style.padding = `${document.getElementById("margin-top")?.value || 0}mm ${document.getElementById("margin-right")?.value || 0}mm ${document.getElementById("margin-bottom")?.value || 0}mm ${document.getElementById("margin-left")?.value || 0}mm`;
            }
        });
    });
}

function _openPrintModal() {
    const modal   = document.getElementById("print-modal");
    const preview = document.getElementById("print-preview");

    // 重建預覽內容
    preview.innerHTML = "";
    const inner = document.createElement("div");
    inner.className = "print-preview-inner";

    editorState.pages.forEach((page, idx) => {
        const pageDiv = document.createElement("div");
        pageDiv.className = "print-page";
        pageDiv.style.cssText = "position:relative;display:inline-block;width:100%;margin-bottom:16px;";

        // 底圖
        const url = page.bgServerUrl || page.bgDataUrl || "";
        if (url) {
            const img = document.createElement("img");
            img.src = url;
            img.style.cssText = "display:block;width:100%;height:auto;";
            pageDiv.appendChild(img);
        } else {
            pageDiv.style.cssText += "background:#fff;aspect-ratio:8.5/11;border:1px solid #ddd;";
        }

        // 文字框疊層（僅視覺預覽，無 border）
        const tl = document.createElement("div");
        tl.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;";
        page.textboxes.forEach(box => {
            const d = document.createElement("div");
            d.style.cssText = [
                `position:absolute`,
                `left:${box.xPct * 100}%`,
                `top:${box.yPct * 100}%`,
                `width:${box.wPct * 100}%`,
                `height:${box.hPct * 100}%`,
                `font-family:${box.fontFamily}`,
                `font-size:${box.fontSizePt}pt`,
                `color:${box.color}`,
                `overflow:hidden`,
                `word-wrap:break-word`,
                `padding:2px`,
            ].join(";");
            d.textContent = box.text || "";
            tl.appendChild(d);
        });
        pageDiv.appendChild(tl);

        const pageLabel = document.createElement("div");
        pageLabel.style.cssText = "font-size:11px;color:#999;text-align:center;margin-top:4px;";
        pageLabel.textContent = `第 ${idx + 1} 頁`;
        pageDiv.appendChild(pageLabel);

        inner.appendChild(pageDiv);
    });

    preview.appendChild(inner);
    modal.classList.remove("hidden");
}

// ════════════════════════════════════════════════
// 模板存取
// ════════════════════════════════════════════════

function _bindTemplateModals() {
    // ── 儲存模板 ──
    const saveModal = document.getElementById("save-template-modal");
    document.getElementById("btn-save-template")?.addEventListener("click", () => {
        document.getElementById("template-title").value = "";
        saveModal.classList.remove("hidden");
    });
    document.getElementById("save-template-close")?.addEventListener("click", () => saveModal.classList.add("hidden"));
    document.getElementById("btn-save-template-cancel")?.addEventListener("click", () => saveModal.classList.add("hidden"));
    saveModal.addEventListener("click", e => { if (e.target === saveModal) saveModal.classList.add("hidden"); });

    document.getElementById("btn-save-template-confirm")?.addEventListener("click", () => {
        const title = document.getElementById("template-title").value.trim();
        if (!title) { alert("請輸入模板名稱"); return; }
        _doSaveTemplate(title);
    });

    // ── 載入模板 ──
    const loadModal = document.getElementById("template-modal");
    document.getElementById("btn-load-template")?.addEventListener("click", _openTemplateList);
    document.getElementById("template-modal-close")?.addEventListener("click", () => loadModal.classList.add("hidden"));
    loadModal.addEventListener("click", e => { if (e.target === loadModal) loadModal.classList.add("hidden"); });
}

function _doSaveTemplate(title) {
    const data = {
        title,
        pages: exportPagesAsTemplate(),
    };

    saveTemplateToServer(data)
        .then(res => {
            if (res.ok) {
                document.getElementById("save-template-modal").classList.add("hidden");
                _toast(`模板「${title}」已儲存`);
            } else {
                alert("儲存失敗：" + (res.error || "未知錯誤"));
            }
        })
        .catch(err => alert("儲存失敗：" + err.message));
}

function _openTemplateList() {
    const modal = document.getElementById("template-modal");
    const list  = document.getElementById("template-list");
    list.innerHTML = "<p style='text-align:center;color:#999;padding:16px;'>載入中...</p>";
    modal.classList.remove("hidden");

    loadTemplateListFromServer(templates => {
        list.innerHTML = "";
        if (!templates.length) {
            list.innerHTML = "<p style='text-align:center;color:#999;padding:16px;'>還沒有儲存過模板</p>";
            return;
        }
        templates.forEach(tpl => {
            const item = document.createElement("div");
            item.className = "template-item";
            const date = tpl.updated_at ? new Date(tpl.updated_at).toLocaleString("zh-TW") : "";
            item.innerHTML = `<strong>${_esc(tpl.title)}</strong><small>更新：${date}</small>`;
            item.addEventListener("click", () => {
                if (confirm(`載入模板「${tpl.title}」？目前的編輯將被覆蓋。`)) {
                    loadTemplateFromServer(tpl.id, data => {
                        if (data && data.pages) {
                            importFromTemplate(data.pages);
                            modal.classList.add("hidden");
                            _toast(`已載入模板「${tpl.title}」`);
                        } else {
                            alert("載入失敗");
                        }
                    });
                }
            });
            list.appendChild(item);
        });
    });
}

// ════════════════════════════════════════════════
// 工具函式
// ════════════════════════════════════════════════

/** 簡易 toast 通知 */
function _toast(msg) {
    const el = document.createElement("div");
    el.textContent = msg;
    el.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:6px;font-size:14px;z-index:9999;opacity:0;transition:opacity .3s;";
    document.body.appendChild(el);
    requestAnimationFrame(() => { el.style.opacity = "1"; });
    setTimeout(() => {
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 400);
    }, 2500);
}

/** HTML 跳脫 */
function _esc(str) {
    return String(str).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
