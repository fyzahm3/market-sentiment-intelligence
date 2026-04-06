import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

def init_db():
    if not DB_URL:
        print("Error: DATABASE_URL not found in .env file")
        return 
    try:
        print("Connecting to database....")
        conn=psycopg2.connect(DB_URL)
        cur=conn.cursor()

        print("Reading schemas.sql....")
        with open("app/db/schemas.sql", "r") as f:
            schema=f.read()


        print("Executing SQL commands")
        cur.execute(schema)

        conn.commit()

        cur.close()
        conn.close()
        print("Success! Table 'sentiment_results' is created.")
    except Exception as e:
        print(f"Database error:{e}")

if __name__ == "__main__":
    init_db()


