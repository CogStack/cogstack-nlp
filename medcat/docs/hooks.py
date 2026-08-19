import re


def on_page_content(html, page, config, files):
    if page.file.src_uri == "index.md":
        # Rewrites <a href="docs/whatever.md"> (or <a href="docs/whatever/">) to <a href="whatever/">
        # Handles .md extensions or already-rendered clean URLs
        html = re.sub(r'href="docs/([^"#\?]+)\.md([#\?][^"]*)?"', r'href="../\1/\2"', html)
        html = re.sub(r'href="docs/([^"#\?]+)/([#\?][^"]*)?"', r'href="../\1/\2"', html)
    return html
