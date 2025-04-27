import spacy
import json
from spacy.training.example import Example

# مسیر فایل دیتای آموزشی
train_file = "train_data_spacy.json"

# لود داده‌ها
with open(train_file, "r", encoding="utf-8") as f:
    train_data = json.load(f)

# ساخت مدل خالی انگلیسی
nlp = spacy.blank("en")

# اضافه کردن pipeline مربوط به NER
ner = nlp.add_pipe("ner")

# ثبت همه لیبل‌ها در مدل
for text, annot in train_data:
    for start, end, label in annot["entities"]:
        ner.add_label(label)

# آموزش مدل
nlp.begin_training()

for itn in range(30):  # تعداد epoch
    print(f"🔁 Iteration {itn+1}")
    for text, annot in train_data:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annot)
        nlp.update([example])

# ذخیره مدل
output_dir = "receipt_ner_model"
nlp.to_disk(output_dir)
print(f"✅ مدل ذخیره شد در پوشه: {output_dir}")
