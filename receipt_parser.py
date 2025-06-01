import hashlib
from collections import defaultdict
from pathlib import Path
import spacy
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
import logging
from typing import Optional, Dict, List, Tuple

class ReceiptParser:
    """
    Class for receipt processing:
    - Text extraction using AWS Textract
    - Entity recognition using NER model
    - Item classification using classification model
    """

    def __init__(
        self, 
        ner_model_path: str = "receipt_ner_model",
        cls_model_path: Optional[str | Path] = None,
        aws_region: str = "us-east-1",
        retry_attempts: int = 3
    ):
        # Load NER and classification models
        self.ner_model = spacy.load(str(ner_model_path))
        # Default path for classification model
        if cls_model_path is None:
            base_dir = Path(__file__).resolve().parent
            cls_model_path = base_dir / "product_classifier" / "training" / "model-best"
        self.cls_model = spacy.load(str(cls_model_path))
        # Initialize Textract client with specified region
        self.textract = boto3.client("textract", region_name=aws_region)
        self.retry_attempts = retry_attempts

    def analyze_bytes(self, image_bytes: bytes) -> dict:
        for attempt in range(self.retry_attempts):
            try:
                return self._try_analyze_bytes(image_bytes)
            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    logging.error(f"Final attempt failed: {e}")
                    raise
                logging.warning(f"Attempt {attempt + 1} failed: {e}")
                
    def _try_analyze_bytes(self, image_bytes: bytes) -> dict:
        """
        فراخوانی AWS Textract analyze_expense برای OCR با اعتبارسنجی اولیه
        """
        # اعتبارسنجی اولیه ورودی
        if not isinstance(image_bytes, (bytes, bytearray)) or len(image_bytes) == 0:
            raise RuntimeError("بایت‌های تصویر نامعتبر است.")
        # Textract میزان حداکثر 5MB برای تصاویر پشتیبانی می‌کند
        if len(image_bytes) > 5 * 1024 * 1024:
            raise RuntimeError("حجم تصویر بیش از 5MB است.")

        try:
            resp = self.textract.analyze_expense(Document={"Bytes": image_bytes})
            return resp

        except NoCredentialsError as e:
            raise RuntimeError("AWS credentials پیدا نشدند. لطفاً ~/.aws/credentials را چک کنید.") from e

        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "UnknownError")
            msg = e.response.get("Error", {}).get("Message", "")
            raise RuntimeError(f"خطای Textract: {code} — {msg}") from e

        except Exception as e:
            raise RuntimeError(f"خطا در اتصال به AWS Textract: {e}") from e

    def extract_text(self, response: dict) -> str:
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

    def extract_entities(self, text: str) -> List[Tuple[str, str]]:
        try:
            doc = self.ner_model(text)
            return [(ent.text, ent.label_) for ent in doc.ents]
        except Exception as e:
            logging.error(f"NER processing error: {e}")
            return []

    def predict_category(self, text: str) -> str:
        """
        پیش‌بینی دسته برای متن ورودی با استفاده از مدل طبقه‌بندی
        """
        doc = self.cls_model(text)
        return max(doc.cats, key=doc.cats.get) if doc.cats else ""

    from collections import defaultdict

    def aggregate_items(self, entities: list[tuple[str, str]]) -> dict:
        items = []
        current_item = None
        for val, lab in entities:
            if lab == "ITEM":
                current_item = val
            elif lab == "PRICE" and current_item is not None:
                try:
                    price = float(val.replace(',', '').replace('$', ''))
                    items.append((current_item, price))
                except ValueError:
                    pass
                current_item = None  # Reset for the next pair

        agg = defaultdict(lambda: {"price": 0.0, "count": 0, "category": ""})
        for item, price in items:
            key = (item, price)
            agg[key]["price"] = price
            agg[key]["count"] += 1
            agg[key]["category"] = self.predict_category(item)
        return agg

    def parse(self, image_bytes: bytes) -> dict:
        # 1. OCR and basic extraction
        response = self.analyze_bytes(image_bytes)
        text = self.extract_text(response)
        entities = self.extract_entities(text)
        items = self.aggregate_items(entities)
        result_items = []
        
        # 2. Calculate raw subtotal from items
        subtotal = 0.0
        for (item, price), val in items.items():
            item_total = price * val["count"]
            subtotal += item_total
            result_items.append({
                "item": item,
                "price": price,
                "quantity": val["count"],
                "category": val["category"],
                "total": item_total
            })

        # 3. Get final total first (we need this for accurate calculations)
        total_amount = 0.0
        for doc in response.get("ExpenseDocuments", []):
            for field in doc.get("SummaryFields", []):
                if field.get("Type", {}).get("Text", "").upper() in ["TOTAL", "BALANCE DUE", "BALANCE TO PAY", "TOTAL_AMOUNT"]:
                    try:
                        total_str = field.get("ValueDetection", {}).get("Text", "0")
                        total_amount = float(total_str.replace("$", "").replace(",", ""))
                        break
                    except (ValueError, AttributeError):
                        continue

        # 4. Find discount from receipt
        discount = 0.0
        for doc in response.get("ExpenseDocuments", []):
            for field in doc.get("SummaryFields", []):
                field_type = field.get("Type", {}).get("Text", "").upper()
                if "DISCOUNT" in field_type:
                    try:
                        discount_str = field.get("ValueDetection", {}).get("Text", "0")
                        discount = abs(float(discount_str.replace("$", "").replace(",", "").replace("-", "")))
                        break
                    except (ValueError, AttributeError):
                        continue

        # 5. Calculate subtotal after discount
        subtotal_after_discount = subtotal - discount

        # 6. Calculate tax as difference between total and subtotal_after_discount
        tax = round(total_amount - subtotal_after_discount, 2)

        # 7. Get date and generate hash
        date = next((val for val, lab in entities if lab == "DATE"), "unknown")
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        return {
            "text": text,
            "entities": entities,
            "items": result_items,
            "subtotal": subtotal,  
            "discount": discount,  
            "subtotal_after_discount": subtotal_after_discount,  
            "tax": tax,  
            "total_amount": total_amount,  
            "date": date,
            "text_hash": text_hash,
            "textract_response": response
        }
