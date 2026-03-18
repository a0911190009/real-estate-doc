import os
import re

index_file = '/Users/chenweiliang/Projects/real-estate-doc/static/index.html'

with open(index_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Instead of complex DOM parsing, we'll replace the exact known text with spans that have classes.
# We will do this carefully.
replacements = [
    ('>莊武松<', '><span class="tpl-owner-name"></span><'),
    ('>台東市豐年路一段271號<', '><span class="tpl-property-address"></span><'),
    ('>台東縣<', '><span class="tpl-city"></span><'),
    ('>台東市<', '><span class="tpl-district"></span><'),
    ('>順天段<', '><span class="tpl-land-section"></span><'),
    ('>54<', '><span class="tpl-land-number"></span><'),
    ('>3980<', '><span class="tpl-selling-price"></span><'),
    ('>160.1㎡<', '><span class="tpl-area-main-m"></span><'),
    ('>約48.43坪<', '><span class="tpl-area-main-p"></span><'),
    ('>2500.43㎡<', '><span class="tpl-area-land-m"></span><'),
    ('>4房<', '><span class="tpl-layout-room"></span>房<'),
    ('>2廳<', '><span class="tpl-layout-living"></span>廳<'),
    ('>2衛<', '><span class="tpl-layout-bath"></span>衛<'),
    ('>82<', '><span class="tpl-complete-year"></span><'),
    ('>10<', '><span class="tpl-complete-month"></span><'),
    ('>19<', '><span class="tpl-complete-day"></span><'),
    ('>鋼筋混凝土造<', '><span class="tpl-material"></span><')
]

for old, new in replacements:
    content = content.replace(old, new)

with open(index_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated formatting classes in index.html")
