import pandas as pd
from datetime import datetime, timezone
from pipeline.db import get_connection

TABLE_NAME = "silver_disease_cases"

def create_table(cursor):
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id                   SERIAL PRIMARY KEY,
            year                 INTEGER,
            disease              TEXT,
            cases                INTEGER,
            rate_per_100k        NUMERIC(6, 2),
            temperature_anomaly  NUMERIC(8, 6),
            canada_population    INTEGER,
            transformed_at       TIMESTAMP WITH TIME ZONE,
            UNIQUE (year, disease)
        );
    """)

def transform():
    print("Reading from Bronze tables...")
    conn = get_connection()
    cursor = conn.cursor()

    create_table(cursor)

    # read all three bronze tables into pandas
    disease_df = pd.read_sql("SELECT year, disease, cases, rate_per_100k FROM bronze_disease_cases", conn)
    climate_df = pd.read_sql("SELECT year, temperature_anomaly FROM bronze_climate", conn)
    population_df = pd.read_sql("SELECT year, population FROM bronze_population WHERE province = 'Canada'", conn)

    # clean disease data
    # drop rows where both cases and rate are null (pre-2000 hantavirus etc)
    disease_df = disease_df.dropna(subset=["cases", "rate_per_100k"], how="all")

    # fill remaining nulls with 0 (e.g. years with 0 reported cases)
    disease_df["cases"] = disease_df["cases"].fillna(0).astype(int)
    disease_df["rate_per_100k"] = disease_df["rate_per_100k"].fillna(0.0)

    # join climate and population onto disease by year
    df = disease_df.merge(climate_df, on="year", how="left")
    df = df.merge(population_df, on="year", how="left")
    df = df.rename(columns={"population": "canada_population"})

    # filter to years where we have all three sources
    df = df.dropna(subset=["temperature_anomaly", "canada_population"])
    df["canada_population"] = df["canada_population"].astype(int)

    transformed_at = datetime.now(timezone.utc)

    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        cursor.execute(f"""
            INSERT INTO {TABLE_NAME}
                (year, disease, cases, rate_per_100k, temperature_anomaly, canada_population, transformed_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (year, disease) DO UPDATE SET
                cases               = EXCLUDED.cases,
                rate_per_100k       = EXCLUDED.rate_per_100k,
                temperature_anomaly = EXCLUDED.temperature_anomaly,
                canada_population   = EXCLUDED.canada_population,
                transformed_at      = EXCLUDED.transformed_at;
        """, (
            int(row["year"]),
            row["disease"],
            int(row["cases"]),
            float(row["rate_per_100k"]),
            float(row["temperature_anomaly"]),
            int(row["canada_population"]),
            transformed_at
        ))
        inserted += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Done. {inserted} rows upserted into {TABLE_NAME}.")

if __name__ == "__main__":
    transform()