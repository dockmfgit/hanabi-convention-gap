#!/bin/bash
set -e
source ~/venvs/hanabi/bin/activate
export OMP_NUM_THREADS=1
SP=/tmp/claude-1002/-home-makotof-research-Hanabi-offbelief-learning/2f15f1ab-92f8-42b0-8e7d-65de0f3c304a/scratchpad
M=$OBL_ROOT/off-belief-learning/models
OUT=$SP/games

# Self-play OBL1-5, model a, 1000 games each
declare -A DIRS=(
  [OBL1]=icml_OBL1/OFF_BELIEF1_SHUFFLE_COLOR0_BZA0_BELIEF_a
  [OBL2]=icml_OBL2/OFF_BELIEF1_SHUFFLE_COLOR0_LOAD1_BZA0_BELIEF_a
  [OBL3]=icml_OBL3/OFF_BELIEF1_SHUFFLE_COLOR0_LOAD1_BZA0_BELIEF_a
  [OBL4]=icml_OBL4/OFF_BELIEF1_SHUFFLE_COLOR0_LOAD1_BZA0_BELIEF_a
  [OBL5]=icml_OBL5/OFF_BELIEF1_SHUFFLE_COLOR0_LOAD1_BZA0_BELIEF_a
)
SEED=100000
for L in OBL1 OBL2 OBL3 OBL4 OBL5; do
  python $SP/export_obl_games.py \
    --weight1 $M/${DIRS[$L]}/model0.pthw \
    --num_game 1000 --seed_base $SEED --out_dir $OUT --prefix ${L}_selfplay
  SEED=$((SEED + 10000))
done

# OBL1 cross-play: all 10 unordered seed pairs, 100 games each
XP=$M/icml_OBL1
seeds=(a b c d e)
for ((i=0; i<5; i++)); do
  for ((j=i+1; j<5; j++)); do
    s1=${seeds[$i]}; s2=${seeds[$j]}
    python $SP/export_obl_games.py \
      --weight1 $XP/OFF_BELIEF1_SHUFFLE_COLOR0_BZA0_BELIEF_${s1}/model0.pthw \
      --weight2 $XP/OFF_BELIEF1_SHUFFLE_COLOR0_BZA0_BELIEF_${s2}/model0.pthw \
      --num_game 100 --seed_base $SEED --out_dir $OUT --prefix OBL1_cross_${s1}${s2}
    SEED=$((SEED + 1000))
  done
done
echo ALL_DONE
