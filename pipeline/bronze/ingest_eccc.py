import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timezone
from pipeline.db import get_connection

URL = "https://ourworldindata.org/grapher/annual-temperature-anomalies.csv"
PARAMS = {
    "v": "1",
    "csvType": "full",
    "useColumnShortNames": "true",
}
HEADERS = {"User-Agent": "Our World In Data data fetch/1.0"}
TABLE_NAME = "bronze_climate"

def create_table(cursor):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id                  SERIAL PRIMARY KEY,
            entity              TEXT,
            code                TEXT,
            year                INTEGER,
            temperature_anomaly NUMERIC(8, 6),
            ingested_at         TIMESTAMP WITH TIME ZONE
        );
    """)

def ingest():
    print("Downloading climate data from Our World in Data...")
    response = requests.get(URL, params=PARAMS, headers=HEADERS)
    df = pd.read_csv(StringIO(response.text))

    df_canada = df[df["code"] == "CAN"].copy()
    df_canada.columns = ["entity", "code", "year", "temperature_anomaly"]

    ingested_at = datetime.now(timezone.utc)

    conn = get_connection()
    cursor = conn.cursor()

    create_table(cursor)

    inserted = 0
    for _, row in df_canada.iterrows():
        cursor.execute(f"""
            INSERT INTO {TABLE_NAME}
                (entity, code, year, temperature_anomaly, ingested_at)
            VALUES
                (%s, %s, %s, %s, %s)
        """, (
            row["entity"],
            row["code"],
            int(row["year"]),
            float(row["temperature_anomaly"]),
            ingested_at
        ))
        inserted += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Done. {inserted} rows inserted into {TABLE_NAME}.")

if __name__ == "__main__":
    ingest()