# File: API/backend_api.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import csv
import os # Import the os module for path manipulation

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.get("/api/profit-book")
def get_profit_book():
    # Construct the absolute path to profit_book.csv
    # This assumes profit_book.csv is in the parent directory of where backend_api.py resides.
    script_dir = os.path.dirname(__file__)
    profit_book_path = os.path.join(script_dir, "..", "profit_book.csv")

    try:
        with open(profit_book_path, "r") as f:
            reader = csv.DictReader(f)
            rows = []
            for r in reader:
                # Safely convert types, providing default values if a key is missing
                # This makes the API more robust to potentially malformed CSV rows
                r["filled_price"] = float(r.get("filled_price", 0.0))
                r["qty"] = int(r.get("qty", 0))
                r["notional"] = float(r.get("notional", 0.0))
                rows.append(r)
            return rows
    except FileNotFoundError:
        # Log a warning if the file is not found and return an empty list
        print(f"Warning: profit_book.csv not found at {profit_book_path}. Returning empty list.")
        return []
    except Exception as e:
        # Catch any other exceptions during file reading or data conversion
        print(f"Error reading profit_book.csv: {e}")
        return []

