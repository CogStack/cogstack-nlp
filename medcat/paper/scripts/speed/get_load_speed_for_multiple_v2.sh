ner1="2023_NER_no_MetaCAT"
ner_model_path_no_mc="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"
ner2="2023_NER_w_MetaCAT"
ner_model_path_w_mc="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/20230227__kch_gstt_trained_model_f76d2121b77c3e9a.zip"
deid="n2c2_DeID"
deid_model_path="/Users/martratas/Documents/CogStack/MedCAT/monorepo-nlp/medcat-v2/.temp/CONVERT_deid_model_af31d2a9c5ccbe4d.zip.zip"

out_prefix="out/load_speed/v2"
if [[ ! -z "$1" ]]
  then
    out_prefix=$1
    echo "Overwriting out prefix with: "$1
fi


bash scripts/speed/get_load_speed_for_multiple.sh $out_prefix "$ner1" "$ner_model_path_no_mc" "$ner2" "$ner_model_path_w_mc" "$deid" "$deid_model_path"
