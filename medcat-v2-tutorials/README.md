# MedCAT Tutorials (version 2)

The MedCAT Tutorials provide an interactive learning path for using MedCAT.

*See the documentation on [index.md](notebooks/index.md) to get started with these tutorials.*

## Developer Readme
The following readmes are around the setup of the tutorials themselves aimed at a tutorial author.

### Documentation Build

The `medcat-v2` documentation site imports this project’s MkDocs navigation file directly. The relevant plugins are the mkdocs-monorepo-plugin and the mkdocs-jupyter pluign.

In `medcat-v2/mkdocs.yml` the `Tutorials` section is wired in via an include:

```yaml
nav:
  - Tutorials: '!include ../medcat-v2-tutorials/mkdocs.yml'
```

#### Run the docs locally (rendered site)

To preview the rendered docs site locally:

```bash
cd cogstack-nlp/medcat-v2-tutorials
uv run mkdocs serve
```
