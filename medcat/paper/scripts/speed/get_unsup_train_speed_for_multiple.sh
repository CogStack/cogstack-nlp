#!/bin/bash

SAVE_PREFIX=$1
shift 1

# --- Input Validation ---
if (( $# == 0 )); then
    echo "Usage: $0 <save_prefix> <name1> <model_path1> <csv_path1> <name2> <model_path2> <csv_path2> ..."
    exit 0
fi

if (( $# % 3 != 0 )); then
    echo "Error: Arguments must be provided in triples (name, model path, and CSV path)." >&2
    exit 1
fi

echo "Starting triplet argument processing..."
echo "-----------------------------------------"

# The 'while' loop continues as long as there are arguments left ($# is non-zero)
while (( "$#" )); do
    MODEL_NAME="$1"
    MODEL_PATH="$2"
    CSV_PATH="$3"

    echo "Model: '$MODEL_NAME' with CSV '$CSV_PATH'"

    SAVE_PATH=$SAVE_PREFIX"_"$MODEL_NAME".json"
    echo "Will save to" $SAVE_PATH

    FULL_TARGET="scripts/speed/get_unsup_train_speed_all.py $MODEL_PATH $CSV_PATH --save-json $SAVE_PATH"
    echo "Running: python $FULL_TARGET"
    python $FULL_TARGET

    echo "---"

    # Shift discards the first N arguments.
    # We discard the thre arguments we just processed ($1, $2, and $3)
    shift 3
done

echo "-----------------------------------------"
echo "Processing complete."