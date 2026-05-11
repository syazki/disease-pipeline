import pandas as pd
import os
from datetime import datetime, timezone
from pipeline.db import get_connection

FILE_PATH = os.path.join("data", "raw", "export", "Data.csv")
TABLE_NAME = "bronze_disease_cases"

def create_table(cursor):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id              SERIAL PRIMARY KEY,
            year            INTEGER,
            disease         TEXT,
            age_group       TEXT,
            sex             TEXT,
            cases           INTEGER,
            rate_per_100k   NUMERIC(6, 2),
            ingested_at     TIMESTAMP WITH TIME ZONE
        );
    """)

def ingest():
    print(f"Reading {FILE_PATH}...")
    df = pd.read_csv(FILE_PATH)

    df.columns = ["year", "disease", "age_group", "sex", "cases", "rate_per_100k"]

    ingested_at = datetime.now(timezone.utc)

    conn = get_connection()
    cursor = conn.cursor()

    create_table(cursor)

    inserted = 0
    for _, row in df.iterrows():
        cursor.execute(f"""
            INSERT INTO {TABLE_NAME}
                (year, disease, age_group, sex, cases, rate_per_100k, ingested_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
        """, (
            int(row["year"]),
            row["disease"],
            row["age_group"],
            row["sex"],
            None if pd.isna(row["cases"]) else int(row["cases"]),
            None if pd.isna(row["rate_per_100k"]) else float(row["rate_per_100k"]),
            ingested_at
        ))
        inserted += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Done. {inserted} rows inserted into {TABLE_NAME}.")

if __name__ == "__main__":
    ingest()