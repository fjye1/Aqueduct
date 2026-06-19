import pandas as pd
from utils.big_query.import_big_query import load_into_bigquery


def test_load_into_bigquery_dry_run(capsys):
    df = pd.DataFrame({
        "a": [1, 2, 3],
        "b": ["x", "y", "z"]
    })

    load_into_bigquery(
        project_id="test-project",
        layer="test_layer",
        table_name="test_table",
        df=df,
        dry_run=True
    )

    captured = capsys.readouterr()

    assert "[DRY RUN]" in captured.out
    assert "test-project.test_layer.test_table" in captured.out