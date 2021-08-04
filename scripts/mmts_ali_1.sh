#!/usr/bin/env bash

export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890 all_proxy=socks5://127.0.0.1:7890 no_proxy=localhost,127.0.0.0/8,*.local

./run.py \
 --model '{"class_path": "src.MMTSMatcher"}' \
 --data '{"class_path": "src.AliDataModule", "init_args": {"use_image": False, "prod_num": 200}}' \
 --trainer.gpus 1,

./run.py \
 --model '{"class_path": "src.MMTSMatcher"}' \
 --data '{"class_path": "src.AliDataModule", "init_args": {"use_image": True,  "prod_num": 200}}' \
 --trainer.gpus 1,