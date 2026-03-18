import re

index_file = '/Users/chenweiliang/Projects/real-estate-doc/static/index.html'

with open(index_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update renderPrintArea
start_marker = "// ── 渲染列印版面 ──"
# We need to find the function's end. It's right before "// 勾選框輔助"
end_marker = "// 勾選框輔助"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    new_func = """// ── 渲染列印版面 ──
function renderPrintArea(f) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || ''; };
  const setHtml = (id, val) => { const el = document.getElementById(id); if (el) el.innerHTML = val || ''; };
  const setSrc = (id, val) => { const el = document.getElementById(id); if (el) { el.src = val || ''; el.style.display = val ? 'block' : 'none'; } };

  // ─ 頁1：封面 ─
  set('pr-case-name', f.case_name);           // 案名（大字青色）
  set('pr-case-addr', f.property_address);    // 委託標的（物件地址）
  set('pr-contract-no', f.contract_no);

  // 附件清單
  const attMap = {
    land_certificate: '土地權狀影本',
    building_certificate: '建物權狀影本',
    land_registry: '土地謄本',
    building_registry: '建物謄本',
    cadastral_map: '地籍圖',
    aerial_photo: '空照圖',
    measurement: '建物測量成果圖'
  };
  const atts = f.attachments || {};
  setHtml('pr-attachments', Object.entries(attMap).map(([k,v]) =>
    `<div>${atts[k] === '有' ? '■' : '□'} ${v}</div>`
  ).join(''));

  // ==== 隱藏原本的預設表單版面 ====
  const pagesToHide = ['page-survey', 'page-rights', 'page-case', 'page-aerial'];
  pagesToHide.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
  });

  // ==== 清除之前插入的 Excel Template ====
  const oldExcel = document.getElementById('print-excel-content');
  if (oldExcel) oldExcel.remove();

  // ==== 插入 Excel Template ====
  const isLand = f.property_type === '土地';
  const tplId = isLand ? 'template-land' : 'template-building';
  const tpl = document.getElementById(tplId);
  if (tpl) {
    const clone = tpl.cloneNode(true);
    clone.style.display = 'block';
    clone.id = 'print-excel-content';
    
    // Set values based on span classes
    const setByClass = (cls, val) => {
      const els = clone.querySelectorAll('.' + cls);
      els.forEach(el => el.textContent = val || '');
    };

    setByClass('tpl-owner-name', f.owner_name);
    setByClass('tpl-property-address', f.property_address);
    setByClass('tpl-city', f.city);
    setByClass('tpl-district', f.district);
    setByClass('tpl-land-section', f.land_section);
    setByClass('tpl-land-number', f.land_number);
    setByClass('tpl-selling-price', f.selling_price);

    if (isLand) {
      setByClass('tpl-area-land-m', f.area_land ? f.area_land + '㎡' : '');
    } else {
      setByClass('tpl-area-main-m', f.area_main ? f.area_main + '㎡' : '');
      setByClass('tpl-area-main-p', f.area_main_p ? '約' + f.area_main_p + '坪' : '');
      setByClass('tpl-layout-room', f.layout_room || '');
      setByClass('tpl-layout-living', f.layout_living || '');
      setByClass('tpl-layout-bath', f.layout_bath || '');
      setByClass('tpl-complete-year', f.complete_year || '');
      setByClass('tpl-complete-month', f.complete_month || '');
      setByClass('tpl-complete-day', f.complete_day || '');
      setByClass('tpl-material', f.material || '');
    }

    // 將 Excel 區塊安插在 page-cover 之後
    const pageCover = document.getElementById('page-cover');
    if (pageCover) {
        pageCover.parentNode.insertBefore(clone, pageCover.nextSibling);
    } else {
        document.getElementById('print-area').appendChild(clone);
    }
  }

  // ==== 設定空照圖 (若有上傳則顯示) ====
  const aerialSrc = imgData.aerial || f.img_aerial || '';
  const aerialPage = document.getElementById('page-aerial');
  if (aerialPage) {
    if (aerialSrc) {
      setSrc('pr-aerial-img', aerialSrc);
      aerialPage.style.display = 'block';
    } else {
      aerialPage.style.display = 'none';
    }
  }
}

"""
    content = content[:start_idx] + new_func + content[end_idx:]
else:
    print("WARNING: renderPrintArea markers not found!")

# 2. Inject CSS string
css_injection = """
  /* 隱藏 A B C 欄號，但保留寬度設定 */
  .column-headers-background {
      color: transparent !important;
      border: none !important;
      background: transparent !important;
      height: 0 !important;
      padding-top: 0 !important; padding-bottom: 0 !important;
      line-height: 0 !important;
      overflow: hidden !important;
  }
  /* 隱藏 1 2 3 列號與左上角空白格子 */
  .row-headers-background, .row-header {
      display: none !important;
  }
"""

if "隱藏 A B C 欄號" not in content:
    # Find the end of style block or the end of Excel Print Styles
    style_idx = content.find('</style>')
    if style_idx != -1:
        content = content[:style_idx] + css_injection + content[style_idx:]
    else:
        print("WARNING: </style> not found")

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated index.html successfully.")
