import pandas as pd

def build_audit_columns(
    df: pd.DataFrame,
    file_path: str,
    sheet_target,
    sheet_name_label=None,
    existing: bool = False
) -> pd.DataFrame:
    """
    Creates or updates audit columns for a dataframe.
    """

    sheet_label = (
        sheet_name_label if sheet_name_label is not None else str(sheet_target)
    )

    audit = pd.DataFrame(index=df.index)

    audit["_source_file"] = file_path
    audit["_sheet_name"] = sheet_label
    audit["_ingested_at"] = pd.Timestamp.now(tz="UTC").tz_convert(None)
    audit["_row_number"] = df.index

    if existing:
        # update mode (overwrite only audit cols if they exist)
        for col in audit.columns:
            df[col] = audit[col]
        return df

    return pd.concat([df, audit], axis=1)