import os
import re

land_file = '/Users/chenweiliang/Downloads/「案名」 近娜路彎酒店農舍（莊武松｜台東市豐年路一段271號）/土地不動產說明書.html'
building_file = '/Users/chenweiliang/Downloads/「案名」 近娜路彎酒店農舍（莊武松｜台東市豐年路一段271號）/成屋不動產說明書.html'
index_file = '/Users/chenweiliang/Projects/real-estate-doc/static/index.html'

def extract_style_and_html(file_path, prefix):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    style_match = re.search(r'<style type="text/css">(.*?)</style>', content, re.DOTALL)
    style = style_match.group(1) if style_match else ''
    style = style.replace('.ritz', f'.{prefix}')

    # Find the main div container
    div_start = content.find('<div class="ritz grid-container" dir="ltr">')
    if div_start == -1:
        div_start = content.find('<div class="ritz grid-container"')
        
    # The div usually goes to the end, but we should drop any scripts at the end
    html_part = content[div_start:]
    script_idx = html_part.find('<script')
    if script_idx != -1:
        html_part = html_part[:script_idx]
        
    html_part = html_part.replace('class="ritz ', f'class="{prefix} ')
    return style, html_part

land_style, land_html = extract_style_and_html(land_file, 'ritz-land')
building_style, building_html = extract_style_and_html(building_file, 'ritz-building')

# Combine styles
combined_styles = f"""
<!-- Excel Print Styles -->
<style>
/* Land Styles */
{land_style}

/* Building Styles */
{building_style}

/* Print Specific Rules */
@media print {{
  @page {{ margin: 5mm; size: A4 portrait; }}
  body * {{ visibility: hidden; }}
  #print-area, #print-area * {{ visibility: visible; }}
  #print-area {{ position: absolute; left: 0; top: 0; width: 100%; }}
  
  .ritz-land, .ritz-building {{ width: 100%; page-break-inside: auto; }}
  .ritz-land tr, .ritz-building tr {{ page-break-inside: avoid; page-break-after: auto; }}
  .ritz-land thead, .ritz-building thead {{ display: table-header-group; }}
  .ritz-land tfoot, .ritz-building tfoot {{ display: table-footer-group; }}
}}
</style>
"""

templates_html = f"""
<!-- EXCEL TEMPLATES -->
<div id="template-land" style="display:none;">
{land_html}
</div>
<div id="template-building" style="display:none;">
{building_html}
</div>
"""

with open(index_file, 'r', encoding='utf-8') as f:
    index_content = f.read()

# Insert styles before </head>
if combined_styles not in index_content:
    index_content = index_content.replace('</head>', combined_styles + '\n</head>')

# Insert templates before #preview-toolbar
target_str = '<!-- ────────────────────────────────────────\n       列印預覽工具列'
if 'id="template-land"' not in index_content:
    index_content = index_content.replace(target_str, templates_html + '\n  ' + target_str)

# Save
with open(index_file, 'w', encoding='utf-8') as f:
    f.write(index_content)

print("Injected styles and templates into index.html")
