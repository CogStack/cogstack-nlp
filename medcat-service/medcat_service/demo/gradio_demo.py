import gradio as gr
import pandas as pd
from fastapi import FastAPI

import medcat_service.demo.demo_content as demo_content
from medcat_service.demo.demo_logic import (
    anoncat_demo_perform_deidentification,
    medcat_demo_perform_named_entity_resolution,
)
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

annotation_details_placeholder_text = "Click on a highlighted entity to view its details"


def format_annotation_details(row: pd.Series | None, selected_text: str) -> str:
    """Format a pandas Series row as markdown for display."""
    if row is None:
        return "**No annotation selected**\n\nClick on a highlighted entity to view its details."

    pretty_name = row.get("Pretty Name", "N/A")
    identifier = row.get("Identifier", "N/A")
    confidence = row.get("Confidence Score", 0.0)
    start_idx = row.get("Start Index", -1)
    end_idx = row.get("End Index", -1)
    entity_id = row.get("ID", -1)

    confidence_pct = float(confidence) * 100

    details = f"""### Annotation Details
**Input Text:**         {selected_text}

**Entity Name:**        {pretty_name}

**Identifier (CUI):**   `{identifier}`

**Confidence Score:**   {confidence_pct:.2f}%

**Text Position:**      Start: `{start_idx}` → End: `{end_idx}`

**Entity ID:**          `{entity_id}`
"""
    return details


def on_select_annotation(value, annotation_details: str, dataframe: pd.DataFrame, evt: gr.SelectData) -> str:
    """
    On select of annotations in the highlighted text component.

    Important things to know: Adding the type gr.SelectData actually changes the data passed

    Then the index appears hacky. The highlighted text selected item has indices, but they are not the indices
    in the datatable. It looks like index 0 is always '', then it always inserts the text between annotations
    as another index. So we need to divide by 2 to get the correct index.
    """
    datatable_index = (evt.index - 1) // 2
    selected_text = evt.value[0]
    if dataframe is not None and datatable_index < len(dataframe):
        row = dataframe.iloc[datatable_index]
        return format_annotation_details(row, selected_text)
    else:
        return annotation_details_placeholder_text


def output_details_interface() -> tuple[gr.HighlightedText, gr.Markdown, gr.Dataframe]:
    """
    Output details interface for the demo.
    Based on gradio Namd-Entity Recognition Demo
    https://www.gradio.app/guides/named-entity-recognition
    """
    highlighted = gr.HighlightedText(label="Processed Text", elem_id="highlighted-text-output", interactive=False)
    annotation_details = gr.Markdown(label="Annotation Details", value=annotation_details_placeholder_text)
    with gr.Accordion(label="All Annotations", open=False):
        dataframe = gr.Dataframe(label="All Annotations", headers=headers, interactive=False, max_chars=50)

    highlighted.select(on_select_annotation, [highlighted, annotation_details, dataframe], outputs=annotation_details)
    return highlighted, annotation_details, dataframe


def anoncat_demo_interface() -> gr.Blocks:
    def input_column():
        with gr.Tab("Input"):
            with gr.Group():
                # Using a tab here just to make the input text box align with the output that is also tabbed
                input_text = gr.Textbox(
                    label="Input Text", lines=3, placeholder="Enter some text and click Deidentify..."
                )
                redact = gr.Checkbox(label="Redact", info="Replace sensitive information with ****")
            examples = gr.Examples(  # noqa
                examples=[demo_content.short_example, demo_content.anoncat_example],
                inputs=input_text,
                example_labels=["Short Example", "Note with personally identifiable information"],
            )
            with gr.Row():
                clear_btn = gr.Button("Clear", variant="secondary")
                annotate_btn = gr.Button("Deidentify", variant="primary")
        return input_text, redact, clear_btn, annotate_btn

    def output_column():
        with gr.Tab("Deidentification"):
            deidentified_text = gr.Textbox(label="Deidentified Text", value="", lines=3, interactive=False)
        with gr.Tab("Details"):
            highlighted, annotation_details, dataframe = output_details_interface()
        return highlighted, dataframe, deidentified_text, annotation_details

    with gr.Blocks(title="AnonCAT", fill_width=True) as io:
        gr.Markdown("# AnonCAT")
        with gr.Row():
            with gr.Column():  # noqa
                input_text, redact, clear_btn, annotate_btn = input_column()
            with gr.Column():
                highlighted, dataframe, deidentified_text, annotation_details = output_column()
        annotate_btn.click(
            anoncat_demo_perform_deidentification,
            inputs=[input_text, redact],
            outputs=[highlighted, dataframe, deidentified_text],
        )
        annotate_btn.click(lambda: (annotation_details_placeholder_text), outputs=[annotation_details])

        clear_btn.click(
            lambda: ("", None, None, annotation_details_placeholder_text),
            outputs=[input_text, highlighted, dataframe, annotation_details],
        )
        gr.Markdown(demo_content.anoncat_help_content)
    return io


def medcat_demo_interface() -> gr.Blocks:
    def input_column():
        input_text = gr.Textbox(label="Input Text", lines=6, placeholder="Enter some text and click Annotate...")
        with gr.Row():
            examples = gr.Examples(  # noqa
                examples=[demo_content.short_example, demo_content.long_example, demo_content.anoncat_example],
                inputs=input_text,
                example_labels=[
                    "Short Example",
                    "Patient Discharge Summary in Neurology",
                    "Note with personally identifiable information",
                ],
            )
        with gr.Row():
            clear_btn = gr.Button("Clear", variant="secondary")
            annotate_btn = gr.Button("Annotate", variant="primary")
        return input_text, clear_btn, annotate_btn

    with gr.Blocks(title="MedCAT", fill_width=True) as io:
        gr.Markdown("# MedCAT")
        with gr.Row():
            with gr.Column():
                input_text, clear_btn, annotate_btn = input_column()
            with gr.Column():
                highlighted, annotation_details, dataframe = output_details_interface()

        annotate_btn.click(lambda: (annotation_details_placeholder_text), outputs=[annotation_details])
        annotate_btn.click(
            medcat_demo_perform_named_entity_resolution, inputs=input_text, outputs=[highlighted, dataframe]
        )

        clear_btn.click(
            lambda: ("", None, None, annotation_details_placeholder_text),
            outputs=[input_text, highlighted, dataframe, annotation_details],
        )
        gr.Markdown(demo_content.article_footer)
    return io


def mount_gradio_app(app: FastAPI, path: str) -> None:
    """
    Mount the Gradio interface to the FastAPI app with a custom theme.

    Args:
        app: The FastAPI application instance
        path: The path at which to mount the Gradio app (default: "/demo")
    """
    theme = gr.themes.Default(primary_hue="blue", secondary_hue="teal")

    io = anoncat_demo_interface() if settings.deid_mode else medcat_demo_interface()

    gr.mount_gradio_app(app, io, path=path, theme=theme, css=highlighted_text_css)
