import boto3
from typing import Any, Dict

# Configuration for AWS Textract region
from config import AWS_REGION

def get_textract_client() -> Any:
    """Return a configured Textract client."""
    return boto3.client("textract", region_name=AWS_REGION)

def call_expense_analyzer(image_bytes: bytes) -> Dict[str, Any]:
    """
    Send image bytes to AWS Textract Expense API and return raw response.
    """
    client = get_textract_client()
    return client.analyze_expense(Document={"Bytes": image_bytes})

def parse_expense_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform Textract Expense response into a structured dict:
    {
        "store_name": str,
        "store_address": str,
        "date": str,
        "phone": str,
        "items": {
            item_name: {"price": float, "count": int}, ...
        }
    }
    """
    data = {
        "store_name": None,
        "store_address": None,
        "date": None,
        "phone": None,
        "items": {}
    }

    # Extract the first ExpenseDocument if available
    docs = resp.get("ExpenseDocuments", [])
    if not docs:
        return data
    doc = docs[0]

    # Extract summary fields (vendor name, address, date, phone)
    for fld in doc.get("SummaryFields", []):
        t = fld.get("Type", {}).get("Text", "")
        v = fld.get("ValueDetection", {}).get("Text", "")
        if t == "VENDOR_NAME":
            data["store_name"] = v
        elif t == "VENDOR_ADDRESS":
            data["store_address"] = v
        elif t == "INVOICE_RECEIPT_DATE":
            data["date"] = v
        elif t == "SUPPLIER_PHONE":
            data["phone"] = v

    # Extract line items with price and quantity
    for group in doc.get("LineItemGroups", []):
        for item in group.get("LineItems", []):
            name = price = count = None
            for lf in item.get("LineItemExpenseFields", []):
                tp = lf.get("Type", {}).get("Text", "")
                va = lf.get("ValueDetection", {}).get("Text", "")
                if tp == "ITEM":
                    name = va
                elif tp == "PRICE":
                    try:
                        price = float(va.replace("$", "").replace(",", ""))
                    except ValueError:
                        price = None
                elif tp == "QUANTITY":
                    try:
                        count = int(va)
                    except ValueError:
                        count = 1
            if name:
                data["items"][name] = {"price": price, "count": count or 1}

    return data
