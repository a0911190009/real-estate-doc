# -*- coding: utf-8 -*-
"""
不動產說明書疊加編輯器 — Flask Blueprint
功能：上傳底圖、模板 CRUD、填寫內容 CRUD、物件庫 Proxy
"""

import os
import io
import json
import uuid
import base64
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, send_from_directory, send_file

# 導入共用函式
from utils import (
    require_login,
    GCS_BUCKET,
    GCS_EDITOR_BG_PREFIX,
    GCS_EDITOR_TEMPLATES_PREFIX,
    GCS_EDITOR_FILLS_PREFIX,
    gcs_save, gcs_load, gcs_list, gcs_delete,
    DRAFTS_DIR,
)

logger = logging.getLogger(__name__)

# ── 建立 Blueprint ──
editor_bp = Blueprint("editor", __name__)

# ── 物件庫設定 ──
LIBRARY_URL = os.environ.get("LIBRARY_SERVICE_URL", "")   # 物件庫 Cloud Run URL
SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "")

# ── 本地目錄 ──
EDITOR_BG_DIR = os.path.join(DRAFTS_DIR, "editor-bg")
EDITOR_TEMPLATES_DIR = os.path.join(DRAFTS_DIR, "editor-templates")
EDITOR_FILLS_DIR = os.path.join(DRAFTS_DIR, "editor-fills")
for _d in (EDITOR_BG_DIR, EDITOR_TEMPLATES_DIR, EDITOR_FILLS_DIR):
    os.makedirs(_d, exist_ok=True)


# ════════════════════════════════════════════════
# 工具函式
# ════════════════════════════════════════════════

def _now():
    return datetime.now(timezone.utc).isoformat()


# ── JSON 通用存取（自動選 GCS 或本地） ──

def _save(prefix, local_dir, key, data):
    data["updated_at"] = _now()
    if GCS_BUCKET:
        gcs_save(prefix, key, data)
    else:
        path = os.path.join(local_dir, f"{key}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _load(prefix, local_dir, key):
    if GCS_BUCKET:
        return gcs_load(prefix, key)
    path = os.path.join(local_dir, f"{key}.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _list(prefix, local_dir):
    if GCS_BUCKET:
        return gcs_list(prefix)
    result = []
    for fname in os.listdir(local_dir):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(local_dir, fname), "r", encoding="utf-8") as f:
                    d = json.load(f)
                result.append({
                    "id": fname[:-5],
                    "title": d.get("title", "未命名"),
                    "updated_at": d.get("updated_at", ""),
                })
            except Exception:
                pass
    return sorted(result, key=lambda x: x.get("updated_at", ""), reverse=True)


def _delete(prefix, local_dir, key):
    if GCS_BUCKET:
        gcs_delete(prefix, key)
    else:
        path = os.path.join(local_dir, f"{key}.json")
        if os.path.isfile(path):
            os.remove(path)


# ── 底圖存取（本地用 bytes 存，GCS 用 base64） ──

def _save_bg(bg_id, image_bytes, mime):
    """儲存底圖 bytes（本地）或 base64（GCS）"""
    if GCS_BUCKET:
        try:
            from google.cloud import storage as gcs_storage
            client = gcs_storage.Client()
            bucket = client.bucket(GCS_BUCKET)
            ext = "jpg" if "jpeg" in mime else "png"
            blob = bucket.blob(f"{GCS_EDITOR_BG_PREFIX}{bg_id}.{ext}")
            blob.upload_from_string(image_bytes, content_type=mime)
            return blob.public_url
        except Exception as e:
            logger.error("GCS 上傳底圖失敗: %s", e)
            raise
    else:
        # 本地：依 mime 決定副檔名
        ext = "jpg" if "jpeg" in mime else "png"
        path = os.path.join(EDITOR_BG_DIR, f"{bg_id}.{ext}")
        with open(path, "wb") as f:
            f.write(image_bytes)
        return f"/api/editor/bg/{bg_id}.{ext}"


def _serve_bg_local(filename):
    """從本地提供底圖"""
    return send_from_directory(EDITOR_BG_DIR, filename)


# ════════════════════════════════════════════════
# 路由：頁面
# ════════════════════════════════════════════════

@editor_bp.route("/editor")
@require_login
def editor_main():
    """編輯器主頁面（回傳 editor.html，不走 Jinja2）"""
    return send_from_directory("static", "editor.html")


# ════════════════════════════════════════════════
# 路由：底圖
# ════════════════════════════════════════════════

@editor_bp.route("/api/editor/upload-bg", methods=["POST"])
@require_login
def api_upload_bg():
    """
    上傳底圖（multipart/form-data，欄位名 image）
    回傳：{"ok": true, "bg_id": "...", "url": "/api/editor/bg/xxx.jpg"}
    """
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "請上傳圖片檔案"}), 400

    mime = file.content_type or "image/jpeg"
    if "image" not in mime:
        return jsonify({"error": "只接受圖片檔案（PNG/JPG）"}), 400

    bg_id = str(uuid.uuid4())[:12]
    image_bytes = file.read()

    try:
        url = _save_bg(bg_id, image_bytes, mime)
        logger.info("底圖上傳成功 bg_id=%s", bg_id)
        return jsonify({"ok": True, "bg_id": bg_id, "url": url})
    except Exception as e:
        logger.error("底圖上傳失敗: %s", e)
        return jsonify({"error": str(e)}), 500


