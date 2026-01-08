import gradio as gr

import medcat_service.demo.demo_content as demo_content
from medcat_service.demo.demo_logic import perform_named_entity_resolution
from medcat_service.dependencies import get_settings

headers = ["Pretty Name", "Identifier", "Confidence Score", "Start Index", "End Index", "ID"]

# CSS to set max height with scrollbar for HighlightedText output
# Target the component container and its content
highlighted_text_css = """
#highlighted-text-output {
    max-height: 460px;
    overflow-y: auto;
}
"""
settings = get_settings()

if settings.deid_mode:
    io = gr.Interface(
        fn=perform_named_entity_resolution,
        inputs=gr.Textbox(label="Input Text", lines=3, placeholder="Enter some text and click Annotate..."),
        outputs=[
            gr.HighlightedText(label="Processed Text", elem_id="highlighted-text-output"),
            gr.Dataframe(label="Annotations", headers=headers, interactive=False),
        ],
        examples=[demo_content.short_example, demo_content.anoncat_example],
        title="AnonCAT Demo",
        flagging_mode="never",
        article=demo_content.anoncat_help_content,
        submit_btn="Deidentify",
    )
else:
    io = gr.Interface(
        fn=perform_named_entity_resolution,
        inputs=gr.Textbox(label="Input Text", lines=6, placeholder="Enter some text and click Annotate..."),
        outputs=[
            gr.HighlightedText(label="Processed Text", elem_id="highlighted-text-output"),
            gr.Dataframe(label="Annotations", headers=headers, interactive=False),
        ],
        examples=[demo_content.short_example, demo_content.long_example],
        title="MedCAT Demo",
        flagging_mode="never",
        article=demo_content.article_footer,
        submit_btn="Annotate",
    )


def mount_gradio_app(app, path: str = "/demo") -> None:
    """
    Mount the Gradio interface to the FastAPI app with a custom theme.

    Args:
        app: The FastAPI application instance
        path: The path at which to mount the Gradio app (default: "/demo")
    """
    theme = gr.themes.Default(primary_hue="blue", secondary_hue="teal")
    gr.mount_gradio_app(app, io, path=path, theme=theme, css=highlighted_text_css)
