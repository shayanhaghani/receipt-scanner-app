# README.md

## 📃 Receipt AI - OCR, NER & Category Classification

This app uses OCR + Named Entity Recognition (NER) + Text Classification with spaCy to extract item names, prices, and categorize products from store receipts. It supports:

- Uploading images of receipts
- Extracting text via Amazon Textract OCR
- Identifying entities (item, price, vendor, date, etc.) with a trained spaCy NER model
- Categorizing products using a separate spaCy text classification model
- Displaying final data in a Streamlit dashboard

---

## 🗂️ Folder Structure

```bash
Scan-grok/
├── main.py                      # Final Streamlit app combining NER + Category
├── main-final.py               # Old final version of Streamlit app
├── test_receipt_ner.py         # Script to test trained NER model standalone
├── train_receipt_ner.py        # Train script for NER model
├── convert_to_spacy_train_data.py # Converts Label Studio JSON to spaCy format
├── generate_labelstudio_data.py   # Converts raw JSON/text to Label Studio import format
├── exported_labelstudio.json   # NER-labeled data exported from Label Studio
├── labelstudio_ready.json      # Transformed input format for Label Studio
├── train_data_spacy.json       # Final NER training data (after conversion)
├── product_classifier/         # Category classification spaCy project
│   ├── assets/train_textcat.spacy      # Final .spacy file (converted from CSV)
│   ├── configs/textcat_config.cfg      # Config file for category model
│   ├── convert_csv_to_spacy.py         # Converts CSV to .spacy format
│   ├── training/model-last/            # Trained text classification model
│   └── training/model-best/           # Best performing checkpoint
├── receipt_ner_model/         # Trained NER model
├── raw_ocr_new/               # Folder with raw OCR results (Amazon Textract)
├── receipts.db                # (Optional) database for scanned receipts
├── training_data_final_v3.csv # CSV for training product category
├── tfidf_vectorizer.pkl       # (Old) Vectorizer for non-spaCy text classification
├── rf_model.pkl               # (Old) RandomForest classifier model
```

---

## ✅ Installation

```bash
pip install -r requirements.txt
```

You also need:
- `spaCy` (>=3.8.0)
- `boto3` for Amazon Textract
- `streamlit` for UI
- `pandas`, `scikit-learn` for preprocessing

---

## 💡 How It Works

### NER Model (receipt_ner_model):
- Trained using Label Studio JSON annotations
- Converts annotations to spaCy format with `convert_to_spacy_train_data.py`
- Trained via `train_receipt_ner.py`

### Category Model (product_classifier):
- Uses labeled CSV (`training_data_final.csv`)
- Converted via `convert_csv_to_spacy.py`
- Trained via:
```bash
python3 -m spacy train configs/textcat_config.cfg \
  --output training/ \
  --paths.train assets/train_textcat.spacy \
  --paths.dev assets/train_textcat.spacy
```

### Final App:
`main.py` loads both models and:
- Takes OCR result
- Extracts items and prices via NER
- Classifies item categories via category model
- Displays table with columns: Item | Price | Category

---

## 🔹 Update Workflow

1. Label more receipts in Label Studio
2. Export JSON
3. Convert via `convert_to_spacy_train_data.py`
4. Retrain NER model
5. Prepare new `training_data_final.csv`
6. Run `convert_csv_to_spacy.py`
7. Retrain classifier

You're done!
