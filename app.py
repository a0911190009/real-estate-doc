# -*- coding: utf-8 -*-
"""
不動產說明書工具 — Flask 後端
功能：上傳謄本/委託書圖片 → Gemini Vision 辨識欄位 → 填入表單 → 列印 PDF
"""

import os
import json
import uuid
import base64
import logging
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory, session, redirect

# 讀取環境變數（優先本專案 .env，其次上層 .env）
try:
    from dotenv import load_dotenv
    _app_dir = os.path.dirname(os.path.abspath(__file__))
    _local_env = os.path.join(_app_dir, ".env")
    _central_env = os.path.join(_app_dir, "..", ".env")
    if os.path.isfile(_local_env):
        load_dotenv(_local_env, override=False)
    if os.path.isfile(_central_env):
        load_dotenv(_central_env, override=False)
except Exception:
    pass

# 日誌設定
try:
    from pythonjsonlogger import jsonlogger
    _handler = logging.StreamHandler()
    _handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.root.handlers = [_handler]
    logging.root.setLevel(logging.INFO)
except ImportError:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

# 導入共用函式（utils.py）
from utils import require_login, save_draft, load_draft, list_drafts, GCS_BUCKET, PORTAL_URL

# Portal token 驗證
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

app = Flask(__name__, static_folder="static", static_url_path="")
_secret = os.environ.get("FLASK_SECRET_KEY", "dev-only-key")
app.secret_key = _secret
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = not os.environ.get("FLASK_DEBUG")

# ─── 開發模式：自動模擬登入 ───
@app.before_request
def auto_login_dev():
    """本地開發時，SKIP_AUTH=true 會自動模擬登入，跳過 Portal token 驗證"""
    if os.getenv('SKIP_AUTH'):
        session['user_email'] = 'dev@test.com'
        session['user_name'] = '開發測試'

# Gemini API 設定
GEMINI_API_KEY = (
    os.environ.get("GOOGLE_AI_STUDIO_API_KEY") or
    os.environ.get("GOOGLE_API_KEY") or
    ""
)

# Service API Key
SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "")

# 應用目錄（封面設定等用）
_APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 公司資訊（可由環境變數覆蓋）
COMPANY_NAME = os.environ.get("COMPANY_NAME", "日盛房屋")
COMPANY_ADDRESS = os.environ.get("COMPANY_ADDRESS", "台東市四維路三段241號")
COMPANY_PHONE = os.environ.get("COMPANY_PHONE", "(089) 357888")
AGENT_NAME = os.environ.get("AGENT_NAME", "陳威良")
AGENT_LICENSE = os.environ.get("AGENT_LICENSE", "登字第256644號")


