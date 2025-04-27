import os
import json

# مسیر پوشه‌ای که فایل‌های JSON خام Textract توش هست
input_folder = "/Users/shayanhaghani/Desktop/Scan-grok/Datasets/Sroie/Train/json"  # ← اینو با مسیر واقعی عوض کن
output_file = "labelstudio_ready.json"

all_tasks = []

for filename in os.listdir(input_folder):
    if filename.endswith(".json"):
        file_path = os.path.join(input_folder, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            textract_data = json.load(f)

        raw_text_lines = []

        for doc in textract_data.get("ExpenseDocuments", []):
            for field in doc.get("SummaryFields", []):
                label = field.get("LabelDetection", {}).get("Text", "")
                value = field.get("ValueDetection", {}).get("Text", "")
                if label or value:
                    raw_text_lines.append(f"{label}: {value}")
            raw_text_lines.append("")  # فاصله بین بخش‌ها

            for group in doc.get("LineItemGroups", []):
                for item in group.get("LineItems", []):
                    item_line = []
                    for field in item.get("LineItemExpenseFields", []):
                        name = field.get("Type", {}).get("Text", "")
                        val = field.get("ValueDetection", {}).get("Text", "")
                        if name and val:
                            item_line.append(f"{name}: {val}")
                    if item_line:
                        raw_text_lines.append(" | ".join(item_line))

        full_text = "\n".join(raw_text_lines).strip()

        task = {
            "data": {
                "text": full_text
            }
        }
        all_tasks.append(task)

with open(output_file, "w", encoding="utf-8") as out:
    json.dump(all_tasks, out, ensure_ascii=False, indent=2)

print(f"✅ Done! {len(all_tasks)} receipts converted to Label Studio format → {output_file}")
