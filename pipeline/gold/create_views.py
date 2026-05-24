from pipeline.db import get_connection

def create_views():
    conn = get_connection()
    cursor = conn.cursor()

    print("Creating Gold views...")

    # View 1: disease trend with 5-year rolling average
    cursor.execute("""
        CREATE OR REPLACE VIEW gold_disease_trend AS
        SELECT
            year,
            disease,
            cases,
            rate_per_100k,
            canada_population,
            ROUND(
                AVG(cases) OVER (
                    PARTITION BY disease
                    ORDER BY year
                    ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                )
            , 2) AS rolling_avg_5yr,
            cases - LAG(cases) OVER (
                PARTITION BY disease ORDER BY year
            ) AS yoy_change
        FROM silver_disease_cases
        ORDER BY disease, year;
    """)

    # View 2: climate correlation
    cursor.execute("""
        CREATE OR REPLACE VIEW gold_climate_correlation AS
        SELECT
            year,
            disease,
            cases,
            rate_per_100k,
            temperature_anomaly,
            ROUND(temperature_anomaly::numeric, 2) AS temp_anomaly_rounded
        FROM silver_disease_cases
        ORDER BY disease, year;
    """)

    # View 3: anomaly flag — years where cases > 2x the rolling average
    cursor.execute("""
        CREATE OR REPLACE VIEW gold_anomaly_flag AS
        WITH base AS (
            SELECT
                year,
                disease,
                cases,
                ROUND(
                    AVG(cases) OVER (
                        PARTITION BY disease
                        ORDER BY year
                        ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
                    )
                , 2) AS rolling_avg_5yr
            FROM silver_disease_cases
        )
        SELECT
            year,
            disease,
            cases,
            rolling_avg_5yr,
            CASE
                WHEN rolling_avg_5yr > 0 AND cases > rolling_avg_5yr * 2
                THEN true
                ELSE false
            END AS is_anomaly
        FROM base
        ORDER BY disease, year;
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("Done. Three Gold views created:")
    print("  - gold_disease_trend")
    print("  - gold_climate_correlation")
    print("  - gold_anomaly_flag")

if __name__ == "__main__":
    create_views()