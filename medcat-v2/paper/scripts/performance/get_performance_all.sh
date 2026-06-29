a

script_path="scripts/performance/get_performance_for_model_and_ds.py"
v1_model_pack="/Users/martratas/Documents/CogStack/MedCAT/MedCAT/models/20230227__kch_gstt_trained_model_no_mc_d84c313f24311484.zip"
v2_model_pack="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"
# v1_model_pack="/Users/martratas/Documents/CogStack/MedCAT/medcat-snomed-model-creation/.creation_cache/out_snomed_2025/final_model_Snomed2025-07-11_de7cbec4a786e418.zip"
# v2_model_pack="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/2025_11_19_issue228_add_meta_cat_to_other/models/v2_Snomed2025_MIMIC_IV_bbe806e192df009f.zip"

echo "*****************"
echo "running v1 stuff"
echo "*****************"

source .venv_v1/bin/activate

python $script_path $v1_model_pack data/supervised/*/*.json

echo "*****************"
echo "running v2 stuff"
echo "*****************"

source ../.venv312/bin/activate

python $script_path $v2_model_pack data/supervised/*/*.json
