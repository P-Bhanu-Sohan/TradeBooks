from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import csv

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.get("/api/profit-book")
def get_profit_book():
    with open("profit_book.csv", "r") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            r["filled_price"] = float(r["filled_price"])
            r["qty"] = int(r["qty"])
            r["notional"] = float(r["notional"])
            rows.append(r)
        return rows
