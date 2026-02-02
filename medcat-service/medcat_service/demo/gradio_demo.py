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
    with gr.Blocks(title="AnonCAT Demo", fill_width=True) as io:
        gr.Markdown("# AnonCAT Demo")
        with gr.Row():
            with gr.Column():
                input_text = gr.Textbox(
                    label="Input Text",
                    lines=3,
                    placeholder="Enter some text and click Deidentify..."
                )
                examples = gr.Examples(
                    examples=[demo_content.short_example,  demo_content.anoncat_example],
                    inputs=input_text,
                    example_labels=["Short Example",
                                    "Note with personally identifiable information"]

                )
                with gr.Row():
                    clear_btn = gr.Button("Clear", variant="secondary")
                    deid_btn = gr.Button("Deidentify", variant="primary")

            with gr.Column():
                highlighted = gr.HighlightedText(label="Processed Text", elem_id="highlighted-text-output")
                dataframe = gr.Dataframe(label="Annotations", headers=headers, interactive=False, max_chars=4)
        deid_btn.click(
            perform_named_entity_resolution,
            inputs=input_text,
            outputs=[highlighted, dataframe]
        )
        clear_btn.click(
            lambda: ("", None, None),
            outputs=[input_text, highlighted, dataframe]
        )
        gr.Markdown(demo_content.anoncat_help_content)
else:
    with gr.Blocks(title="MedCAT Demo", fill_width=True) as io:
        gr.Markdown("# MedCAT Demo")
        with gr.Row():
            with gr.Column():
                input_text = gr.Textbox(
                    label="Input Text",
                    lines=6,
                    placeholder="Enter some text and click Annotate..."
                )
                with gr.Row():
                    examples = gr.Examples(
                        examples=[demo_content.short_example, demo_content.long_example, demo_content.anoncat_example],
                        inputs=input_text,
                        example_labels=["Short Example",
                                        "Patient Discharge Summary in Neurology",
                                        "Note with personally identifiable information" ]
                    )
                with gr.Row():
                    clear_btn = gr.Button("Clear", variant="secondary")
                    annotate_btn = gr.Button("Annotate", variant="primary")
            with gr.Column():
                highlighted = gr.HighlightedText(
                    label="Processed Text", elem_id="highlighted-text-output")
                dataframe = gr.Dataframe(label="Annotations", headers=headers, interactive=False, max_chars=50)
        annotate_btn.click(
            perform_named_entity_resolution,
            inputs=input_text,
            outputs=[highlighted, dataframe]
        )
        clear_btn.click(
            lambda: ("", None, None),
            outputs=[input_text, highlighted, dataframe]
        )
        gr.Markdown(demo_content.article_footer)


def mount_gradio_app(app, path: str = "/demo") -> None:
    """
    Mount the Gradio interface to the FastAPI app with a custom theme.

    Args:
        app: The FastAPI application instance
        path: The path at which to mount the Gradio app (default: "/demo")
    """
    theme = gr.themes.Default(primary_hue="blue", secondary_hue="teal")
    gr.mount_gradio_app(app, io, path=path, theme=theme, css=highlighted_text_css)
