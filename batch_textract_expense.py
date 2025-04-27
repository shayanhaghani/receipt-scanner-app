import boto3
import os
from tqdm import tqdm

# ---------- تنظیمات ----------
input_folder = "/Users/shayanhaghani/Desktop/Scan-grok/Datasets/Sroie/Train/img"     # پوشه‌ی تصاویر
output_folder = "/Users/shayanhaghani/Desktop/Scan-grok/Datasets/Sroie/Train/json"      # پوشه‌ی خروجی JSON
region = "ca-central-1"           # ناحیه AWS (بسته به منطقه خودت)

# ایجاد پوشه خروجی اگر وجود نداره
os.makedirs(output_folder, exist_ok=True)

# اتصال به Amazon Textract
textract = boto3.client("textract", region_name=region)

# خواندن همه فایل‌های تصویر
image_files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

print(f"✅ شروع OCR روی {len(image_files)} تصویر...")

for filename in tqdm(image_files):
    image_path = os.path.join(input_folder, filename)
    with open(image_path, "rb") as img_file:
        img_bytes = img_file.read()
    
    try:
        response = textract.analyze_expense(Document={'Bytes': img_bytes})
        output_path = os.path.join(output_folder, filename.rsplit('.', 1)[0] + ".json")
        with open(output_path, "w", encoding="utf-8") as f:
            import json
            json.dump(response, f, indent=2)
    except Exception as e:
        print(f"❌ خطا در فایل {filename}: {e}")

print("✅ همه فایل‌ها پردازش شدند و خروجی JSON ذخیره شد.")
