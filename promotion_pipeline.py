import pandas as pd

from db_connection import get_db_connection


# ============================================================
# CONFIGURATION
# ============================================================

EXCEL_FILE = "data/promotion_table.xlsx"

PROMOTIONAL_SKU_SHEET = 1   # Sheet 2
PROMOTION_RULE_SHEET = 2    # Sheet 3
DEFAULT_SEASON = "Q4"

EXCLUDED_SUBCATEGORIES = {
    "SJ",
    "UNK"
}


# ============================================================
# LOAD PROMOTIONAL SKUs
# ============================================================

def load_promotional_skus():
    """Load promotional SKUs from Excel Sheet 2."""

    df = pd.read_excel(
        EXCEL_FILE,
        sheet_name=PROMOTIONAL_SKU_SHEET
    )

    required_column = "Promotional SKUs"

    if required_column not in df.columns:
        raise ValueError(
            f"Column '{required_column}' not found "
            "in promotional SKU sheet."
        )

    df = df[
        [required_column]
    ].copy()

    df["Promotional SKUs"] = (
        df["Promotional SKUs"]
        .astype(str)
        .str.strip()
    )

    df = df[
        df["Promotional SKUs"] != ""
    ]

    df = df.drop_duplicates(
        subset=["Promotional SKUs"]
    )

    print(
        f"Promotional SKUs loaded: {len(df)}"
    )

    return df


# ============================================================
# LOAD PL
# ============================================================

def load_pl_data(connection):
    """Load SKU, PL and subcategory from PL."""

    query = """
        SELECT
            SKU,
            PL,
            subcategory
        FROM PL
    """

    df = pd.read_sql(
        query,
        connection
    )

    if df.empty:
        raise ValueError(
            "PL table is empty."
        )

    df["SKU"] = (
        df["SKU"]
        .astype(str)
        .str.strip()
    )

    df["PL"] = (
        df["PL"]
        .astype(str)
        .str.strip()
    )

    df["subcategory"] = (
        df["subcategory"]
        .astype(str)
        .str.strip()
    )

    print(
        f"PL records loaded: {len(df)}"
    )

    return df


# ============================================================
# EXCLUDE UNSUPPORTED PROMOTIONAL SKUs
# ============================================================

def exclude_unsupported_skus(
    promotional_df,
    pl_df
):
    """Remove promotional SKUs with unsupported subcategories."""

    promotional_df = promotional_df.copy()
    pl_df = pl_df.copy()

    pl_df["_sku_key"] = (
        pl_df["SKU"]
        .str.lower()
    )

    promotional_df["_sku_key"] = (
        promotional_df["Promotional SKUs"]
        .str.lower()
    )

    excluded_skus = pl_df[
        pl_df["subcategory"].str.upper().isin(
            EXCLUDED_SUBCATEGORIES
        )
    ]["_sku_key"].drop_duplicates()

    excluded_df = promotional_df[
        promotional_df["_sku_key"].isin(
            excluded_skus
        )
    ].copy()

    if not excluded_df.empty:

        print(
            "\nExcluding promotional SKUs "
            "with unsupported subcategories:"
        )

        print(
            excluded_df[
                ["Promotional SKUs"]
            ].to_string(index=False)
        )

    promotional_df = promotional_df[
        ~promotional_df["_sku_key"].isin(
            excluded_skus
        )
    ].copy()

    promotional_df = promotional_df.drop(
        columns=["_sku_key"]
    )

    print(
        f"\nPromotional SKUs remaining: "
        f"{len(promotional_df)}"
    )

    return promotional_df


# ============================================================
# LOAD PRICE_LIST
# ============================================================

def load_price_list(connection):
    """Load SKU, PL, MAP and LPP from PRICE_LIST."""

    query = """
        SELECT
            SKU,
            PL,
            MAP,
            LPP
        FROM PRICE_LIST
    """

    df = pd.read_sql(
        query,
        connection
    )

    if df.empty:
        raise ValueError(
            "PRICE_LIST table is empty."
        )

    df["SKU"] = (
        df["SKU"]
        .astype(str)
        .str.strip()
    )

    df["PL"] = (
        df["PL"]
        .astype(str)
        .str.strip()
    )

    df["MAP"] = pd.to_numeric(
        df["MAP"],
        errors="coerce"
    )

    df["LPP"] = pd.to_numeric(
        df["LPP"],
        errors="coerce"
    )

    invalid_map = df[
        df["MAP"].isna()
    ]

    if not invalid_map.empty:
        raise ValueError(
            "Invalid MAP values found in PRICE_LIST."
        )

    print(
        f"PRICE_LIST records loaded: {len(df)}"
    )

    return df


