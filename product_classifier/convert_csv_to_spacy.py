
import spacy
from spacy.tokens import DocBin
import pandas as pd
import sys

def convert_csv_to_spacy(csv_path, output_path):
    df = pd.read_csv(csv_path)
    nlp = spacy.blank("en")
    doc_bin = DocBin()

    for _, row in df.iterrows():
        text = row["item"]
        label = row["category"]
        doc = nlp.make_doc(text)
        doc.cats = {label: 1.0}
        doc_bin.add(doc)

    doc_bin.to_disk(output_path)
    print(f"✅ فایل .spacy با موفقیت ساخته شد: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 convert_csv_to_spacy.py <input_csv> <output_spacy>")
        sys.exit(1)

    csv_input = sys.argv[1]
    spacy_output = sys.argv[2]
    convert_csv_to_spacy(csv_input, spacy_output)
