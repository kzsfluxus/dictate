#!/bin/bash

dictate_path="/path/to/dictate"
cd "$dictate_path" || exit
bash -c "source .venv/bin/activate && python3 dictate.py --model medium"
