# product_classifier.py
from pathlib import Path
import spacy

class ProductClassifier:
    def __init__(self, model_path: Path | str):
        self.model = spacy.load(str(model_path))

    def predict_category(self, text: str) -> str:
        doc = self.model(text)
        # فرض کن برچسب نهایی توکن اول باشد
        return doc.cats and max(doc.cats, key=doc.cats.get) or "unknown"