# ──────────────────────────────────────────────
# Gemini Vision 辨識
# ──────────────────────────────────────────────
EXTRACT_PROMPT = """你是不動產專業辨識助手。請仔細閱讀這些不動產相關文件圖片（可能包含土地謄本、建物謄本、委託書、地籍圖等），
從中抽取以下欄位的資料。若某欄位在圖片中找不到，請回傳空字串 ""。

請以 JSON 格式回傳，不要有任何多餘說明文字，只輸出純 JSON：

{
  "case_name": "案件名稱/委託標的（例如：台東市中山路房屋）",
  "contract_no": "合約/委託編號",
  "fill_date": "填表日期（YYYY/MM/DD 格式）",
  "owner_name": "所有權人姓名",
  "owner_id": "所有權人身分證字號",
  "owner_phone": "所有權人聯絡電話",
  "owner_address": "通訊住址",
  "contact_name": "連絡人姓名",
  "contact_relation": "與所有權人關係",
  "contact_use": "用途（公寓/住家/別墅/店住/土地）",
  "contact_phone": "連絡人電話",
  "property_address": "物件地址（門牌地址）",
  "land_section": "土地地段（例如：台東市 某某段）",
  "land_number": "地號",
  "building_number": "建號",
  "facing": "座向（東/西/南/北/東南/東北/西南/西北）",
  "complete_year": "竣工年（民國年）",
  "complete_month": "竣工月",
  "complete_day": "竣工日",
  "layout_room": "房數",
  "layout_living": "廳數",
  "layout_bath": "衛數",
  "layout_balcony": "陽台數",
  "status": "現況（空屋/自用/租賃）",
  "transaction_status": "交屋情況（立即/商談）",
  "area_land": "土地坪數",
  "area_main": "主建物坪數",
  "area_attached": "附屬建物坪數",
  "area_public": "公共設施坪數",
  "area_increase": "增建坪數",
  "area_total": "合計坪數",
  "floor_total": "總樓層",
  "floor_current": "所在樓層",
  "land_ownership": "土地所有權型態（單獨所有/分別共有/公同共有/其他）",
  "land_share": "土地持分（全部/持分比例）",
  "building_ownership": "建物所有權型態",
  "building_share": "建物持分",
  "has_restriction": "是否有限制處分（是/否）",
  "restriction_type": "限制類型（查封/假扣押/假處分/預告登記）",
  "land_match": "土地面積是否與土地標示吻合（是/否）",
  "building_match": "建物面積是否與建物標示吻合（是/否）",
  "floor_type": "樓層別",
  "commission_start": "委託起日（YYYY/MM/DD）",
  "commission_end": "委託迄日（YYYY/MM/DD）",
  "service_fee": "服務費率（例如：4%）",
  "commission_price": "委託價",
  "selling_price": "售價",
  "loan_info": "現金貸款及銀行",
  "selling_reason": "售屋原因",
  "property_type": "物件種類（住宅/套房/別墅/店面/廠房/辦公/車位/土地）",
  "guard": "警衛管理（無/有）",
  "garden": "中庭花園（無/有）",
  "elevator": "電梯（無/有）",
  "management_fee": "管理費（元/月）",
  "parking": "車位（無/有）",
  "exterior": "外牆外飾（二丁掛/方塊磚/馬賽克/洗石子/玻璃帷幕/其他）",
  "floor_material": "地板（木板/磁石子/大理石/磁磚/塑膠地板/其他）",
  "water": "自來水（已安裝/未安裝）",
  "electricity": "電力系統（已安裝/未安裝）",
  "phone_line": "電話系統（已安裝/未安裝）",
  "gas": "天然瓦斯（已安裝/未安裝）",
  "other_notes": "其他補充說明",
  "nearby_facilities": "附近設施說明",
  "fixed_items": "固定物說明",
  "case_features": "個案特色說明",
  "attachments": {
    "land_certificate": "土地權狀影本（有/無）",
    "building_certificate": "建物權狀影本（有/無）",
    "land_registry": "土地謄本（有/無）",
    "building_registry": "建物謄本（有/無）",
    "cadastral_map": "地籍圖（有/無）",
    "aerial_photo": "空照圖（有/無）",
    "measurement": "建物測量成果圖（有/無）"
  },
  "land_rights": [
    {
      "type": "他項權利種類（例如：抵押權）",
      "rank": "順位",
      "register_date": "登記日期",
      "attribute": "屬性",
      "amount": "設定金額（萬元）",
      "holder": "設定權利人"
    }
  ],
  "building_rights": [
    {
      "type": "他項權利種類",
      "rank": "順位",
      "register_date": "登記日期",
      "attribute": "屬性",
      "amount": "設定金額（萬元）",
      "holder": "設定權利人"
    }
  ]
}
"""

