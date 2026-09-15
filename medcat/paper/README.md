## MedCAT v2 paper

This folder involves scripts and workflows used to create the data for MedCAT v2 paper.
This will be presented within the BioNLP Workshop at ACL 2026.

The process was last run with MedCAT v2.7.0.

### Layout and usage

#### Folder structure

- `data`: the place for input data and scripts to manipulate the incoming data, each subfolder should have its own instructions
- `out`: the place for output data
- `scripts`: the scripts to generate the data

#### Reproducuing results

1. Fill in the paths for models in various scripts
  - In `scripts/performance/*.sh`
  - In `scripts/performance/*.sh`
  - In `scripts/speed/*.sh`
  - In `scripts/variance/*.sh`
2. Run the master script
  - `bash scripts/run_all_at_once.sh`

NOTE: You are unlikely to get identical results on different hardrware.
