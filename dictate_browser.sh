#!/bin/bash

dictate_path="/path/to/dictate"
cd "$dictate_path" || exit
bash -c "python3 diktatum_browser.py"
