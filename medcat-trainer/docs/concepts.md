# Concepts

The **Concepts** tab (`/model-explore`) lets you explore the concept hierarchy
of an available Concept Database (CDB) and build a concept filter for use in an
annotation project.

Use it when you need to understand which concepts a model can recognise, or when
you want a reusable CUI list that limits annotation to a clinical specialty or
subset of the ontology.

## What it is for

- browsing the parent/child hierarchy of a Concept Database
- searching for a specific concept and locating it in the tree
- selecting parent concepts and expanding them to include descendants
- excluding unwanted child concepts from a draft filter
- exporting a JSON CUI filter for Project Admin / Try Model

Concept filters restrict which Concept Unique Identifiers (CUIs) are in scope
for a project. On the Projects list, a filtered project shows its CUI count;
**All** means no filter is set.

## Prerequisites

- At least one Concept Database (or Model Pack that includes a CDB) must be
  uploaded in MedCATtrainer.
- Concept search in the left panel uses the Solr concept index. If type-ahead
  search returns nothing, import concepts for that CDB in Django Admin
  (`/admin` → **Concept Dbs** → **Import concepts**). See
  [Django Admin](django_admin.md#concept-lookup-index-solr-import).
- Hierarchy browsing depends on parent/child links in the CDB. Flat CDBs without
  hierarchy still support search and selecting individual concepts, but tree
  expansion may be limited.

## Layout

Open **Concepts** from the top navigation, or go to `/model-explore`.

| Area | Purpose |
|------|---------|
| **Left sidebar** | Choose a Concept Database, search for concepts, manage the selected filter, and export or clear it. |
| **Main viewport** | Interactive concept tree for the selected CDB. Click nodes to expand children; use the chevron on a node to add it to the filter. |

### Left sidebar controls

| Control | Description |
|---------|-------------|
| **Concept Database Models** | Dropdown of available CDBs. Changing the CDB reloads the tree. |
| **Concept search** | Type-ahead concept picker scoped to the selected CDB. Selecting a result focuses that concept in the tree (path to root). |
| **Selected Concepts** | Concepts added to the filter, with a running total of included CUIs (parents plus expanded children, minus exclusions). |
| **Child list** | Expand a selected parent with the chevron to see descendant concepts. Click a child to exclude or re-include it. |
| **Clear Filter** | Removes all selected concepts and exclusions. |
| **Export Filter** | Downloads a JSON file of the final CUI list (after exclusions). Disabled while empty or while export is in progress. |

### Tree viewport

- Nodes show `pretty name - CUI`.
- Click a node label to load its children.
- Use the node’s chevron button to add that concept to the filter.
- Zoom with **+** / **-**, or reset with **1:1**.

## Build a concept filter

1. Select a **Concept Database** from the dropdown.
2. Optionally search for a concept in the left picker to jump to its location in
   the tree.
3. Add one or more parent concepts:
    - from the tree (chevron on the node), or
    - by navigating the hierarchy until you find the right branch.
4. Each selected parent is expanded to include its child concepts. The
   **Selected Concepts** count updates automatically.
5. Review children under each selected parent. Click a child to exclude it from
   the filter (unchecked), or click again to include it.
6. Remove a parent from the filter with the **×** control next to its name.
7. Click **Export Filter** to download `filter.json`.

The export is a JSON array of CUI strings, for example:

```json
["91175000", "84757009", "386661006"]
```

Filters with more than about 10,000 concepts still export correctly, but the
sidebar may not render the full child list in the UI for very large expansions.

## Use the filter in a project

In **Project Admin** (`/project-admin`), open a project’s **Concept Filtering**
section and upload the exported file under **CUI File**.

You can also:

- paste a comma-separated CUI list
- pick individual concepts with the concept picker
- enable **Incl. Sub-concepts** so selected parents also include descendants
  at annotation / Try Model time

See [Annotation Project Creation and Management](project_admin.md#concept-filtering).

To try a filter without creating a project, use
[Try Model](demo_page.md) and apply the same CUI list or sub-concept option
there.

## Tips

- Prefer selecting a small number of high-level parents and excluding a few
  unwanted children, rather than picking hundreds of leaf concepts by hand.
- Keep exported filters versioned with the project (for example in source
  control) so the same CUI set can be reused or audited later.
- After changing the underlying CDB, re-import Solr concepts and regenerate
  filters if hierarchy or preferred names have changed.
- API endpoints used by this view are documented under
  [Advanced Usage](advanced_usage.md#concept-exploration-and-filter-export).
