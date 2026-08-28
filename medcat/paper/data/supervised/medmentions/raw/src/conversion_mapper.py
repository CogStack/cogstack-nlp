import os
import json
import pandas as pd
from medcat.model_creation.preprocess_umls import _DEFAULT_COLUMNS


def get_umls_df(umls_path: str) -> pd.DataFrame:
    mrconso = os.path.join(umls_path, "MRCONSO.RRF")
    df = pd.read_csv(mrconso, names=_DEFAULT_COLUMNS, sep="|", index_col=False)
    print("INIT", len(df.index))
    df = df[df["LAT"] == "ENG"]
    print("After LANG", len(df.index))
    df = df[df["SAB"].str.contains("SNOMEDCT")]
    print("After SNOMED", len(df.index))
    df = df[df["SCUI"].notna()]
    print("After non-none Snomed CUIs", len(df.index))
    return df


def load_cuis(needed_path: str) -> list[str]:
    with open(needed_path) as f:
        return [cui for line in f.readlines() if line for cui in line.split(",")]


def get_mappings(df: pd.DataFrame, umls_cuis: list[str],
                 status_order: list[str] = ['P', 'p', 'S', 's']) -> dict[str, str]:
    print("GM")
    custom_order = pd.CategoricalDtype(status_order, ordered=True)
    out_dict = {}
    for nr, cui in enumerate(umls_cuis):
        print(nr, cui)
        per_cui = df[df['CUI'] == cui]
        per_cui['TS'] = per_cui['TS'].astype(custom_order)
        per_cui = per_cui.sort_values('TS')
        # print("PCUI", per_cui)
        cui_and_status = per_cui[['CUI', 'TS']]
        print("CUI and status", cui_and_status)
        ordered_cuis = [row['CUI'] for _, row in cui_and_status.iterrows()]
        # ordered_cuis = sorted([
        #     (row['CUI'], row['TS']) for _, row in
        #     cui_and_status.iterrows()
        #     ], key=lambda cs: status_order.index(cs[1]))
        # # remove duplicates
        # ordered_cuis = [cui for nr, cui in enumerate(ordered_cuis) if cui not in ordered_cuis[:nr]]
        print(cui, "Ordered CUIs", len(ordered_cuis))
        # scuis = per_cui['SCUI'].unique().tolist()
        # if nr >= 25:
        #     raise
        if len(ordered_cuis) == 0:
            continue
        if len(ordered_cuis) > 1:
            print(f"{cui}:", len(ordered_cuis) if len(ordered_cuis) > 10 else ordered_cuis)
            print("CONTEXT:")
            for nr, row in per_cui.iterrows():
                print(row)
        out_dict[cui] = ordered_cuis[0]
    return out_dict


def main(*args: str):
    umls_path, needed_path, json_path = args
    umls_df = get_umls_df(umls_path)
    needed_umls_cuis = load_cuis(needed_path)
    print("Getting mappings")
    map_dict = get_mappings(umls_df, needed_umls_cuis)
    print("SAVING to", json_path)
    with open(json_path, 'w') as f:
        json.dump(map_dict, f)


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])
