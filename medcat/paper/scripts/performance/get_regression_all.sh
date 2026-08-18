

script_path="scripts/performance/regression_perf.py"
v1_model_pack="/Users/martratas/Documents/CogStack/MedCAT/MedCAT/models/20230227__kch_gstt_trained_model_no_mc_d84c313f24311484.zip"
v2_model_pack="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"
v1_out_file="out/performance/v1_regression.csv"
v2_out_file="out/performance/v2_regression.csv"

echo "*****************"
echo "running v1 stuff"
echo "*****************"

source .venv_v1/bin/activate

python $script_path $v1_model_pack | head -n 1 >> $v1_out_file

echo "*****************"
echo "running v2 stuff"
echo "*****************"

source ../.venv312/bin/activate

python $script_path $v2_model_pack | head -n 1 >> $v2_out_file
