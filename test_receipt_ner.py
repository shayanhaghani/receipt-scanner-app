import spacy

nlp = spacy.load("receipt_ner_model")

# یه نمونه رسید واقعی از دیتای آموزش
text = """
: FARM BOY ST CLAIR
-
81 St Clair Ave East
Toronto, Ontario
: 81 St Clair Ave East
: Toronto,
: Ontario
: FARM BOY
: 81 St Clair Ave East
Toronto, Ontario
: FARM BOY
Visa: $43.00
Manual item discount: $1.11
Temporary markdown: $3.66
SAVING GRAND TOTAL: $4.77
: 3/23/2025
Inv#:: 00260000
Net Sales: $43.00
TOTAL SALES: $43.00
SUB TOTAL: $43.00
: FARM BOY ST CLAIR
-
81 St Clair Ave East
Toronto, Ontario
: FARM BOY
: FARM BOY
Tel:: (416) - 963 8949
Your Store Manager is:: Philip Jones Jr.
Trs#:: 261736
[Tare:: 0.010 kgl 0.720 kg @ $6.59/kg
Markdown:: $1.60
Markdown:: $1.06
Markdown:: $1.00
Item discount:: $1.11
Balance: $0.00
New customer balance: $0.00
Item count: 13

ITEM: GRAPE GreenSeedless | PRICE: $4.74 | UNIT_PRICE: $1.60 | EXPENSE_ROW: GRAPE GreenSeedless $4.74
Markdown: $1.60
ITEM: Romaine Hearts | PRICE: $4.99 | EXPENSE_ROW: Romaine Hearts $4.99
ITEM: Eggplant Blkbell PK | PRICE: $3.91 | QUANTITY: 0.185 kg | UNIT_PRICE: $8.80/kg | EXPENSE_ROW: Eggplant Blkbell PK $3.91
0.185 kg @ $8.80/kg
ITEM: PEPPER Orange Bell | PRICE: $1.63 | QUANTITY: 0.395 kg | UNIT_PRICE: $3.90/kg | EXPENSE_ROW: PEPPER Orange Bell $1.63
0.395 kg @ $3.90/kg
ITEM: TOMATO Vine Ripe | PRICE: $1.54 | QUANTITY: 0.275 kg | UNIT_PRICE: $11.00/kg | EXPENSE_ROW: TOMATO Vine Ripe $1.54
Markdown: $1.06
0.275 kg @ $11.00/kg
ITEM: PLUM Black Reg | PRICE: $3.02 | EXPENSE_ROW: $3.02
PLUM Black Reg
ITEM: CORIANDER/CILANTRO
Markdown: $1.00 | PRICE: $0.99 | EXPENSE_ROW: $0.99
CORIANDER/CILANTRO
Markdown: $1.00
ITEM: Canadian Swiss Slc | PRICE: $5.87 | EXPENSE_ROW: Canadian Swiss Slc $5.87
ITEM: PORK SCHNITZEL | PRICE: $4.92 | EXPENSE_ROW: PORK SCHNITZEL $4.92
ITEM: PORK SCHNITZEL | PRICE: $4.42 | EXPENSE_ROW: PORK SCHNITZEL $4.42
Item discount: $1.11
ITEM: Pita Wheat 8" | PRICE: $1.99 | EXPENSE_ROW: Pita Wheat 8" $1.99
ITEM: Pita Wheat 10" | PRICE: $2.49 | EXPENSE_ROW: Pita Wheat 10" $2.49
ITEM: Pita Wheat10" | PRICE: $2.49 | EXPENSE_ROW: $2.49
Pita Wheat10"
"""

doc = nlp(text)

print("📌 موجودیت‌های شناسایی‌شده:")
found = False
for ent in doc.ents:
    print(f"{ent.text} → {ent.label_}")
    found = True

if not found:
    print("❌ هیچ موجودیتی شناسایی نشد.")
