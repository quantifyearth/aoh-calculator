import tempfile
from pathlib import Path

import pytest
import pandas as pd

from aoh.validation.collate_data import collate_data

def test_simple_positive_path() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        src_data_path = Path("tests/testdata/collate_data")
        input_file_count = len(list(src_data_path.glob("*.json")))

        output_path = Path(tmpdir) / "res.csv"
        collate_data(src_data_path, output_path)

        results = pd.read_csv(output_path)
        assert len(results) == input_file_count

def test_fails_on_empty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(FileNotFoundError):
            collate_data(Path(tmpdir), Path(tmpdir) / "output.csv")
