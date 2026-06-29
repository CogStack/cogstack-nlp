from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles

from medcat_service.config import Settings

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


def configure_docs(app: FastAPI, settings: Settings) -> None:
    """
    Support self-hosting javascript and css for docs instead of using the CDN.

    This allows the docs page to work offline or in an air-gapped environment.

    https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/#self-hosting-javascript-and-css-for-docs

    If the flag is true, then it should just have the default FastAPI behaviour.
    """
    if settings.use_cdn_for_docs:
        return

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        root_path = app.root_path.rstrip("/")
        oauth2_redirect_url = app.swagger_ui_oauth2_redirect_url
        if oauth2_redirect_url:
            oauth2_redirect_url = root_path + oauth2_redirect_url
        return get_swagger_ui_html(
            openapi_url=root_path + app.openapi_url,
            title=app.title + " - Swagger UI",
            oauth2_redirect_url=oauth2_redirect_url,
            swagger_js_url=f"{root_path}/static/swagger-ui-bundle.js",
            swagger_css_url=f"{root_path}/static/swagger-ui.css",
        )

    if app.swagger_ui_oauth2_redirect_url:

        @app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
        async def swagger_ui_redirect():
            return get_swagger_ui_oauth2_redirect_html()

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        root_path = app.root_path.rstrip("/")
        return get_redoc_html(
            openapi_url=root_path + app.openapi_url,
            title=app.title + " - ReDoc",
            redoc_js_url=f"{root_path}/static/redoc.standalone.js",
        )
