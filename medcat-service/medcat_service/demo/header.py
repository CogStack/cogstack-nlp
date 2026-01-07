from medcat_service.demo.brand_logo import logo as brand_logo_base64

# Use the base64-encoded logo from brand_logo module
_logo_base64 = f"data:image/png;base64,{brand_logo_base64}"

# CSS styles for the header
_header_css = """
<style>
/* Override Gradio container constraints for header */
.header {
    font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
    color: #000;
    line-height: 1.6;
    box-sizing: border-box;
    border-bottom: 1px solid #c8b9b9;
    padding: 1rem 0;
    position: sticky;
    top: 0;
    z-index: 100;
    background: linear-gradient(135deg, #126cad, #3d0372, #8e1b73);
    width: 100vw !important;
    margin-left: calc(-50vw + 50%) !important;
    margin-right: calc(-50vw + 50%) !important;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    overflow: hidden !important;
    overflow-x: hidden !important;
    overflow-y: hidden !important;
}

/* Break out of Gradio's container - target parent elements */
.fillable:has(.header),
.app:has(.header),
.svelte-1v1ee78:has(.header) {
    max-width: none !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
    width: 100% !important;
}

/* Target Gradio's main container that wraps the HTML component */
main:has(.header),
.gradio-container:has(.header) {
    padding-left: 0 !important;
    padding-right: 0 !important;
}

/* Ensure header breaks out of any parent container */
header.header {
    position: relative;
    display: block;
}

header.header * {
    box-sizing: border-box;
}

.header-gradient {
    background: linear-gradient(135deg, #126cad, #3d0372, #8e1b73);
}

.nav {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    padding: 0 24px;
}

.logo-section {
    display: flex;
    align-items: center;
    gap: 16px;
}

.brand-logo {
    height: 48px !important;
    width: auto;
}

.divider {
    height: 24px;
    width: 1px;
    background-color: rgba(255, 255, 255, 0.3);
}

.app-title {
    font-size: 24px;
    font-weight: bold;
    color: white !important;
    margin: 0 !important;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
</style>
"""

# Logo image tag
_logo_img = f'<img src="{_logo_base64}" alt="Brand Logo" class="brand-logo">'

# Header HTML structure
_header_html = (
    """
<header class="header header-gradient">
    <nav class="nav">
        <div class="logo-section">
"""
    + _logo_img
    + """
            <div class="divider"></div>
            <h1 class="app-title">MedCAT Demo</h1>
        </div>
    </nav>
</header>
"""
)

custom_header_html = _header_css + _header_html
