import re

s = open("output/omni_readme.md", encoding="utf-8").read()
i = s.find("## Python API")
seg = re.sub(r"[^\x00-\x7f]", "?", s[i:i + 5600])
print(seg)
