# Meta Annotations

Meta annotations are extra labels attached to concept annotations, useful for
context-specific tasks such as temporality, experiencer, assertion, or
hypothetical mentions.

Examples:

- `Temporality`: Past / Present / Future
- `Experiencer`: Patient / Family / Other
- `Assertion`: Affirmed / Negated / Possible

## Configure meta tasks

Create and manage tasks in Django admin (`/admin`):

1. Create **Meta Task Values** (the allowed label options).
2. Create a **Meta Task**:
   - name
   - values
   - default value (optional)
   - description
   - ordering
3. Attach selected tasks to your project (`Project annotate entities`).

## Model-pack predictions vs manual labels

If your project uses a model pack that includes MetaCAT models:

- predicted meta labels may be shown in the annotation UI,
- annotators can validate or override predictions.

If no prediction is available, annotators can still assign labels manually.

## Annotator behavior

In the annotation screen, meta tasks appear in the sidebar for eligible concept
statuses (for example Correct/Alternative flows).

Task values can be toggled/updated and are stored as `MetaAnnotation` records.

## Reporting

Metrics reports include a **Meta Annotations** tab when meta annotation data is
present, including macro/micro performance summaries by task.
