ner1="2023_NER_no_MetaCAT"
ner_model_path_no_mc="/Users/martratas/Documents/CogStack/MedCAT/MedCAT/models/20230227__kch_gstt_trained_model_no_mc_d84c313f24311484.zip"
ner2="2023_NER_w_MetaCAT"
ner_model_path_w_mc="/Users/martratas/Documents/CogStack/MedCAT/MedCAT/models/20230227__kch_gstt_trained_model_494c3717f637bb89.zip"
deid="n2c2_DeID"
deid_model_path="/Users/martratas/Documents/CogStack/MedCAT/MedCAT/models/deid_medcat_n2c2_modelpack.zip"

out_prefix="out/load_speed/v1"
if [[ ! -z "$1" ]]
  then
    out_prefix=$1
    echo "Overwriting out prefix with: "$1
fi

bash scripts/speed/get_load_speed_for_multiple.sh $out_prefix "$ner1" "$ner_model_path_no_mc" "$ner2" "$ner_model_path_w_mc" "$deid" "$deid_model_path"
