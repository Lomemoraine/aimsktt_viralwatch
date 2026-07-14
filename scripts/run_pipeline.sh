#!/bin/bash

set -e


echo "Starting ML pipeline"


./scripts/download_data.sh


./scripts/verify_files.sh


python src/train_model.py


echo "Pipeline completed"