def gemini_extract(images_b64: list) -> dict:
    """
    呼叫 Gemini Vision API，從多張圖片中辨識不動產欄位。
    images_b64: list of {"mime_type": "image/jpeg", "data": "<base64>"}
    回傳: dict 欄位資料
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未設定")

    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")

    # 組合 content：先放 prompt，再放所有圖片
    parts = [EXTRACT_PROMPT]
    for img in images_b64:
        parts.append({
            "mime_type": img["mime_type"],
            "data": img["data"]
        })

    response = model.generate_content(parts)
    text = response.text.strip()

    # 清理 markdown code block 包裝（Gemini 有時會加上 ```json ... ```）
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return json.loads(text)


# ──────────────────────────────────────────────
# 路由
# ──────────────────────────────────────────────

@app.route("/")
@require_login
def index():
    """主頁面（回傳 index.html）"""
    return send_from_directory("static", "index.html")




@app.route("/auth/portal-login")
def portal_login():
    """
    接收 Portal 傳來的簽名 token，驗證後建立 session。
    Portal 端用 FLASK_SECRET_KEY 簽名 {"email": "...", "ts": ...}
    """
    token = request.args.get("token", "")
    if not token:
        return "缺少 token", 400
    try:
        s = URLSafeTimedSerializer(app.secret_key)
        data = s.loads(token, max_age=300, salt="portal-sso")  # 需與 Portal 的 salt 一致
        session["user_email"] = data.get("email", "")
        session["user_name"] = data.get("name", "")
        logger.info("Portal 登入成功: %s", session["user_email"])
        return redirect("/")
    except SignatureExpired:
        return "登入連結已過期，請返回入口重新登入", 403
    except BadSignature:
        return "無效的登入憑證", 403


@app.route("/api/config")
def api_config():
    """回傳前端設定"""
    return jsonify({
        "company_name": COMPANY_NAME,
        "company_address": COMPANY_ADDRESS,
        "company_phone": COMPANY_PHONE,
        "agent_name": AGENT_NAME,
        "agent_license": AGENT_LICENSE,
        "portal_url": PORTAL_URL,
    })


@app.route("/api/detect-fields", methods=["POST"])
@require_login
def api_detect_fields():
    """
    智慧辨識：上傳一張文件圖片
    → Gemini 自動找出所有欄位的位置（bbox 相對座標）+ 辨識值
    → 回傳 [{field_id, field_label, value, bbox:[x,y,w,h]}]
    bbox 為 0~1 的相對比例座標（左上角 x,y + 寬w + 高h）
    """
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "請上傳圖片"}), 400

    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY 未設定"}), 500

    # ── 第一階段：先判斷文件類型 ──
    step1_prompt = """這是一張台灣不動產相關文件的圖片。
請判斷這是哪種文件，只回傳以下其中一個值（純文字，不加任何說明）：
土地謄本
建物謄本
委託書
地籍圖
其他"""

    # 各文件類型對應的欄位清單
    FIELD_MAP = {
        "土地謄本": [
            {"field_id": "land_section",  "field_label": "地段（鄉鎮市區＋段名）"},
            {"field_id": "land_number",   "field_label": "地號"},
            {"field_id": "land_sqm",      "field_label": "登記面積（平方公尺）"},
            {"field_id": "area_land",     "field_label": "登記面積（坪）"},
            {"field_id": "land_share",    "field_label": "權利範圍（持分）"},
            {"field_id": "land_ownership","field_label": "所有權人姓名"},
            {"field_id": "owner_id",      "field_label": "所有權人身分證字號"},
            {"field_id": "owner_address", "field_label": "所有權人住址"},
            {"field_id": "complete_date", "field_label": "登記日期（民國年月日，例：81年8月24日）"},
        ],
        "建物謄本": [
            {"field_id": "building_number",  "field_label": "建號"},
            {"field_id": "property_address", "field_label": "建物門牌地址"},
            {"field_id": "floor_type",       "field_label": "樓層別"},
            {"field_id": "floor_total",      "field_label": "總樓層數"},
            {"field_id": "area_main",        "field_label": "主建物面積（平方公尺）"},
            {"field_id": "area_attached",    "field_label": "附屬建物面積（平方公尺）"},
            {"field_id": "area_public",      "field_label": "共有部分面積（平方公尺）"},
            {"field_id": "area_total",       "field_label": "合計面積（坪）"},
            {"field_id": "building_share",   "field_label": "建物權利範圍（持分）"},
            {"field_id": "owner_name",       "field_label": "所有權人姓名"},
            {"field_id": "owner_id",         "field_label": "所有權人身分證字號"},
            {"field_id": "complete_date",    "field_label": "建築完成日期（民國年月日，例：81年8月24日）"},
            {"field_id": "land_section",     "field_label": "基地坐落地段"},
            {"field_id": "land_number",      "field_label": "基地地號"},
        ],
        "委託書": [
            {"field_id": "case_name",         "field_label": "案件名稱／委託標的"},
            {"field_id": "contract_no",       "field_label": "合約／委託編號"},
            {"field_id": "owner_name",        "field_label": "委託人姓名"},
            {"field_id": "owner_id",          "field_label": "委託人身分證字號"},
            {"field_id": "owner_phone",       "field_label": "委託人電話"},
            {"field_id": "owner_address",     "field_label": "委託人住址"},
            {"field_id": "property_address",  "field_label": "物件地址"},
            {"field_id": "selling_price",     "field_label": "售價"},
            {"field_id": "commission_price",  "field_label": "委託價"},
            {"field_id": "service_fee",       "field_label": "服務費率"},
            {"field_id": "commission_start",  "field_label": "委託起日"},
            {"field_id": "commission_end",    "field_label": "委託迄日"},
            {"field_id": "layout_room",       "field_label": "房數"},
            {"field_id": "layout_living",     "field_label": "廳數"},
            {"field_id": "layout_bath",       "field_label": "衛數"},
            {"field_id": "case_features",     "field_label": "個案特色說明"},
        ],
    }

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        mime = file.content_type or "image/jpeg"
        img_data = base64.b64encode(file.read()).decode("utf-8")
        img_part = {"mime_type": mime, "data": img_data}

        # 第一階段：判斷文件類型
        r1 = model.generate_content([step1_prompt, img_part])
        doc_type = r1.text.strip().replace("```", "").strip()
        logger.info("文件類型判斷結果: %s", doc_type)

        # 取得對應欄位清單（找不到就用全部欄位）
        target_fields = FIELD_MAP.get(doc_type, [
            f for fields in FIELD_MAP.values() for f in fields
        ])

        # ── 第二階段：只針對這類文件的欄位辨識位置 ──
        fields_json = json.dumps(
            [{"field_id": f["field_id"], "field_label": f["field_label"]} for f in target_fields],
            ensure_ascii=False, indent=2
        )
        step2_prompt = f"""你是台灣不動產文件辨識專家。這是一張【{doc_type}】。

