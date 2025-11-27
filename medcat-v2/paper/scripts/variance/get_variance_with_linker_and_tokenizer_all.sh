SCRIPT="scripts/variance/get_variance_with_linker_and_tokenizer.py"
MODEL_PATH="../.temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"

echo "==COMETA=="
DATASET="data/supervised/cometa/mct_export.json"

echo "NORMAL"
python $SCRIPT old spacy $MODEL_PATH $DATASET
echo "With faster linker"
python $SCRIPT new spacy $MODEL_PATH $DATASET
echo "With regex tokenizer"
python $SCRIPT old regex $MODEL_PATH $DATASET
echo "With regex tokenizer AND faster linker"
python $SCRIPT new regex $MODEL_PATH $DATASET

# with embedding linker

echo "With spacy tokenizer + embed lnker"
python $SCRIPT embed spacy $MODEL_PATH $DATASET
echo "With regex tokenizer + embed linker"
python $SCRIPT embed regex $MODEL_PATH $DATASET

# other dataset
echo "==Linking Challenge=="
DATASET="data/supervised/linking_challenge/mct_export.json"

echo "NORMAL"
python $SCRIPT old spacy $MODEL_PATH $DATASET
echo "With faster linker"
python $SCRIPT new spacy $MODEL_PATH $DATASET
echo "With regex tokenizer"
python $SCRIPT old regex $MODEL_PATH $DATASET
echo "With regex tokenizer AND faster linker"
python $SCRIPT new regex $MODEL_PATH $DATASET

# with embedding linker

echo "With spacy tokenizer + embed lnker"
python $SCRIPT embed spacy $MODEL_PATH $DATASET
echo "With regex tokenizer + embed linker"
python $SCRIPT embed regex $MODEL_PATH $DATASET
