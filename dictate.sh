#!/bin/bash

cd ~/path/to/dictate || exit
bash -c "source .venv/bin/activate && python3 dictate.py --model medium"