請在圖片中找出以下欄位的位置（bbox）和內容（value）。

重要規則：
1. bbox 是該欄位「值的內容」所在的矩形框，用圖片寬高的相對比例：[左上x, 左上y, 寬度, 高度]，值域 0.0~1.0
2. 【嚴禁】框到欄位標題文字，只框「值」的區域
3. 若此文件中確實沒有該欄位，bbox 設為 null，value 設為 ""
4. 【嚴禁】猜測或捏造不存在的欄位值
5. 只回傳純 JSON，不加 markdown 包裝

要辨識的欄位清單：
{fields_json}

回傳格式：
{{
  "fields": [
    {{"field_id": "欄位id", "field_label": "欄位名稱", "value": "辨識到的值", "bbox": [x, y, w, h]}},
    ...
  ]
}}"""

        r2 = model.generate_content([step2_prompt, img_part])
        text = r2.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        result = json.loads(text)

        # 過濾掉找不到的欄位（bbox 為 null 或 value 為空）
        fields = [
            f for f in result.get("fields", [])
            if f.get("bbox") and str(f.get("value", "")).strip()
        ]
        logger.info("智慧辨識完成，文件類型: %s，找到 %d 個欄位", doc_type, len(fields))
        return jsonify({
            "ok": True,
            "doc_type": doc_type,
            "fields": fields
        })

    except json.JSONDecodeError as e:
        logger.error("Gemini 回傳格式異常: %s | 原文: %s", e, text[:200])
        return jsonify({"error": "AI 回傳格式異常，請重試"}), 500
    except Exception as e:
        logger.error("智慧辨識失敗: %s", e)
        return jsonify({"error": f"辨識失敗：{str(e)}"}), 500


@app.route("/api/extract-region", methods=["POST"])
@require_login
def api_extract_region():
    """
    精準框選辨識：接收單張裁切後的區域圖片 + 欄位提示
    → 呼叫 Gemini Vision 辨識該欄位的值
    → 回傳 {"ok": true, "value": "辨識結果"}
    """
    file = request.files.get("images[]")
    if not file:
        return jsonify({"error": "請上傳裁切區域圖片"}), 400

    field_hint = request.form.get("field_hint", "")   # 欄位 id（例如 "land_number"）
    field_label = request.form.get("field_label", "")  # 欄位中文名稱（例如 "地號"）

    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY 未設定"}), 500

    # 建立精準 prompt：只要求回傳這個欄位的純文字值
    prompt = f"""你是不動產文件辨識專家。
