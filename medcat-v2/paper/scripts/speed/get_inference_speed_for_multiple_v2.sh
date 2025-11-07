echo "Regular NER / 2023 model"
ner1="2023 NER (no MetaCAT)"
ner_model_path_no_mc="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"
ner2="2023 NER (w MetaCAT)"
ner_model_path_w_mc="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/CONVERT_2023_model_7ff751a4bb71630d.zip"
csv_path="data/unsupervised/mimic_iv_discharge_head20.csv"

out_prefix="out/inference_speed/v2"
if [ -z "$1" ]
  then
    out_prefix=$1
    echo "Overwriting out prefix with: "$1
fi

bash scripts/speed/get_load_speed_for_multiple.sh $out_prefix "$ner1" "$ner_model_path_no_mc" $csv_path "$ner2" "$ner_model_path_w_mc" $csv_path
