import yaml
import pandas as pd

from db_connection import get_db_connection


YAML_FILE = "data/price_list.yaml"


def load_yaml():
    """Load SKU, PL and MAP records from YAML."""

    with open(YAML_FILE, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not data:
        raise ValueError("YAML file is empty.")

    if not isinstance(data, list):
        raise ValueError("Expected YAML to contain a list of records.")

    print(f"YAML records loaded: {len(data)}")

    return data


def prepare_yaml_data(records):
    """Validate and prepare YAML data."""

    df = pd.DataFrame(records)

    required_columns = {"sku", "PL", "MAP"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing YAML columns: {missing_columns}"
        )

    df = df[["sku", "PL", "MAP"]].copy()

    df["sku"] = df["sku"].astype(str).str.strip()
    df["PL"] = df["PL"].astype(str).str.strip()

    df["MAP"] = pd.to_numeric(
        df["MAP"],
        errors="coerce"
    )

    invalid_text = df[
        (df["sku"] == "") |
        (df["PL"] == "")
    ]

    if not invalid_text.empty:
        raise ValueError("Empty SKU or PL found in YAML.")

    invalid_map = df[df["MAP"].isna()]

    if not invalid_map.empty:
        print("\nInvalid MAP records:")
        print(invalid_map.to_string(index=False))
        raise ValueError("Invalid MAP value found in YAML.")

    print("YAML validation passed.")

    return df


def load_pl_data(connection):
    """Load SKU, PL and subcategory from PL."""

    query = """
        SELECT
            SKU,
            PL,
            subcategory
        FROM PL
    """

    df = pd.read_sql(query, connection)

    if df.empty:
        raise ValueError("PL table is empty.")

    print(f"PL master records loaded: {len(df)}")

    return df


def load_price_rules(connection):
    """Load pricing rules from PRICE_RULE."""

    query = """
        SELECT
            company,
            subcategory,
            reduction_percentage
        FROM PRICE_RULE
    """

    df = pd.read_sql(query, connection)

    if df.empty:
        raise ValueError("PRICE_RULE table is empty.")

    df["company"] = (
        df["company"]
        .astype(str)
        .str.strip()
    )

    df["subcategory"] = (
        df["subcategory"]
        .astype(str)
        .str.strip()
    )

    df["reduction_percentage"] = pd.to_numeric(
        df["reduction_percentage"],
        errors="coerce"
    )

    invalid_percentage = df[
        df["reduction_percentage"].isna()
    ]

    if not invalid_percentage.empty:
        print("\nInvalid PRICE_RULE percentages:")
        print(invalid_percentage.to_string(index=False))
        raise ValueError(
            "Invalid reduction percentage found."
        )

    print(f"PRICE_RULE records loaded: {len(df)}")

    return df


def derive_company(pl_df, price_rules_df):
    """
    Derive company temporarily from PL.
    Company is not stored in PL or PRICE_LIST.
    """

    companies = (
        price_rules_df["company"]
        .drop_duplicates()
        .tolist()
    )

    companies = sorted(
        companies,
        key=len,
        reverse=True
    )

    def find_company(pl_value):
        pl_value = str(pl_value).strip()

        for company in companies:
            if pl_value.upper().startswith(
                company.upper()
            ):
                return company

        return None

    pl_df["company"] = pl_df["PL"].apply(
        find_company
    )

    return pl_df


def match_yaml_with_pl(yaml_df, pl_df):
    """Match YAML records with PL using SKU + PL."""

    master_df = pl_df[
        [
            "SKU",
            "PL",
            "subcategory",
            "company"
        ]
    ].copy()

    yaml_df = yaml_df.copy()

    yaml_df["_sku_key"] = (
        yaml_df["sku"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    master_df["_sku_key"] = (
        master_df["SKU"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    master_df = master_df.rename(
        columns={"PL": "PL_master"}
    )

    merged_df = yaml_df.merge(
        master_df[
            [
                "_sku_key",
                "SKU",
                "PL_master",
                "subcategory",
                "company"
            ]
        ],
        left_on=[
            "_sku_key",
            "PL"
        ],
        right_on=[
            "_sku_key",
            "PL_master"
        ],
        how="left",
        indicator=True
    )

    missing_match = merged_df[
        merged_df["_merge"] != "both"
    ].copy()

    if not missing_match.empty:
        print(
            "\nSKU + PL combinations not found "
            "in PL table:"
        )

        print(
            missing_match[
                [
                    "sku",
                    "PL",
                    "MAP"
                ]
            ].to_string(index=False)
        )

        raise ValueError(
            "Some YAML SKU + PL combinations "
            "do not exist in PL."
        )

    result = merged_df[
        [
            "sku",
            "PL",
            "MAP",
            "subcategory",
            "company"
        ]
    ].copy()

    print("YAML → PL matching passed.")

    return result


def apply_price_rules(
    working_df,
    price_rules_df
):
    """Match company + subcategory with PRICE_RULE."""

    result = working_df.merge(
        price_rules_df,
        on=[
            "company",
            "subcategory"
        ],
        how="left"
    )

    unknown_rules = result[
        result["reduction_percentage"].isna()
    ].copy()

    if not unknown_rules.empty:
        print("\nSkipping records with no PRICE_RULE:")
        print(
            unknown_rules[
                [
                    "sku",
                    "PL",
                    "company",
                    "subcategory",
                    "MAP"
                ]
            ].to_string(index=False)
        )

    valid_records = result[
        result["reduction_percentage"].notna()
    ].copy()

    print(f"\nValid records: {len(valid_records)}")
    print(f"Skipped records: {len(unknown_rules)}")

    if valid_records.empty:
        raise ValueError(
            "No valid records remain after PRICE_RULE validation."
        )

    return valid_records


def prepare_lpp_data():
    """Prepare all validated data required for LPP calculation."""

    records = load_yaml()
    yaml_df = prepare_yaml_data(records)

    connection = get_db_connection()

    try:
        pl_df = load_pl_data(connection)
        price_rules_df = load_price_rules(connection)

        pl_df = derive_company(
            pl_df,
            price_rules_df
        )

        working_df = match_yaml_with_pl(
            yaml_df,
            pl_df
        )

        working_df = apply_price_rules(
            working_df,
            price_rules_df
        )

        return working_df

    finally:
        connection.close()