這張圖片是從謄本/委託書中框選出來的某個特定區域。
請辨識這個區域中「{field_label}」的文字內容。

要求：
1. 只回傳純文字值，不要任何解釋
2. 如果是數字，直接回傳數字（例如：907.5）
3. 如果是日期，用 YYYY/MM/DD 格式
4. 如果是年份（民國年），直接回傳數字（例如：81）
5. 如果看不清楚或找不到，回傳空字串
6. 不要加單位（坪、元、%等），除非特別要求

欄位名稱：{field_label}
請回傳這個欄位的值："""

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        mime = file.content_type or "image/jpeg"
        data = base64.b64encode(file.read()).decode("utf-8")

        response = model.generate_content([
            prompt,
            {"mime_type": mime, "data": data}
        ])
        value = response.text.strip().strip('"').strip("'")
        logger.info("精準框選辨識成功 field=%s value=%s", field_hint, value[:30] if value else "")
        return jsonify({"ok": True, "value": value})

    except Exception as e:
        logger.error("精準框選辨識失敗: %s", e)
        return jsonify({"error": f"辨識失敗：{str(e)}"}), 500


@app.route("/api/extract", methods=["POST"])
@require_login
def api_extract():
    """
    接收多張圖片（multipart/form-data，欄位名 images[]）
    → 呼叫 Gemini Vision 辨識
    → 回傳欄位 JSON
    """
    files = request.files.getlist("images[]")
    if not files:
        return jsonify({"error": "請上傳至少一張圖片"}), 400

    # 將圖片轉為 base64
    images_b64 = []
    for f in files:
        mime = f.content_type or "image/jpeg"
        data = base64.b64encode(f.read()).decode("utf-8")
        images_b64.append({"mime_type": mime, "data": data})

    try:
        result = gemini_extract(images_b64)
        logger.info("Gemini 辨識成功，辨識圖片數: %d", len(files))
        return jsonify({"ok": True, "fields": result})
    except json.JSONDecodeError as e:
        logger.error("Gemini 回傳格式不是合法 JSON: %s", e)
        return jsonify({"error": "AI 辨識結果格式異常，請重試"}), 500
    except Exception as e:
        logger.error("Gemini 辨識失敗: %s", e)
        return jsonify({"error": f"辨識失敗：{str(e)}"}), 500


@app.route("/api/save", methods=["POST"])
@require_login
def api_save():
    """
    儲存草稿。
    Body JSON：{"id": "<draft_id 可省略，省略則新建>", "title": "案件名", ...其他欄位}
    回傳：{"ok": true, "id": "<draft_id>"}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "請傳送 JSON 資料"}), 400

    draft_id = data.get("id") or str(uuid.uuid4())[:8]
    title = data.get("title") or data.get("case_name") or "未命名"
    data["id"] = draft_id
    data["title"] = title

    try:
        save_draft(draft_id, data)
        return jsonify({"ok": True, "id": draft_id})
    except Exception as e:
        logger.error("儲存草稿失敗: %s", e)
        return jsonify({"error": f"儲存失敗：{str(e)}"}), 500


@app.route("/api/drafts")
@require_login
def api_list_drafts():
    """列出所有草稿（id, title, updated_at）"""
    return jsonify(list_drafts())


@app.route("/api/drafts/<draft_id>")
@require_login
def api_get_draft(draft_id):
    """取得單筆草稿完整資料"""
    data = load_draft(draft_id)
    if data is None:
        return jsonify({"error": "找不到此草稿"}), 404
    return jsonify(data)


