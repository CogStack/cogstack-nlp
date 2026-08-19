import re


def on_page_markdown(markdown, page, config, files):
    if page.file.src_uri == "index.md":
        snippet_pattern = r'--8<--\s*["\']README\.md["\']'
        if re.search(snippet_pattern, markdown):
            readme_path = Path(config["config_file_path"]).parent / "README.md"
            if readme_path.exists():
                readme_content = readme_path.read_text(encoding="utf-8")
                # Rewrite [text](docs/page.md) -> [text](page.md)
                # Also handles anchors like [text](docs/page.md#section) -> [text](page.md#section)
                rewritten = re.sub(r'\]\(docs/([^\)]+\.md(?:#[^\)]*)?)\)', r'](\1)', readme_content)
                markdown = re.sub(snippet_pattern, rewritten, markdown)
    return markdown
