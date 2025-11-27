SCRIPT="scripts/variance/get_variance_with_linker_and_tokenizer.py"
MODEL_PATH="../.temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"
MODEL_PATH="../tests/resources/mct2_model_pack.zip"

#"==COMETA=="
DATASET="data/supervised/cometa/mct_export.json"
EXTRA="--one-line"

#"NORMAL"
python $SCRIPT old spacy $MODEL_PATH $DATASET $EXTRA
#"With faster linker"
python $SCRIPT new spacy $MODEL_PATH $DATASET $EXTRA
#"With regex tokenizer"
python $SCRIPT old regex $MODEL_PATH $DATASET $EXTRA
# "With regex tokenizer AND faster linker"
python $SCRIPT new regex $MODEL_PATH $DATASET $EXTRA

# with embedding linker

# "With spacy tokenizer + embed lnker"
python $SCRIPT embed spacy $MODEL_PATH $DATASET $EXTRA
# "With regex tokenizer + embed linker"
python $SCRIPT embed regex $MODEL_PATH $DATASET $EXTRA

# other dataset
# "==Linking Challenge=="
DATASET="data/supervised/linking_challenge/mct_export.json"

# "NORMAL"
python $SCRIPT old spacy $MODEL_PATH $DATASET $EXTRA
# "With faster linker"
python $SCRIPT new spacy $MODEL_PATH $DATASET $EXTRA
# "With regex tokenizer"
python $SCRIPT old regex $MODEL_PATH $DATASET $EXTRA
# "With regex tokenizer AND faster linker"
python $SCRIPT new regex $MODEL_PATH $DATASET $EXTRA

# with embedding linker

# "With spacy tokenizer + embed lnker"
python $SCRIPT embed spacy $MODEL_PATH $DATASET $EXTRA
# "With regex tokenizer + embed linker"
python $SCRIPT embed regex $MODEL_PATH $DATASET $EXTRA
