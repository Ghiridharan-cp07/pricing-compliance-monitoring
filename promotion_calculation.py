import re
import pandas as pd

from db_connection import get_db_connection
from promotion_pipeline import prepare_promotion_data


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

EXCEL_FILE = "data/promotion_table.xlsx"  # Change this to your actual Excel file path.

# Change this if your promotion-rule sheet is different.
# 0 = first sheet, 1 = second sheet, 2 = third sheet.
PROMOTION_RULE_SHEET = 2

DEFAULT_SEASON = "Q4"


# --------------------------------------------------
# LOAD Q4 PROMOTION RULES
# --------------------------------------------------

def load_q4_promotion_rules(working_df):
    rules_df = pd.read_excel(
        EXCEL_FILE,
        sheet_name=PROMOTION_RULE_SHEET
    )

    if "Category" not in rules_df.columns:
        raise ValueError(
            "Category column not found in promotion-rule sheet."
        )

    q4_column = None

    for column in rules_df.columns:
        column_name = str(column).strip().upper()

        if column_name.startswith("Q4"):
            q4_column = column
            break

    if q4_column is None:
        raise ValueError(
            "Q4 promotion-rule column not found."
        )

    rules_df = rules_df[["Category", q4_column]].copy()

    rules_df = rules_df.rename(
        columns={q4_column: "Q4"}
    )

    rules_df["Category"] = (
        rules_df["Category"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    rules_df["Q4"] = (
        rules_df["Q4"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    subcategories = (
        working_df["subcategory"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .drop_duplicates()
        .tolist()
    )

    subcategories = sorted(
        subcategories,
        key=len,
        reverse=True
    )

    parsed_rules = []

    for _, row in rules_df.iterrows():

        category = row["Category"]
        q4_rule = row["Q4"]

        if not q4_rule:
            continue

        q4_rule_upper = q4_rule.upper()

        # Find a known subcategory in the rule
        matched_subcategory = None

        for subcategory in subcategories:
            if re.search(
                rf"\b{re.escape(subcategory)}\b",
                q4_rule_upper
            ):
                matched_subcategory = subcategory
                break

        # Check whether the rule contains an extra word
        # after "OFF" that is not a known subcategory.
        off_match = re.search(
            r"\bOFF\b\s*(.*)",
            q4_rule_upper
        )

        if (
            matched_subcategory is None
            and off_match
            and off_match.group(1).strip()
        ):
            print("\nSkipping invalid Q4 rule:")
            print(f"Category: {category}")
            print(f"Q4 Rule : {q4_rule}")
            print("Reason  : Unknown subcategory.")
            continue

        # Extract percentage or flat value
        percentage_match = re.search(
            r"(\d+(?:\.\d+)?)\s*%",
            q4_rule_upper
        )

        if percentage_match:
            promotion_type = "percentage"
            promotion_value = float(
                percentage_match.group(1)
            )

        else:
            amount_match = re.search(
                r"\$?\s*(\d+(?:\.\d+)?)",
                q4_rule_upper
            )

            if not amount_match:
                print("\nSkipping invalid Q4 rule:")
                print(f"Category: {category}")
                print(f"Q4 Rule : {q4_rule}")
                continue

            promotion_type = "flat"
            promotion_value = float(
                amount_match.group(1)
            )

        parsed_rules.append(
            {
                "category": category,
                "subcategory": matched_subcategory,
                "promotion_type": promotion_type,
                "promotion_value": promotion_value
            }
        )

    promotion_rules_df = pd.DataFrame(parsed_rules)

    if promotion_rules_df.empty:
        raise ValueError(
            "No valid Q4 promotion rules found."
        )

    duplicate_rules = (
        promotion_rules_df[
            promotion_rules_df.duplicated(
                subset=["category", "subcategory"],
                keep=False
            )
        ]
    )

    if not duplicate_rules.empty:
        print("\nDuplicate Q4 promotion rules:")
        print(
            duplicate_rules.to_string(index=False)
        )

        raise ValueError(
            "Duplicate Q4 rules found for "
            "the same category + subcategory."
        )

    print("\nQ4 promotion rules loaded:")
    print(
        promotion_rules_df.to_string(index=False)
    )
    print("RULE:", repr(q4_rule_upper))
    print("SUBCATEGORIES:", subcategories)
    print("MATCHED:", matched_subcategory)

    return promotion_rules_df

# --------------------------------------------------
# APPLY Q4 PROMOTION RULES
# --------------------------------------------------

def calculate_promotion(
    working_df,
    promotion_rules_df
):
    """
    Match category + subcategory with Q4 rules
    and calculate the final promotion value.
    """

    working_df = working_df.copy()

    working_df["category"] = (
        working_df["category"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    working_df["subcategory"] = (
        working_df["subcategory"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    working_df["season"] = DEFAULT_SEASON

    # Separate specific rules and category-wide rules.
    specific_rules = promotion_rules_df[
        promotion_rules_df["subcategory"].notna()
    ].copy()

    category_rules = promotion_rules_df[
        promotion_rules_df["subcategory"].isna()
    ].copy()

    # First match specific category + subcategory rules.
    result = working_df.merge(
        specific_rules,
        on=[
            "category",
            "subcategory"
        ],
        how="left"
    )

    # Match category-wide rules separately.
    category_rules = category_rules.rename(
        columns={
            "promotion_type": "category_promotion_type",
            "promotion_value": "category_promotion_value"
        }
    )

    result = result.merge(
        category_rules[
            [
                "category",
                "category_promotion_type",
                "category_promotion_value"
            ]
        ],
        on="category",
        how="left"
    )

    # If no specific rule exists,
    # use the category-wide rule.
    result["promotion_type"] = result[
        "promotion_type"
    ].fillna(
        result["category_promotion_type"]
    )

    result["promotion_value"] = result[
        "promotion_value"
    ].fillna(
        result["category_promotion_value"]
    )

    # Default to zero when there is no Q4 rule.
    result["promotion"] = 0.0

    percentage_mask = (
        result["promotion_type"]
        == "percentage"
    )

    flat_mask = (
        result["promotion_type"]
        == "flat"
    )

    result.loc[
        percentage_mask,
        "promotion"
    ] = (
        result.loc[
            percentage_mask,
            "MAP"
        ]
        * (
            1
            - result.loc[
                percentage_mask,
                "promotion_value"
            ] / 100
        )
    )

    result.loc[
        flat_mask,
        "promotion"
    ] = (
        result.loc[
            flat_mask,
            "MAP"
        ]
        - result.loc[
            flat_mask,
            "promotion_value"
        ]
    )

    result["promotion"] = (
        result["promotion"]
        .round(2)
    )

    print(
        "\nPromotion calculation completed."
    )

    print(
        result[
            [
                "SKU",
                "PL",
                "MAP",
                "category",
                "subcategory",
                "season",
                "promotion_type",
                "promotion_value",
                "promotion"
            ]
        ].to_string(index=False)
    )

    return result

# --------------------------------------------------
# PREPARE FINAL PROMOTION DATA
# --------------------------------------------------

def prepare_final_promotion_data():
    """
    Prepare final records required for PROMOTION table.
    """

    # Existing pipeline gives us:
    #
    # SKU
    # PL
    # MAP
    # LPP
    # category
    # subcategory
    # season

    working_df = prepare_promotion_data()

    print(
        f"\nPromotional working records: "
        f"{len(working_df)}"
    )

    promotion_rules_df = (
        load_q4_promotion_rules(
            working_df
        )
    )

    result = calculate_promotion(
        working_df,
        promotion_rules_df
    )

    final_df = result[
        [
            "SKU",
            "PL",
            "season",
            "promotion"
        ]
    ].copy()

   


    return final_df


# --------------------------------------------------
# CREATE PROMOTION TABLE
# --------------------------------------------------

def create_promotion_table(connection):
    """
    Create PROMOTION table.
    """

    cursor = connection.cursor()

    query = """
        CREATE TABLE IF NOT EXISTS PROMOTION (
            SKU VARCHAR(100) NOT NULL,
            PL VARCHAR(100) NOT NULL,
            season VARCHAR(20) NOT NULL,
            promotion DECIMAL(12,2) NOT NULL,

            CONSTRAINT uq_promotion_sku_pl
            UNIQUE (SKU, PL)
        )
    """

    cursor.execute(query)

    connection.commit()

    cursor.close()

    print(
        "\nPROMOTION table ready."
    )


# --------------------------------------------------
# INSERT PROMOTION DATA
# --------------------------------------------------

def insert_promotion_data(
    connection,
    df
):
    """
    Insert final promotion records.
    """

    cursor = connection.cursor()

    query = """
        INSERT INTO PROMOTION
        (
            SKU,
            PL,
            season,
            promotion
        )
        VALUES
        (%s, %s, %s, %s)
    """

    records = [
        (
            row["SKU"],
            row["PL"],
            row["season"],
            row["promotion"]
        )
        for _, row in df.iterrows()
    ]

    cursor.executemany(
        query,
        records
    )

    connection.commit()

    print(
        f"\nPromotion records inserted: "
        f"{cursor.rowcount}"
    )

    cursor.close()


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    print(
        "\nStarting promotion calculation..."
    )

    final_df = (
        prepare_final_promotion_data()
    )

    print(
        "\nFinal PROMOTION data:"
    )

    print(
        final_df.to_string(
            index=False
        )
    )

    connection = get_db_connection()

    try:

        create_promotion_table(
            connection
        )

        insert_promotion_data(
            connection,
            final_df
        )

    finally:

        connection.close()

    print(
        "\nPromotion pipeline completed."
    )


if __name__ == "__main__":
    main()