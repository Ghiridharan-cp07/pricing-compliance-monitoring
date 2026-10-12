from lpp_data import prepare_lpp_data
from db_connection import get_db_connection


def calculate_lpp(df):
    """Calculate LPP for valid records."""

    df = df.copy()

    df["LPP"] = (
        df["MAP"]
        * (
            1 -
            df["reduction_percentage"] / 100
        )
    )

    df["LPP"] = df["LPP"].round(2)

    print("\nLPP calculation completed.")

    return df


def final_validation(df):
    """Validate final records before insertion."""

    required_columns = {
        "sku",
        "PL",
        "MAP",
        "LPP"
    }

    missing_columns = (
        required_columns - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Missing final columns: {missing_columns}"
        )

    null_rows = df[
        df[
            [
                "sku",
                "PL",
                "MAP",
                "LPP"
            ]
        ].isna().any(axis=1)
    ]

    if not null_rows.empty:
        print("\nRows containing NULL values:")
        print(
            null_rows.to_string(index=False)
        )
        raise ValueError(
            "NULL values found in final result."
        )

    if (df["LPP"] < 0).any():
        raise ValueError(
            "Negative LPP value found."
        )

    print("Final validation passed.")


def create_price_list_table(connection):
    """Create PRICE_LIST if it does not exist."""

    query = """
        CREATE TABLE IF NOT EXISTS PRICE_LIST (
           SKU VARCHAR(100) NOT NULL,
            PL VARCHAR(100) NOT NULL,
            MAP DECIMAL(12,2) NOT NULL,
            LPP DECIMAL(12,2) NOT NULL,

            CONSTRAINT uq_price_list_sku_pl
            UNIQUE (SKU, PL)
)
    """

    cursor = connection.cursor()

    try:
        cursor.execute(query)
        connection.commit()
        print("PRICE_LIST table is ready.")
    finally:
        cursor.close()


def insert_price_list(connection, df):
    """Insert valid records into PRICE_LIST."""

    insert_query = """
        INSERT INTO PRICE_LIST
        (
            SKU,
            PL,
            MAP,
            LPP
        )
        VALUES (%s, %s, %s, %s)
    """

    records = list(
        df[
            [
                "sku",
                "PL",
                "MAP",
                "LPP"
            ]
        ].itertuples(
            index=False,
            name=None
        )
    )

    cursor = connection.cursor()

    try:
        cursor.executemany(
            insert_query,
            records
        )

        connection.commit()

        print(
            f"\nInserted into PRICE_LIST: "
            f"{cursor.rowcount} records"
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()


def main():

    print("\nStarting LPP pipeline...")

    working_df = prepare_lpp_data()

    working_df = calculate_lpp(
        working_df
    )

    final_validation(
        working_df
    )

    print("\nFinal preview:")

    print(
        working_df[
            [
                "sku",
                "PL",
                "MAP",
                "company",
                "subcategory",
                "reduction_percentage",
                "LPP"
            ]
        ].to_string(index=False)
    )

    connection = get_db_connection()

    try:
        create_price_list_table(
            connection
        )

        insert_price_list(
            connection,
            working_df
        )

    finally:
        connection.close()

    print("\nLPP pipeline completed successfully.")


if __name__ == "__main__":
    main()