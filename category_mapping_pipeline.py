import pandas as pd

from db_connection import get_db_connection


# --------------------------------------------------
# LOAD PL DATA
# --------------------------------------------------

def load_pl_data(connection):
    query = """
        SELECT SKU, PL, subcategory
        FROM PL
    """

    df = pd.read_sql(query, connection)

    if df.empty:
        raise ValueError("PL table is empty.")

    print(f"PL records loaded: {len(df)}")

    return df


# --------------------------------------------------
# PREPARE CATEGORY MAPPING DATA
# --------------------------------------------------

def prepare_category_mapping(pl_df):

    df = pl_df.copy()

    # Extract category from the middle
    # part of the PL.
    pl_parts = (
        df["PL"]
        .astype(str)
        .str.strip()
        .str.split("_")
    )

    df["category"] = pl_parts.str[1]

    # Keep only required columns.
    df = df[
        [
            "SKU",
            "PL",
            "category",
            "subcategory"
        ]
    ].copy()

    # Validate category extraction.
    if df["category"].isna().any():
        raise ValueError(
            "Category could not be extracted "
            "from one or more PL values."
        )

    print(
        f"Category mapping records prepared: {len(df)}"
    )

    return df


# --------------------------------------------------
# CREATE CATEGORY MAPPING TABLE
# --------------------------------------------------

def create_category_mapping_table(connection):

    query = """
        CREATE TABLE IF NOT EXISTS CATEGORY_MAPPING (
            SKU VARCHAR(100) NOT NULL,
            PL VARCHAR(100) NOT NULL,
            category VARCHAR(100) NOT NULL,
            subcategory VARCHAR(100) NOT NULL,

            CONSTRAINT uq_category_mapping_sku_pl
            UNIQUE (SKU, PL)
        )
    """

    cursor = connection.cursor()

    try:
        cursor.execute(query)
        connection.commit()

    finally:
        cursor.close()


# --------------------------------------------------
# INSERT CATEGORY MAPPING DATA
# --------------------------------------------------

def insert_category_mapping(
    connection,
    df
):

    query = """
        INSERT INTO CATEGORY_MAPPING (
            SKU,
            PL,
            category,
            subcategory
        )
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            category = VALUES(category),
            subcategory = VALUES(subcategory)
    """

    records = [
        (
            row["SKU"],
            row["PL"],
            row["category"],
            row["subcategory"]
        )
        for _, row in df.iterrows()
    ]

    cursor = connection.cursor()

    try:
        cursor.executemany(query, records)
        connection.commit()

        print(
            f"Records processed: {len(records)}"
        )

    finally:
        cursor.close()


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print(
        "\nStarting Category Mapping pipeline..."
    )

    connection = get_db_connection()

    try:

        # 1. Load existing PL table
        pl_df = load_pl_data(connection)

        # 2. Derive category
        mapping_df = prepare_category_mapping(
            pl_df
        )

        # 3. Create table
        create_category_mapping_table(
            connection
        )

        # 4. Insert data
        insert_category_mapping(
            connection,
            mapping_df
        )

        print(
            "Category Mapping pipeline completed."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()