@app.route("/api/drafts/<draft_id>", methods=["DELETE"])
@require_login
def api_delete_draft(draft_id):
    """刪除草稿"""
    try:
        from utils import delete_draft
        delete_draft(draft_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/view/<draft_id>")
@require_login
def view_draft(draft_id):
    """載入指定草稿的互動頁面（帶 ?draft_id= 參數）"""
    return redirect(f"/?draft_id={draft_id}")


# ──────────────────────────────────────────────
# 封面設計設定 GET/POST
# ──────────────────────────────────────────────
_COVER_CONFIG_PATH = os.path.join(_APP_DIR, "cover_config.json")
_COVER_CONFIG_GCS_KEY = "cover_config.json"

# 預設值
_DEFAULT_COVER_CONFIG = {
    # 標題
    "title_height": 28, "title_margin_top": 4, "title_margin_bottom": 6, "title_align": "center",
    # 印章
    "stamp_height": 10, "stamp_align": "center",
    # LOGO
    "logo_width": 80, "logo_margin_top": 6, "logo_align": "center",
    # 表格
    "border_width": 1.5, "border_color": "#000000", "th_bg": "#e8e8e8",
    "table_row_height": 20, "col_content_width": 40, "content_row_height": 25,
    "table_margin_top": 6,
    # 字體
    "font_family": "Arial,微軟正黑體,sans-serif",
    "font_size_label": 12, "font_size_value": 14, "font_size_th": 11,
    "label_color": "#000000", "accent_color": "#cc0000",
    # 間距
    "page_padding": 10, "field_row_gap": 4, "sign_table_margin_top": 6,
}

def _load_cover_config():
    """讀取封面設定（優先 GCS，其次本地）"""
    if GCS_BUCKET:
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(GCS_BUCKET)
            blob = bucket.blob(_COVER_CONFIG_GCS_KEY)
            if blob.exists():
                return json.loads(blob.download_as_text())
        except Exception as e:
            logger.warning("GCS 讀取 cover_config 失敗: %s", e)
    if os.path.isfile(_COVER_CONFIG_PATH):
        with open(_COVER_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(_DEFAULT_COVER_CONFIG)

def _save_cover_config(cfg: dict):
    """儲存封面設定（優先 GCS，其次本地）"""
    if GCS_BUCKET:
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(GCS_BUCKET)
            blob = bucket.blob(_COVER_CONFIG_GCS_KEY)
            blob.upload_from_string(json.dumps(cfg, ensure_ascii=False), content_type="application/json")
            return
        except Exception as e:
            logger.warning("GCS 儲存 cover_config 失敗: %s", e)
    with open(_COVER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

@app.route("/api/cover-config", methods=["GET"])
def api_get_cover_config():
    """取得封面設計設定"""
    cfg = _load_cover_config()
    # 補齊預設值（舊資料可能缺欄位）
    for k, v in _DEFAULT_COVER_CONFIG.items():
        cfg.setdefault(k, v)
    return jsonify(cfg)

@app.route("/api/cover-config", methods=["POST"])
@require_login
def api_save_cover_config():
    """儲存封面設計設定"""
    data = request.get_json(force=True)
    cfg = {}
    for k, default in _DEFAULT_COVER_CONFIG.items():
        raw = data.get(k, default)
        try:
            if isinstance(default, float):
                cfg[k] = float(raw)
            elif isinstance(default, int):
                cfg[k] = int(float(raw))
            else:
                cfg[k] = str(raw)
        except (ValueError, TypeError):
            cfg[k] = default
    _save_cover_config(cfg)
    return jsonify({"ok": True, "config": cfg})


# ──────────────────────────────────────────────
# 註冊 Blueprint（編輯器）
# ──────────────────────────────────────────────
try:
    from blueprints.editor_bp import editor_bp
    app.register_blueprint(editor_bp)
    logger.info("編輯器 Blueprint 已掛載")
except ImportError:
    logger.warning("編輯器 Blueprint 未找到（暫未實作）")
except Exception as e:
    logger.warning("編輯器 Blueprint 掛載失敗: %s", e)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    debug = bool(os.environ.get("FLASK_DEBUG"))
    logger.info("不動產說明書工具啟動 port=%d debug=%s", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
