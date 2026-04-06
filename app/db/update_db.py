import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

def update_db():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        with open("app/db/trading_schema.sql", "r") as f:
            cur.execute(f.read())
            
        conn.commit()
        cur.close()
        conn.close()
        print("Trading Tables & Seed Money ($100k) Created!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_db()