import pandas as pd

from db_connection import get_db_connection


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

EXCEL_FILE = "data/LPP_Lookup.xlsx"
SHEET_NAME = 1   # Second sheet (0-based index)


# ---------------------------------------------------------
# Load and transform Excel
# ---------------------------------------------------------

def load_price_rules():
    """
    Read the pricing-rule table from the second Excel sheet
    and transform the wide format into database-ready rows.
    """

    # Read the second sheet
    df = pd.read_excel(
        EXCEL_FILE,
        sheet_name=SHEET_NAME
    )

    print("Excel data loaded successfully.")
    print(f"Rows found: {len(df)}")
    print(f"Columns found: {list(df.columns)}")

    # Make sure the first column exists
    if len(df.columns) < 2:
        raise ValueError(
            "Excel sheet must contain a subcategory column "
            "and at least one company column."
        )

    # Rename the first column to our standard name
    df = df.rename(
        columns={
            df.columns[0]: "subcategory"
        }
    )

    # Remove completely empty rows
    df = df.dropna(
        how="all"
    )

    # Convert wide format into long format
    price_rules = df.melt(
        id_vars=["subcategory"],
        var_name="company",
        value_name="reduction_percentage"
    )

    # Remove rows where the percentage is empty
    price_rules = price_rules.dropna(
        subset=["reduction_percentage"]
    )

    # -----------------------------------------------------
    # Clean text values
    # -----------------------------------------------------

    price_rules["subcategory"] = (
        price_rules["subcategory"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"^\d+\.\s*",
            "",
            regex=True
        )
    )

    price_rules["company"] = (
        price_rules["company"]
        .astype(str)
        .str.strip()
    )

    print(
        price_rules["reduction_percentage"].head(10)
    )

    # -----------------------------------------------------
    # Convert percentage to numeric
    # -----------------------------------------------------

    price_rules["reduction_percentage"] = (
        price_rules["reduction_percentage"]
        .astype(str)
        .str.strip()
        .str.replace(
            "%",
            "",
            regex=False
        )
    )

    price_rules["reduction_percentage"] = (
        pd.to_numeric(
            price_rules["reduction_percentage"],
            errors="coerce"
        ) * 100
    )

    # -----------------------------------------------------
    # Check for invalid percentages
    # -----------------------------------------------------

    invalid_percentage = price_rules[
        price_rules["reduction_percentage"].isna()
    ]

    if not invalid_percentage.empty:
        raise ValueError(
            "Invalid reduction percentage found in Excel."
        )

    # -----------------------------------------------------
    # Make sure required text fields are not empty
    # -----------------------------------------------------

    invalid_text = price_rules[
        (price_rules["subcategory"] == "")
        |
        (price_rules["company"] == "")
    ]

    if not invalid_text.empty:
        raise ValueError(
            "Empty company or subcategory found in Excel."
        )

    # -----------------------------------------------------
    # Check duplicate business keys
    # -----------------------------------------------------

    duplicates = price_rules[
        price_rules.duplicated(
            subset=[
                "company",
                "subcategory"
            ],
            keep=False
        )
    ]

    if not duplicates.empty:
        print("\nDuplicate pricing rules found:")
        print(
            duplicates.to_string(index=False)
        )

        raise ValueError(
            "Duplicate company + subcategory "
            "combinations found."
        )

    return price_rules


# ---------------------------------------------------------
# Insert into MySQL
# ---------------------------------------------------------

def insert_price_rules(price_rules):
    """
    Insert transformed pricing rules into PRICE_RULE table.
    """

    connection = get_db_connection()
    cursor = connection.cursor()

    insert_query = """
        INSERT INTO PRICE_RULE
        (
            company,
            subcategory,
            reduction_percentage
        )
        VALUES (%s, %s, %s)
    """

    try:

        # Convert DataFrame rows into tuples
        records = list(
            price_rules[
                [
                    "company",
                    "subcategory",
                    "reduction_percentage"
                ]
            ].itertuples(
                index=False,
                name=None
            )
        )

        cursor.executemany(
            insert_query,
            records
        )

        connection.commit()

        print(
            "\nPRICE_RULE table populated successfully."
        )

        print(
            f"Records processed: {len(records)}"
        )

        print(
            f"Records inserted: {cursor.rowcount}"
        )

    except Exception as error:

        connection.rollback()

        print(
            "\nDatabase insertion failed."
        )

        print(
            f"Error: {error}"
        )

        raise

    finally:

        cursor.close()
        connection.close()


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    print(
        "Starting Excel → PRICE_RULE pipeline...\n"
    )

    price_rules = load_price_rules()

    print(
        "\nTransformed pricing rules:"
    )

    print(
        price_rules.to_string(
            index=False
        )
    )

    insert_price_rules(
        price_rules
    )

    print(
        "\nPipeline completed."
    )


if __name__ == "__main__":
    main()