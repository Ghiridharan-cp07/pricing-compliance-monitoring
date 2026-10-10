import xml.etree.ElementTree as ET

from db_connection import get_db_connection


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

XML_FILE = "data/sku_data.xml"


# --------------------------------------------------
# LOAD AND PARSE SKU DATA
# --------------------------------------------------

def load_sku_data():

    tree = ET.parse(XML_FILE)
    root = tree.getroot()

    records = []

    for item in root.findall(".//item"):

        pn_element = item.find("PN")
        sku_element = item.find("Sku")

        if (
            pn_element is None
            or sku_element is None
        ):
            print(
                "\nSkipping item because "
                "PN or SKU is missing."
            )
            continue

        pn = (
            pn_element.text or ""
        ).strip().upper()

        sku = (
            sku_element.text or ""
        ).strip().upper()

        if not pn or not sku:
            print(
                "\nSkipping item because "
                "PN or SKU is empty."
            )
            continue

        records.append(
            (
                pn,
                sku
            )
        )

    if not records:
        raise ValueError(
            "No valid PN and SKU records found."
        )

    print(
        f"Valid SKU records loaded: {len(records)}"
    )

    return records


# --------------------------------------------------
# CREATE SKU TABLE
# --------------------------------------------------

def create_sku_table(connection):

    query = """
        CREATE TABLE IF NOT EXISTS SKU (
            PN VARCHAR(100) NOT NULL,
            SKU VARCHAR(100) NOT NULL,

            CONSTRAINT uq_sku_pn
            UNIQUE (PN, SKU)
        )
    """

    cursor = connection.cursor()

    try:
        cursor.execute(query)
        connection.commit()

    finally:
        cursor.close()


# --------------------------------------------------
# INSERT SKU DATA
# --------------------------------------------------

def insert_sku_data(
    connection,
    records
):

    query = """
        INSERT INTO SKU (
            PN,
            SKU
        )
        VALUES (%s, %s)

        ON DUPLICATE KEY UPDATE
            SKU = VALUES(SKU)
    """

    cursor = connection.cursor()

    try:
        cursor.executemany(
            query,
            records
        )

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
        "\nStarting SKU pipeline..."
    )

    records = load_sku_data()

    connection = get_db_connection()

    try:

        create_sku_table(
            connection
        )

        insert_sku_data(
            connection,
            records
        )

        print(
            "SKU pipeline completed."
        )

    finally:
        connection.close()


if __name__ == "__main__":
    main()