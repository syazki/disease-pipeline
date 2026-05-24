import requests
import zipfile
import io
import pandas as pd
from datetime import datetime, timezone
from pipeline.db import get_connection

URL = "https://www150.statcan.gc.ca/n1/tbl/csv/17100009-eng.zip"
TABLE_NAME = "bronze_population"

def create_table(cursor):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id          SERIAL PRIMARY KEY,
            year        INTEGER,
            province    TEXT,
            population  INTEGER,
            ingested_at TIMESTAMP WITH TIME ZONE
        );
    """)

def ingest():
    print("Downloading population data from Statistics Canada...")
    response = requests.get(URL)
    z = zipfile.ZipFile(io.BytesIO(response.content))
    df = pd.read_csv(z.open("17100009.csv"))

    # keep only what we need
    df = df[["REF_DATE", "GEO", "VALUE"]].copy()
    df.columns = ["ref_date", "province", "population"]

    # extract year from ref_date (e.g. "2020-01" → 2020)
    df["year"] = df["ref_date"].str[:4].astype(int)

    # drop rows with missing population
    df = df.dropna(subset=["population"])

    # average quarterly figures into one annual number per province
    df_annual = (
        df.groupby(["year", "province"])["population"]
        .mean()
        .round()
        .astype(int)
        .reset_index()
    )

    # filter to years that overlap with our disease data
    df_annual = df_annual[df_annual["year"].between(1991, 2023)]

    ingested_at = datetime.now(timezone.utc)

    conn = get_connection()
    cursor = conn.cursor()

    create_table(cursor)

    inserted = 0
    for _, row in df_annual.iterrows():
        cursor.execute(f"""
            INSERT INTO {TABLE_NAME}
                (year, province, population, ingested_at)
            VALUES
                (%s, %s, %s, %s)
        """, (
            int(row["year"]),
            row["province"],
            int(row["population"]),
            ingested_at
        ))
        inserted += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Done. {inserted} rows inserted into {TABLE_NAME}.")

if __name__ == "__main__":
    ingest()