# ============================================================
# MAP PROMOTIONAL SKUs WITH PRICE_LIST
# ============================================================

def map_promotional_skus(
    promotional_df,
    price_list_df
):
    """
    Match promotional SKUs with PRICE_LIST.

    PRICE_LIST contains the actual PL and MAP
    required for promotion calculation.
    """

    promotional_df = promotional_df.copy()
    price_list_df = price_list_df.copy()

    promotional_df["_sku_key"] = (
        promotional_df["Promotional SKUs"]
        .str.lower()
    )

    price_list_df["_sku_key"] = (
        price_list_df["SKU"]
        .str.lower()
    )

    working_df = promotional_df.merge(
        price_list_df[
            [
                "_sku_key",
                "SKU",
                "PL",
                "MAP",
                "LPP"
            ]
        ],
        on="_sku_key",
        how="left"
    )

    missing_matches = working_df[
        working_df["PL"].isna()
    ]

    if not missing_matches.empty:

        print(
            "\nPromotional SKUs not found "
            "in PRICE_LIST:"
        )

        print(
            missing_matches[
                ["Promotional SKUs"]
            ].to_string(index=False)
        )

        raise ValueError(
            "Some promotional SKUs do not "
            "exist in PRICE_LIST."
        )

    working_df = working_df[
        [
            "SKU",
            "PL",
            "MAP",
            "LPP"
        ]
    ].copy()

    print(
        "\nPromotional SKU → PRICE_LIST "
        "mapping passed."
    )

    return working_df


# ============================================================
# DERIVE CATEGORY AND SUBCATEGORY FROM PL
# ============================================================

def derive_category_subcategory(df):
    """
    Derive category and subcategory from PL.

    Example:
        HPON_PC_LAPTOP

        HPON      -> brand / identifier
        PC        -> category
        LAPTOP    -> subcategory
    """

    df = df.copy()

    pl_parts = (
        df["PL"]
        .astype(str)
        .str.strip()
        .str.split("_")
    )

    invalid_pl = df[
        pl_parts.apply(
            lambda parts: len(parts) != 3
        )
    ]

    if not invalid_pl.empty:

        print(
            "\nInvalid PL format found:"
        )

        print(
            invalid_pl[
                ["SKU", "PL"]
            ].to_string(index=False)
        )

        raise ValueError(
            "PL must contain exactly "
            "three parts separated by '_'."
        )

    df["category"] = pl_parts.str[1]

    df["subcategory"] = pl_parts.str[2]

    df["category"] = (
        df["category"]
        .astype(str)
        .str.strip()
    )

    df["subcategory"] = (
        df["subcategory"]
        .astype(str)
        .str.strip()
    )

    return df


# ============================================================
# ADD DEFAULT SEASON
# ============================================================

def add_default_season(df):
    """Add the currently active promotion season."""

    df = df.copy()

    df["season"] = DEFAULT_SEASON

    return df


# ============================================================
# LOAD PROMOTION RULES
# ============================================================

def load_promotion_rules():
    """
    Load promotion rules from Excel Sheet 3.

    Rule calculation will be implemented after
    confirming the exact Sheet 3 structure.
    """

    rules_df = pd.read_excel(
        EXCEL_FILE,
        sheet_name=PROMOTION_RULE_SHEET
    )

    print("\nPromotion rule sheet loaded.")

    print(
        rules_df.to_string(index=False)
    )

    return rules_df


# ============================================================
# PREPARE PROMOTION DATA
# ============================================================

def prepare_promotion_data():
    """
    Prepare the complete working DataFrame
    before applying promotion rules.
    """

    promotional_df = (
        load_promotional_skus()
    )

    connection = get_db_connection()

    try:

        pl_df = load_pl_data(
            connection
        )

        price_list_df = load_price_list(
            connection
        )

    finally:
        connection.close()

    promotional_df = exclude_unsupported_skus(
        promotional_df,
        pl_df
    )

    working_df = map_promotional_skus(
        promotional_df,
        price_list_df
    )

    working_df = derive_category_subcategory(
        working_df
    )

    working_df = add_default_season(
        working_df
    )

    return working_df


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\nStarting promotion pipeline..."
    )

    working_df = prepare_promotion_data()

    print(
        "\nPromotion working DataFrame:"
    )

    print(
        working_df[
            [
                "SKU",
                "PL",
                "category",
                "subcategory",
                "MAP",
                "LPP",
                "season"
            ]
        ].to_string(index=False)
    )

    print(
        "\nLoading promotion rules..."
    )

    rules_df = load_promotion_rules()

    print(
        "\nPromotion mapping preparation "
        "completed successfully."
    )


if __name__ == "__main__":
    main()