@editor_bp.route("/api/editor/bg/<path:filename>")
def api_serve_bg(filename):
    """提供本地底圖（Cloud Run 用 GCS 公開 URL，不會進入這裡）"""
    return _serve_bg_local(filename)


# ════════════════════════════════════════════════
# 路由：模板
# ════════════════════════════════════════════════

@editor_bp.route("/api/editor/templates", methods=["GET"])
@require_login
def api_list_templates():
    """列出所有模板（id, title, updated_at）"""
    return jsonify(_list(GCS_EDITOR_TEMPLATES_PREFIX, EDITOR_TEMPLATES_DIR))


@editor_bp.route("/api/editor/templates", methods=["POST"])
@require_login
def api_save_template():
    """
    儲存模板（模板只存框框結構，不含文字內容）
    Body JSON：{id?, title, pages: [{page_index, bg_url, textboxes:[...]}]}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "請傳送 JSON 資料"}), 400

    tpl_id = data.get("id") or f"tpl-{uuid.uuid4().hex[:12]}"
    data["id"] = tpl_id
    if not data.get("title"):
        data["title"] = "未命名模板"

    # 移除每個文字框的 text 欄位（模板只存結構，不存內容）
    for page in data.get("pages", []):
        for box in page.get("textboxes", []):
            box.pop("text", None)

    try:
        _save(GCS_EDITOR_TEMPLATES_PREFIX, EDITOR_TEMPLATES_DIR, tpl_id, data)
        return jsonify({"ok": True, "id": tpl_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@editor_bp.route("/api/editor/templates/<tpl_id>", methods=["GET"])
@require_login
def api_get_template(tpl_id):
    """取得單個模板"""
    data = _load(GCS_EDITOR_TEMPLATES_PREFIX, EDITOR_TEMPLATES_DIR, tpl_id)
    if data is None:
        return jsonify({"error": "找不到模板"}), 404
    return jsonify(data)


@editor_bp.route("/api/editor/templates/<tpl_id>", methods=["DELETE"])
@require_login
def api_delete_template(tpl_id):
    """刪除模板"""
    try:
        _delete(GCS_EDITOR_TEMPLATES_PREFIX, EDITOR_TEMPLATES_DIR, tpl_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════
# 路由：填寫內容
# ════════════════════════════════════════════════

@editor_bp.route("/api/editor/fills", methods=["GET"])
@require_login
def api_list_fills():
    """列出所有填寫內容（id, title, updated_at）"""
    return jsonify(_list(GCS_EDITOR_FILLS_PREFIX, EDITOR_FILLS_DIR))


@editor_bp.route("/api/editor/fills", methods=["POST"])
@require_login
def api_save_fill():
    """
    儲存填寫內容
    Body JSON：{id?, title, template_id, object_id?, pages:[{page_index, textbox_values:{box_id:text}}]}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "請傳送 JSON 資料"}), 400

    fill_id = data.get("id") or f"fill-{uuid.uuid4().hex[:12]}"
    data["id"] = fill_id
    if not data.get("title"):
        data["title"] = "未命名填寫"

    try:
        _save(GCS_EDITOR_FILLS_PREFIX, EDITOR_FILLS_DIR, fill_id, data)
        return jsonify({"ok": True, "id": fill_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@editor_bp.route("/api/editor/fills/<fill_id>", methods=["GET"])
@require_login
def api_get_fill(fill_id):
    """取得單個填寫內容"""
    data = _load(GCS_EDITOR_FILLS_PREFIX, EDITOR_FILLS_DIR, fill_id)
    if data is None:
        return jsonify({"error": "找不到填寫內容"}), 404
    return jsonify(data)


@editor_bp.route("/api/editor/fills/<fill_id>", methods=["DELETE"])
@require_login
def api_delete_fill(fill_id):
    """刪除填寫內容"""
    try:
        _delete(GCS_EDITOR_FILLS_PREFIX, EDITOR_FILLS_DIR, fill_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ════════════════════════════════════════════════
# 路由：物件庫 Proxy
# ════════════════════════════════════════════════

@editor_bp.route("/api/editor/objects", methods=["GET"])
@require_login
def api_editor_objects():
    """
    代理呼叫物件庫 API，回傳物件清單。
    若 LIBRARY_SERVICE_URL 未設定，回傳空清單（本地開發友善）。
    """
    if not LIBRARY_URL:
        logger.info("LIBRARY_SERVICE_URL 未設定，回傳空物件清單")
        return jsonify([])

    url = LIBRARY_URL.rstrip("/") + "/api/objects/for-service-selling"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "X-Service-Key": SERVICE_API_KEY,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            items = result.get("items", result) if isinstance(result, dict) else result
            return jsonify(items)
    except urllib.error.HTTPError as e:
        logger.error("物件庫 API HTTPError: %s %s", e.code, e.reason)
        return jsonify([])
    except Exception as e:
        logger.error("物件庫 API 呼叫失敗: %s", e)
        return jsonify([])
