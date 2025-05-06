import hashlib
from collections import defaultdict
from pathlib import Path

import boto3
import spacy
from botocore.exceptions import BotoCoreError, ClientError


class ReceiptParser:
    """
    کلاس برای پردازش رسید:
    - استخراج متن با AWS Textract
    - تشخیص موجودیت‌ها با مدل NER
    - دسته‌بندی آیتم‌ها با مدل طبقه‌بندی
    """

    def __init__(
        self,
        ner_model_path: str = "receipt_ner_model",
        cls_model_path: str | Path = None,
        aws_region: str = "ca-central-1"
    ):
        # بارگذاری مدل‌های NER و دسته‌بندی
        self.ner_model = spacy.load(str(ner_model_path))
        # مسیر پیش‌فرض مدل طبقه‌بندی
        if cls_model_path is None:
            base_dir = Path(__file__).resolve().parent
            cls_model_path = base_dir / "product_classifier" / "training" / "model-best"
        self.cls_model = spacy.load(str(cls_model_path))
        # مقداردهی Textract client
        self.textract = boto3.client("textract", region_name=aws_region)

    def analyze_bytes(self, image_bytes: bytes) -> dict:
        """
        فراخوانی AWS Textract analyze_expense برای OCR
        """
        try:
            return self.textract.analyze_expense(Document={"Bytes": image_bytes})
        except (BotoCoreError, ClientError) as e:
            raise RuntimeError("خطا در اتصال به AWS Textract") from e

    @staticmethod
    def extract_text(response: dict) -> str:
        """
        استخراج متن خام OCR از پاسخ Textract
        """
        lines = []
        for doc in response.get("ExpenseDocuments", []):
            for field in doc.get("SummaryFields", []):
                label = field.get("LabelDetection", {}).get("Text", "")
                value = field.get("ValueDetection", {}).get("Text", "")
                if label or value:
                    lines.append(f"{label}: {value}")
            for grp in doc.get("LineItemGroups", []):
                for item in grp.get("LineItems", []):
                    parts = []
                    for f in item.get("LineItemExpenseFields", []):
                        key = f.get("Type", {}).get("Text", "")
                        val = f.get("ValueDetection", {}).get("Text", "")
                        if key and val:
                            parts.append(f"{key}: {val}")
                    if parts:
                        lines.append(" | ".join(parts))
        return "\n".join(lines)

    def extract_entities(self, text: str) -> list[tuple[str, str]]:
        """
        اجرای مدل NER و بازگرداندن لیستی از جفت‌های (متن، برچسب)
        """
        doc = self.ner_model(text)
        return [(ent.text, ent.label_) for ent in doc.ents]

    def predict_category(self, text: str) -> str:
        """
        پیش‌بینی دسته برای متن ورودی با استفاده از مدل طبقه‌بندی
        """
        doc = self.cls_model(text)
        return max(doc.cats, key=doc.cats.get) if doc.cats else ""

    def aggregate_items(self, entities: list[tuple[str, str]]) -> dict:
        """
        تجمیع آیتم‌ها و قیمت‌ها بر اساس موجودیت‌های استخراج‌شده
        خروجی:
            {item_name: {"price": float, "count": int, "category": str}}
        """
        items = defaultdict(lambda: {"price": 0.0, "count": 0, "category": ""})
        for i in range(len(entities) - 1):
            text, label = entities[i]
            next_text, next_label = entities[i + 1]
            if label == "ITEM" and next_label == "PRICE":
                name = text.strip()
                try:
                    price = float(next_text.replace("$", ""))
                except ValueError:
                    continue
                items[name]["price"] += price
                items[name]["count"] += 1
                items[name]["category"] = self.predict_category(name)
        return dict(items)

    def parse(self, image_bytes: bytes) -> dict:
        """
        اجرای کل فرایند:
        1. OCR با Textract
        2. استخراج متن
        3. تشخیص موجودیت‌ها
        4. تجمیع آیتم‌ها
        5. استخراج فیلدهای کلیدی (TOTAL, TAX, DISCOUNT, DATE)

        خروجی:
            {
                "text": str,
                "entities": list[tuple[str, str]],
                "items": dict,
                "total": float,
                "tax": float,
                "discount": float,
                "date": str,
                "text_hash": str,
                "textract_response": dict
            }
        """
        # 1. OCR
        response = self.analyze_bytes(image_bytes)
        # 2. استخراج متن
        text = self.extract_text(response)
        # 3. NER
        entities = self.extract_entities(text)
        # 4. تجمیع آیتم‌ها
        items = self.aggregate_items(entities)

        # 5. استخراج فیلدهای کلیدی
        def _find_amount(labels):
            for val, lab in entities:
                if lab in labels:
                    try:
                        return float(val.replace("$", ""))
                    except ValueError:
                        return 0.0
            return 0.0

        total = _find_amount(["TOTAL"])
        tax = _find_amount(["TAX", "TAX_AMOUNT"])
        discount = _find_amount(["DISCOUNT", "DISCOUNT_AMOUNT"])
        date = next((val for val, lab in entities if lab == "DATE"), "unknown")
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        return {
            "text": text,
            "entities": entities,
            "items": items,
            "total": total,
            "tax": tax,
            "discount": discount,
            "date": date,
            "text_hash": text_hash,
            "textract_response": response,
        }
