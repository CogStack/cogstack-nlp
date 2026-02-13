# Medical <img src="_static/img/cat-logo.png" width=45>oncept Annotation Tool Trainer

MedCATtrainer is a web application for creating, validating, and improving
MedCAT concept annotation models on biomedical or clinical text.

It supports both classic active-learning workflows (train on submit) and
review-only workflows (collect annotations without changing the model).

## What you can do with MedCATtrainer

- Build annotation projects from CSV/XLSX datasets.
- Use either:
  - a **Model Pack** (recommended), or
  - a **Concept DB + Vocabulary** pair.
- Optionally use a **remote MedCAT model service** for document preparation.
- Collect concept-level labels:
  - Correct
  - Incorrect
  - Alternative concept
  - Terminate
  - Irrelevant
- Collect optional **meta annotations** and **relation annotations**.
- Use **Project Groups** for multi-annotator setups.
- Run **metrics reports** across one or more compatible projects.
- Explore concept hierarchies and export concept filters.

## Typical workflow

1. Install and configure MedCATtrainer.
2. Create users and upload model artifacts (Model Pack or CDB/Vocab).
3. Create a project and assign annotators.
4. Annotate and submit documents.
5. Export annotations and evaluate with the metrics tools.

## Documentation map

- [Installation](installation.md)
- [Administrator Setup](admin_setup.md)
- [Annotation Project Creation and Management](project_admin.md)
- [Project Groups](project_group_admin.md)
- [Annotator Guide](annotator_guide.md)
- [Meta Annotations](meta_annotations.md)
- [Demo / Try Model](demo_page.md)
- [Advanced Usage](advanced_usage.md)
- [Maintenance](maintenance.md)
- [Python Client](client.md)

