import re

def on_page_markdown(markdown, page, config, files):
    # Only rewrite relative links on the home/index page where README is embedded
    if page.file.src_uri == "index.md":
        # Rewrites [text](docs/page.md) -> [text](page.md)
        return re.sub(r'\]\(docs/([^\)]+\.md)\)', r'](\1)', markdown)
    return markdown

