#!/bin/bash

SAVE_PREFIX=$1
shift 1

# --- Input Validation ---
if (( $# == 0 )); then
    echo "Usage: $0 <save_prefix> <name1> <path1> <name2> <path2> ..."
    exit 0
fi

if (( $# % 2 != 0 )); then
    echo "Error: Arguments must be provided in pairs (name and path)." >&2
    exit 1
fi

echo "Starting pairwise argument processing..."
echo "-----------------------------------------"

# The 'while' loop continues as long as there are arguments left ($# is non-zero)
while (( "$#" )); do
    MODEL_NAME="$1"
    MODEL_PATH="$2"

    echo "Model: '$MODEL_NAME'"

    SAVE_PATH=$SAVE_PREFIX"_"$MODEL_NAME".json"
    echo "Will save to" $SAVE_PATH

    python scripts/speed/get_load_speed_all.py $MODEL_PATH --save-json $SAVE_PATH

    echo "---"

    # Shift discards the first N arguments.
    # We discard the two arguments we just processed ($1 and $2)
    shift 2
done

echo "-----------------------------------------"
echo "Processing complete."