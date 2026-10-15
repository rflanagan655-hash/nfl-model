"""Wrap the published Artifact page (no doctype/head) into a standalone index.html.

Usage: python3 tools/build_site.py <artifact_page.html> [index.html]
"""
import re, subprocess, sys, tempfile

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "index.html"
s = open(src, encoding="utf-8").read()

# A page saved from an artifact read may already be a full document; keep only the body content then.
m = re.search(r"<body[^>]*>(.*)</body>", s, re.S | re.I)
if m and "<title>" in m.group(1):
    s = m.group(1)

i = s.index("</style>") + len("</style>")
head, body = s[:i], s[i:]
doc = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);'
    'padding-bottom:env(safe-area-inset-bottom,0px)}'
    'body{margin:0;font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}'
    'img{max-width:100%}[hidden]{display:none!important}</style>\n'
    + head + "\n</head><body>" + body + "\n</body></html>\n"
)

# Syntax-check the page script before writing.
js = re.search(r"<script>(.*)</script>", doc, re.S).group(1)
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
    f.write(js)
subprocess.run(["node", "--check", f.name], check=True)

open(out, "w", encoding="utf-8").write(doc)
print(f"wrote {out} ({len(doc):,} bytes)")
