import re

index_file = '/Users/chenweiliang/Projects/real-estate-doc/static/index.html'

with open(index_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace between:
# // ── 渲染列印版面 ──
# function renderPrintArea(f) {
# ...
# }
# // 勾選框輔助：產生帶有 ■/□ 的選項文字

start_marker = "// ── 渲染列印版面 ──\nfunction renderPrintArea(f) {"
end_marker = "// 勾選框輔助：產生帶有 ■/□ 的選項文字"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    new_func = """// ── 渲染列印版面 ──
function renderPrintArea(f) {
  const printArea = document.getElementById('print-area');
  printArea.innerHTML = ''; // 清除舊版面

  const isLand = f.property_type === '土地';
  const tplId = isLand ? 'template-land' : 'template-building';
  const tpl = document.getElementById(tplId);
  if (!tpl) {
    console.error('Template not found:', tplId);
    return;
  }

  const clone = tpl.cloneNode(true);
  clone.style.display = 'block';
  clone.id = 'print-content';
  
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

  printArea.appendChild(clone);
}

"""
    content = content[:start_idx] + new_func + content[end_idx:]
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced renderPrintArea successfully")
else:
    print("Could not find markers!")
