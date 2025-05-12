import hashlib
from collections import defaultdict
from pathlib import Path
import spacy
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

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
        aws_region: str = "us-east-1"
    ):
        # بارگذاری مدل‌های NER و دسته‌بندی
        self.ner_model = spacy.load(str(ner_model_path))
        # مسیر پیش‌فرض مدل طبقه‌بندی
        if cls_model_path is None:
            base_dir = Path(__file__).resolve().parent
            cls_model_path = base_dir / "product_classifier" / "training" / "model-best"
        self.cls_model = spacy.load(str(cls_model_path))
        # مقداردهی Textract client با ریجن مشخص
        self.textract = boto3.client("textract", region_name=aws_region)

    def analyze_bytes(self, image_bytes: bytes) -> dict:
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
        for val, lab in entities:
            if lab == "ITEM":
                current = items[val]
                current["count"] += 1
                current["category"] = self.predict_category(val)
            elif lab == "PRICE":
                # مقدار عددی را استخراج و به آیتم قبل نسبت می‌دهیم
                try:
                    price = float(val.replace(',', ''))
                except ValueError:
                    continue
                # آخرین آیتم اضافه‌شده
                last_item = list(items.keys())[-1] if items else None
                if last_item:
                    items[last_item]["price"] = price
        return items

    def parse(self, image_bytes: bytes) -> dict:
        """
        روش کلی:
        1. فراخوانی analyze_bytes برای OCR دریافت پاسخ
        2. extract_text گرفتن متن خام
        3. extract_entities شناسایی موجودیت‌ها
        4. aggregate_items تجمیع آیتم‌ها
        5. محاسبه مجموع و مالیات و تخفیف
        """
        # 1. OCR
        response = self.analyze_bytes(image_bytes)
        # 2. استخراج متن خام
        text = self.extract_text(response)
        # 3. شناسایی موجودیت‌ها
        entities = self.extract_entities(text)
        # 4. تجمیع آیتم‌ها
        items = self.aggregate_items(entities)

        # محاسبات اضافی: جمع کل، مالیات و تخفیف
        def _find_amount(labels):
            for val, lab in entities:
                if lab in labels:
                    try:
                        return float(val.replace(',', ''))
                    except ValueError:
                        continue
            return 0.0

        total = _find_amount(["TOTAL", "TOTAL_AMOUNT"])
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
