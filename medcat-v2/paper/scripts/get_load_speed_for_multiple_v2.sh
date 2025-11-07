echo "Regular NER / 2023 model"
ner1="2023 NER (no MetaCAT)"
ner_model_path_no_mc="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"
ner2="2023 NER (w MetaCAT)"
ner_model_path_w_mc="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/CONVERT_2023_model_7ff751a4bb71630d.zip"
deid="n2c2 DeID"
deid_model_path="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/CONVERT_deid_model_af31d2a9c5ccbe4d.zip.zip"

bash scripts/get_load_speed_for_multiple.sh "$ner1" "$ner_model_path_no_mc" "$ner2" "$ner_model_path_w_mc" "$deid" "$deid_model_path"
