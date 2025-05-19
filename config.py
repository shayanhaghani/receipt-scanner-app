# config.py

import os
from pathlib import Path

# Base project directory
BASE_DIR = Path(__file__).parent

# AWS configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Model paths
NER_MODEL_DIR = BASE_DIR / "receipt_ner_model"
CLS_MODEL_DIR = BASE_DIR / "product_classifier" / "training" / "model-best"  # use ASCII hyphen to match folder name

# Database URL (you can override via env var)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'receipts.db'}"
)

# Output directory for any generated files
OUTPUT_DIR = BASE_DIR / "output"
