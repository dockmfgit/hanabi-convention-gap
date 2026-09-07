#!/bin/bash
set -e
source ~/venvs/hanabi/bin/activate
export OMP_NUM_THREADS=1
SP=/tmp/claude-1002/-home-makotof-research-Hanabi-offbelief-learning/2f15f1ab-92f8-42b0-8e7d-65de0f3c304a/scratchpad
M=$OBL_ROOT/off-belief-learning/models
OUT=$SP/games

declare -A DIRS=(
  [1]=icml_OBL1/OFF_BELIEF1_SHUFFLE_COLOR0_BZA0_BELIEF_a
  [2]=icml_OBL2/OFF_BELIEF1_SHUFFLE_COLOR0_LOAD1_BZA0_BELIEF_a
  [3]=icml_OBL3/OFF_BELIEF1_SHUFFLE_COLOR0_LOAD1_BZA0_BELIEF_a
  [4]=icml_OBL4/OFF_BELIEF1_SHUFFLE_COLOR0_LOAD1_BZA0_BELIEF_a
  [5]=icml_OBL5/OFF_BELIEF1_SHUFFLE_COLOR0_LOAD1_BZA0_BELIEF_a
)
SEED=200000
for ((i=1; i<=5; i++)); do
  for ((j=i+1; j<=5; j++)); do
    python $SP/export_obl_games.py \
      --weight1 $M/${DIRS[$i]}/model0.pthw --name1 OBL$i \
      --weight2 $M/${DIRS[$j]}/model0.pthw --name2 OBL$j \
      --num_game 1000 --seed_base $SEED --out_dir $OUT --prefix interlevel_OBL${i}xOBL${j} \
      | tail -1
    SEED=$((SEED + 10000))
  done
done
echo ALL_DONE
