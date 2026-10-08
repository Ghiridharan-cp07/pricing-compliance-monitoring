import json
from pathlib import Path

from db_connection import get_db_connection


# --------------------------------------------------
# Configuration
# --------------------------------------------------

JSON_FILE = Path("data/upload_74850445-e066-4347-b7d1-4f1aab478d6e.json")


# --------------------------------------------------
# Validation
# --------------------------------------------------

def validate_record(record, line_number):
    """
    Validate the structure of one JSON record.
    """

    # Check that the record is a dictionary
    if not isinstance(record, dict):
        raise ValueError(
            f"Line {line_number}: Record is not a JSON object."
        )

    # Check required keys
    required_keys = {"sku", "PL"}

    if not required_keys.issubset(record.keys()):
        raise ValueError(
            f"Line {line_number}: Missing SKU or PL key."
        )

    sku = record["sku"]
    pl = record["PL"]

    # Check SKU
    if not isinstance(sku, str) or not sku.strip():
        raise ValueError(
            f"Line {line_number}: Invalid SKU."
        )

    # Check PL
    if not isinstance(pl, str) or not pl.strip():
        raise ValueError(
            f"Line {line_number}: Invalid PL."
        )

    # Validate PL structure
    parts = pl.split("_")

    if len(parts) != 3:
        raise ValueError(
            f"Line {line_number}: Invalid PL format: {pl}"
        )

    # Make sure all three components contain something
    if any(not part.strip() for part in parts):
        raise ValueError(
            f"Line {line_number}: PL contains an empty component: {pl}"
        )

    return True


# --------------------------------------------------
# Extract subcategory
# --------------------------------------------------

def extract_subcategory(pl):
    """
    Extract the subcategory from a valid PL.

    Expected format:
        PREFIX_CATEGORY_SUBCATEGORY

    Example:
        HPON_PC_LAPTOP
        -> LAPTOP
    """

    parts = pl.split("_")

    return parts[2]


# --------------------------------------------------
# Read and transform JSON
# --------------------------------------------------

def load_and_transform_data():
    """
    Read JSONL data, validate each record,
    and prepare data for database insertion.
    """

    valid_records = []
    invalid_records = []

    with open(JSON_FILE, "r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            # Ignore completely empty lines
            if not line.strip():
                continue

            try:
                record = json.loads(line)

                # Validate original record
                validate_record(record, line_number)

                sku = record["sku"]
                pl = record["PL"]

                # Extract only the subcategory
                subcategory = extract_subcategory(pl)

                # IMPORTANT:
                # SKU and PL remain unchanged.
                transformed_record = (
                    sku,
                    pl,
                    subcategory
                )

                valid_records.append(transformed_record)

            except (json.JSONDecodeError, ValueError) as error:

                invalid_records.append(
                    str(error)
                )

    return valid_records, invalid_records


# --------------------------------------------------
# Insert into MySQL
# --------------------------------------------------
def insert_into_database(records):
    """
    Insert validated records into MAP_DB.PL.
    Duplicate SKUs are ignored.
    """

    connection = get_db_connection()
    cursor = connection.cursor()

    insert_query = """
        INSERT IGNORE INTO PL (SKU, PL, subcategory)
        VALUES (%s, %s, %s)
    """

    try:

        cursor.executemany(
            insert_query,
            records
        )

        connection.commit()

        print(
            f"Records successfully processed: {len(records)}"
        )
        print(
            f"Records actually inserted: {cursor.rowcount}"
        )
        print(
            f"Duplicate records skipped: "
            f"{len(records) - cursor.rowcount}"
        )

    except Exception as error:

        connection.rollback()

        print("Database insertion failed.")
        print(f"Error: {error}")

        raise

    finally:

        cursor.close()
        connection.close()


# --------------------------------------------------
# Main pipeline
# --------------------------------------------------

def main():

    print("Starting PL data pipeline...")

    valid_records, invalid_records = load_and_transform_data()

    print(f"Valid records   : {len(valid_records)}")
    print(f"Invalid records : {len(invalid_records)}")

    # Display invalid records
    if invalid_records:

        print("\nInvalid records:")

        for error in invalid_records:
            print(f"- {error}")

    # Insert only if valid records exist
    if valid_records:

        insert_into_database(valid_records)

    else:

        print("No valid records found. Nothing inserted.")

    print("\nPipeline completed.")


if __name__ == "__main__":
    main()