# Annotation Interface

The annotator view is designed for fast review and correction of model
predictions.

![](_static/img/main-annotation-interface.png)

## 1) Document list

The left panel shows documents in the project dataset.

- Current document is highlighted.
- Prepared documents (model predictions generated) are marked.
- Submitted/validated documents are marked as complete.

## 2) Clinical text

The center panel displays document text with detected concept spans.

Select spans by clicking them directly, then apply one status from the task bar.

### Supported concept statuses

- **Correct**
- **Incorrect**
- **Terminate** (if enabled for project)
- **Alternative** (choose a different concept)
- **Irrelevant** (if enabled for project)

Only one status can be active per concept at a time.

### Adding missing annotations

If the model missed a mention:

1. Highlight text in the document.
2. Right-click and choose **Add Term**.
3. Search/select a concept in the concept picker.
4. Confirm to create the annotation.

Projects with `add_new_entities` enabled can also create brand-new concepts.

Overlapping annotations are supported.

## 3) Task bar and submission

The task bar contains status buttons and the **Submit** button.

- Submit is enabled only when required tasks are completed for all concepts.
- On submit, a confirmation dialog shows an annotation summary.
- If project `train_model_on_submit` is enabled, submitted annotations are used
  for incremental model updates (except remote model-service projects).

## 4) Header actions

Top-right actions:

- **Summary**: open document annotation summary.
- **Help**: keyboard shortcuts and project guidance.
- **Reset document**: re-prepare current document and clear document-level
  annotation state.

## 5) Right sidebar (concept details)

The sidebar shows details for the currently selected concept, including:

- concept name/CUI
- type IDs/semantic type (if available)
- synonyms and description
- confidence score

If enabled by project settings, a **Comment** field is also available.

## Meta annotations and relations

Depending on project configuration:

- **Meta Annotation Tasks** appear for relevant concept statuses.
- **Relation** tab appears to create/edit relations between annotated entities.

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Up / Down | Previous / next document |
| Left / Right (or Space) | Previous / next concept |
| `1` | Correct |
| `2` | Incorrect |
| `3` | Terminate (if enabled) |
| `4` | Alternative |
| `5` | Irrelevant (if enabled) |
| Enter | Submit / confirm submit |
| Esc | Close active modal/cancel active add-term flow |
