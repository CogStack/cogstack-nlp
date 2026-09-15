SCRIPT="scripts/variance/get_variance_with_linker_and_tokenizer.py"
MODEL_PATH="../.temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"

# HEADER
echo "Dataset,linker,tokenizer,prec,rec,f1,runtime,throughput"

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
# convert embedding model once
EMBED_MODEL_PATH=`python scripts/variance/convert_to_embed_linker.py $MODEL_PATH data/embed_model_converted | tail -n 1`

# "With spacy tokenizer + embed lnker"
python $SCRIPT embed spacy $EMBED_MODEL_PATH $DATASET $EXTRA
# "With regex tokenizer + embed linker"
python $SCRIPT embed regex $EMBED_MODEL_PATH $DATASET $EXTRA

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
python $SCRIPT embed spacy $EMBED_MODEL_PATH $DATASET $EXTRA
# "With regex tokenizer + embed linker"
python $SCRIPT embed regex $EMBED_MODEL_PATH $DATASET $EXTRA
