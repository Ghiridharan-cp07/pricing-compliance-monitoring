import pandas as pd

from db_connection import get_db_connection


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

EXCEL_FILE = "data/seller mapping table.xlsx"
SELLER_MAPPING_SHEET = 0


# --------------------------------------------------
# LOAD SELLER MAPPING DATA
# --------------------------------------------------

def load_seller_mapping():

    df = pd.read_excel(
        EXCEL_FILE,
        sheet_name=SELLER_MAPPING_SHEET
    )

    required_columns = {
        "Sellers_Name",
        "Homologated_Name"
    }

    missing_columns = (
        required_columns - set(df.columns)
    )

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    df = df[
        [
            "Sellers_Name",
            "Homologated_Name"
        ]
    ].copy()

    # Remove unnecessary spaces.
    df["Sellers_Name"] = (
        df["Sellers_Name"]
        .astype(str)
        .str.strip()
    )

    df["Homologated_Name"] = (
        df["Homologated_Name"]
        .astype(str)
        .str.strip()
    )

    # Remove completely empty rows.
    df = df[
        (df["Sellers_Name"] != "")
        & (df["Homologated_Name"] != "")
    ]

    print(
        f"Seller mapping records loaded: {len(df)}"
    )

    return df


# --------------------------------------------------
# CREATE SELLER MAPPING TABLE
# --------------------------------------------------

def create_seller_mapping_table(connection):

    query = """
        CREATE TABLE IF NOT EXISTS SELLER_MAPPING (
            Sellers_Name VARCHAR(255) NOT NULL,
            Homologated_Name VARCHAR(255) NOT NULL
        )
    """

    cursor = connection.cursor()

    try:
        cursor.execute(query)
        connection.commit()

    finally:
        cursor.close()


# --------------------------------------------------
# INSERT SELLER MAPPING DATA
# --------------------------------------------------

def insert_seller_mapping(
    connection,
    df
):

    query = """
        INSERT INTO SELLER_MAPPING (
            Sellers_Name,
            Homologated_Name
        )
        VALUES (%s, %s)
    """

    records = [
        (
            row["Sellers_Name"],
            row["Homologated_Name"]
        )
        for _, row in df.iterrows()
    ]

    cursor = connection.cursor()

    try:
        cursor.executemany(
            query,
            records
        )

        connection.commit()

        print(
            f"Records inserted: {len(records)}"
        )

    finally:
        cursor.close()


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print(
        "\nStarting Seller Mapping pipeline..."
    )

    df = load_seller_mapping()

    connection = get_db_connection()

    try:

        create_seller_mapping_table(
            connection
        )

        insert_seller_mapping(
            connection,
            df
        )

        print(
            "Seller Mapping pipeline completed."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()