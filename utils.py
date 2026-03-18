# -*- coding: utf-8 -*-
"""
不動產工具共用函式
登入驗證、草稿存取（GCS/本地）、設定等
"""

import os
import json
import logging
from datetime import datetime, timezone
from flask import session, redirect

logger = logging.getLogger(__name__)

# 環境變數
PORTAL_URL = os.environ.get("PORTAL_URL", "")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")
GCS_DRAFTS_PREFIX = "doc-drafts/"
GCS_EDITOR_BG_PREFIX = "editor-bg/"
GCS_EDITOR_TEMPLATES_PREFIX = "editor-templates/"
GCS_EDITOR_FILLS_PREFIX = "editor-fills/"

# 本地草稿目錄
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
DRAFTS_DIR = os.path.join(_APP_DIR, "drafts")
os.makedirs(DRAFTS_DIR, exist_ok=True)

# ──────────────────────────────────────────────
# 登入驗證裝飾器
# ──────────────────────────────────────────────
def require_login(f):
    """驗證使用者已登入（Portal session 或直接開發模式）"""
    import functools
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # 開發模式跳過驗證
        if os.environ.get("FLASK_DEBUG"):
            return f(*args, **kwargs)
        if not session.get("user_email"):
            return redirect(PORTAL_URL or "/")
        return f(*args, **kwargs)
    return wrapper


# ──────────────────────────────────────────────
# GCS 操作（通用封裝）
# ──────────────────────────────────────────────
def _get_gcs_client():
    """取得 GCS client（若 GCS_BUCKET 未設定回傳 None）"""
    if not GCS_BUCKET:
        return None
    try:
        from google.cloud import storage
        return storage.Client()
    except Exception as e:
        logger.error("GCS Client 初始化失敗: %s", e)
        return None


def gcs_save(prefix: str, key: str, data: dict):
    """儲存 JSON 到 GCS（prefix 決定前綴，例如 GCS_EDITOR_TEMPLATES_PREFIX）"""
    try:
        client = _get_gcs_client()
        if not client:
            raise ValueError("GCS 未設定")
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(f"{prefix}{key}.json")
        blob.upload_from_string(json.dumps(data, ensure_ascii=False), content_type="application/json")
    except Exception as e:
        logger.error("GCS 儲存失敗 (prefix=%s, key=%s): %s", prefix, key, e)
        raise


def gcs_load(prefix: str, key: str) -> dict:
    """從 GCS 讀取 JSON（找不到回傳 None）"""
    try:
        client = _get_gcs_client()
        if not client:
            return None
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(f"{prefix}{key}.json")
        if not blob.exists():
            return None
        return json.loads(blob.download_as_text())
    except Exception as e:
        logger.error("GCS 讀取失敗 (prefix=%s, key=%s): %s", prefix, key, e)
        return None


def gcs_list(prefix: str) -> list:
    """列出 GCS 某前綴下的所有 JSON"""
    try:
        client = _get_gcs_client()
        if not client:
            return []
        bucket = client.bucket(GCS_BUCKET)
        blobs = bucket.list_blobs(prefix=prefix)
        result = []
        for blob in blobs:
            try:
                data = json.loads(blob.download_as_text())
                key = blob.name.replace(prefix, "").replace(".json", "")
                result.append({
                    "id": key,
                    "title": data.get("title", "未命名"),
                    "updated_at": data.get("updated_at", ""),
                })
            except Exception:
                pass
        return sorted(result, key=lambda x: x.get("updated_at", ""), reverse=True)
    except Exception as e:
        logger.error("GCS 列表失敗 (prefix=%s): %s", prefix, e)
        return []


def gcs_delete(prefix: str, key: str):
    """刪除 GCS 中的 JSON"""
    try:
        client = _get_gcs_client()
        if not client:
            raise ValueError("GCS 未設定")
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(f"{prefix}{key}.json")
        blob.delete()
    except Exception as e:
        logger.error("GCS 刪除失敗 (prefix=%s, key=%s): %s", prefix, key, e)
        raise


# ──────────────────────────────────────────────
# 本地草稿操作
# ──────────────────────────────────────────────
def _save_draft_local(draft_id: str, data: dict):
    """儲存草稿到本地"""
    path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_draft_local(draft_id: str) -> dict:
    """從本地讀取草稿"""
    path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _list_drafts_local() -> list:
    """列出本地所有草稿"""
    result = []
    for fname in os.listdir(DRAFTS_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(DRAFTS_DIR, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                result.append({
                    "id": fname.replace(".json", ""),
                    "title": data.get("title", "未命名"),
                    "updated_at": data.get("updated_at", ""),
                })
            except Exception:
                pass
    return sorted(result, key=lambda x: x.get("updated_at", ""), reverse=True)


def _delete_draft_local(draft_id: str):
    """刪除本地草稿"""
    path = os.path.join(DRAFTS_DIR, f"{draft_id}.json")
    if os.path.isfile(path):
        os.remove(path)


# ──────────────────────────────────────────────
# 草稿通用 API（自動選擇 GCS 或本地）
# ──────────────────────────────────────────────
def save_draft(draft_id: str, data: dict):
    """儲存草稿（自動選擇 GCS 或本地）"""
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    if GCS_BUCKET:
        _save_draft_gcs(draft_id, data)
    else:
        _save_draft_local(draft_id, data)


def _save_draft_gcs(draft_id: str, data: dict):
    """儲存草稿到 GCS（內部用）"""
    try:
        gcs_save(GCS_DRAFTS_PREFIX, draft_id, data)
    except Exception as e:
        logger.error("GCS 儲存草稿失敗: %s", e)
        raise


def load_draft(draft_id: str) -> dict:
    """讀取草稿（自動選擇 GCS 或本地）"""
    if GCS_BUCKET:
        return _load_draft_gcs(draft_id)
    return _load_draft_local(draft_id)


def _load_draft_gcs(draft_id: str) -> dict:
    """從 GCS 讀取草稿（內部用）"""
    try:
        return gcs_load(GCS_DRAFTS_PREFIX, draft_id)
    except Exception as e:
        logger.error("GCS 讀取草稿失敗: %s", e)
        return None


def list_drafts() -> list:
    """列出所有草稿"""
    if GCS_BUCKET:
        return _list_drafts_gcs()
    return _list_drafts_local()


def _list_drafts_gcs() -> list:
    """列出 GCS 所有草稿（內部用）"""
    try:
        return gcs_list(GCS_DRAFTS_PREFIX)
    except Exception as e:
        logger.error("GCS 列出草稿失敗: %s", e)
        return []


def delete_draft(draft_id: str):
    """刪除草稿"""
    if GCS_BUCKET:
        _delete_draft_gcs(draft_id)
    else:
        _delete_draft_local(draft_id)


def _delete_draft_gcs(draft_id: str):
    """刪除 GCS 草稿（內部用）"""
    try:
        gcs_delete(GCS_DRAFTS_PREFIX, draft_id)
    except Exception as e:
        logger.error("GCS 刪除草稿失敗: %s", e)
        raise
