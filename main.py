from fastapi import FastAPI
import csv
from fastapi.middleware.cors import CORSMiddleware
from backend.config import ORDER_BOOK_PATH

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Shikshak Securities HFT System"}

@app.get("/api/profit-book")
def profit_book():
    try:
        with open(ORDER_BOOK_PATH) as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return {"error": "Order book not found"}