# README.md
# SmartReceipt AI

A Streamlit-based, AI-powered receipt scanner and analyzer that leverages **AWS Textract**, **spaCy NER**, and a **product categorization** pipeline to automatically extract, categorize, and visualize purchase data from scanned receipts.

---

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Installation](#installation)
   - [Environment Configuration](#environment-configuration)
4. [Usage](#usage)
   - [Run the Streamlit App](#run-the-streamlit-app)
   - [CLI Scripts](#cli-scripts)
5. [Model Training & Data Preparation](#model-training--data-preparation)
6. [Database Schema](#database-schema)
7. [Testing](#testing)
8. [Deploy & Docker (Optional)](#deploy--docker-optional)
9. [Contributing](#contributing)
10. [License](#license)

---

## Features

- **Automated OCR**: Extract raw text from receipt images or PDFs via AWS Textract.
- **Named Entity Recognition**: Identify key receipt entities (ITEM, PRICE, TOTAL, TAX, DISCOUNT, DATE) using a custom spaCy model.
- **Product Categorization**: Classify each line-item into product categories with a spaCy text classification model.
- **Data Persistence**: Store receipts and line-items in a SQLite database (`receipts.db`) with hash-based duplicate detection.
- **Interactive Dashboard**: Streamlit UI for uploading receipts, browsing saved records, and viewing monthly purchase summaries.
- **Reporting**: Bar and pie charts summarizing expenses by category and month.

---

## Project Structure

```
ScanappProject/
├─ main-final.py                   # Streamlit application entrypoint
├─ receipts.db                     # SQLite database (example or initial schema)
├─ raw_ocr_new/                    # Directory for raw OCR text output
├─ tfidf_vectorizer.pkl            # TF-IDF vectorizer for legacy classification scripts
├─ rf_model.pkl                    # RandomForest model for legacy classification scripts
├─ labelstudio_ready.json          # JSON fixture for Label Studio import
├─ receipt_ner_model/              # Trained spaCy NER model directory
├─ product_classifier/             # spaCy TextCat model directories (model-best / model-last)
│  └─ training/
│     ├─ model-best/
│     └─ model-last/
├─ convert_to_spacy_train_data.py  # Convert Label Studio JSON → spaCy training data
├─ generate_labelstudio_data.py    # Generate Label Studio import data from raw receipts
├─ train_receipt_ner.py            # Train the NER model with spaCy
├─ test_receipt_ner.py             # Unit tests for the NER pipeline
└─ ...                             # Additional scripts, configs, .gitignore, etc.
```

---

## Getting Started

### Prerequisites

- **Python 3.8+**
- **pip** package manager
- **AWS Credentials** with permission for Textract (set via environment or IAM role)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ScanappProject.git
   cd ScanappProject
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   If you don’t have a `requirements.txt`, ensure you install:
   ```bash
   pip install streamlit pandas spacy boto3 plotly sklearn
   ```
3. Download spaCy models (if needed):
   ```bash
   python -m spacy download en_core_web_sm
   ```

### Environment Configuration

Create a `.env` file or export the following variables:
```bash
export AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY
export AWS_REGION=ca-central-1      # Canada Central (adjust to your region)
export DB_PATH=receipts.db          # Path to sqlite database
export OUTPUT_DIR=raw_ocr_new       # Path for saving raw OCR text
```

---

## Usage

### Run the Streamlit App

```bash
streamlit run main-final.py
```

- **Upload Receipt**: Drag & drop images or PDFs.
- **Review Data**: View raw OCR text, recognized entities, and item table.
- **Duplicate Handling**: Detect and display existing receipts.
- **Browse & Reports**: Navigate to saved receipts and view monthly category charts.

### CLI Scripts

- **Generate Label Studio Data**:
  ```bash
  python generate_labelstudio_data.py
  ```
- **Convert to spaCy Training Format**:
  ```bash
  python convert_to_spacy_train_data.py
  ```
- **Train NER Model**:
  ```bash
  python train_receipt_ner.py --output receipt_ner_model
  ```

---

## Model Training & Data Preparation

1. Label a few receipts in [Label Studio](https://labelstud.io/) using `labelstudio_ready.json` as the import.
2. Convert to spaCy format:
   ```bash
   python convert_to_spacy_train_data.py
   ```
3. Train the custom NER model:
   ```bash
   python train_receipt_ner.py --output receipt_ner_model
   ```
4. Retrain or fine-tune the text classification model if needed (scikit-learn TF-IDF + RandomForest or spaCy textcat).

---

## Database Schema

- **receipts**: stores `id`, `receipt_date`, `total_amount`, `tax_amount`, `discount_amount`, `item_count`, `ocr_path`, `text_hash`, `created_at`
- **items**: stores `id`, `receipt_id` (FK), `item_name`, `price`, `category`

---

## Testing

Run pytest to verify the NER pipeline:

```bash
pytest test_receipt_ner.py
```

---

## Deploy & Docker (Optional)

You can containerize the app:

```dockerfile
# Dockerfile example
FROM python:3.9-slim
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ["streamlit", "run", "main-final.py"]
```

Build and run:
```bash
docker build -t smartreceipt-ai .
docker run -p 8501:8501 smartreceipt-ai
```

---

## Contributing

Contributions are welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Submit a pull request

---

## License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

*Made with ❤️ by Shayan*