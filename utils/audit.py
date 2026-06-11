import pandas as pd

def build_audit_columns(
    df: pd.DataFrame,
    source_file: str,
    sheet_target=None,
    existing: bool = False
) -> pd.DataFrame:
    """
    Creates or updates audit columns for a dataframe.
    """

    # Explicitly use the custom label if provided, otherwise default to 'na'
    sheet_target = (
        sheet_target if sheet_target is not None else "na"
    )

    audit = pd.DataFrame(index=df.index)

    audit["_source_file"] = source_file
    audit["_sheet_name"] = sheet_target  # will be na if no sheet number/ name provided
    audit["_ingested_at"] = pd.Timestamp.now(tz="UTC").tz_convert(None)
    audit["_row_number"] = df.index

    if existing:
        for col in audit.columns:
            df[col] = audit[col]
        return df

    return pd.concat([df, audit], axis=1)