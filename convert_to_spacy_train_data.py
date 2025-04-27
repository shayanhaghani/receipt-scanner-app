import json

# مسیر فایل خروجی Label Studio
input_file = "exported_labelstudio.json"  # ← اسم فایل خروجی که از Label Studio گرفتی
output_file = "train_data_spacy.json"

with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

train_data = []

for item in data:
    text = item.get("data", {}).get("text", "")
    entities = []

    annotations = item.get("annotations", [])
    if annotations:
        results = annotations[0].get("result", [])
        for r in results:
            if r["type"] == "labels":
                start = r["value"]["start"]
                end = r["value"]["end"]
                label = r["value"]["labels"][0]
                entities.append((start, end, label))

    if text and entities:
        train_data.append((text, {"entities": entities}))

# ذخیره فایل خروجی نهایی
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(train_data, f, ensure_ascii=False, indent=2)

print(f"✅ Done! {len(train_data)} samples saved in {output_file}")
