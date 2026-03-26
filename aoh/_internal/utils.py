from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

# \w technically will gobble underscores, but that's okay
# as we're explicit about the underscores around the taxon/assessment ids
PATTERN = re.compile(r"^(\w+)_T(\d+)(?:A(\d+))?(?:_(\w+))?$")

@dataclass
class IUCNFormatFilename:
    """This class represents the naming scheme used by the IUCN Redlist Website for filetypes."""

    content: str
    taxon_id: int
    assessment_id: int | None
    season: str | None
    suffix: str

    @classmethod
    def of_filename(cls, filename: Path | str) -> IUCNFormatFilename:
        typed_filename = Path(filename)
        name = typed_filename.stem
        match = PATTERN.match(name)
        if match is None:
            raise ValueError("Filename did not match expected format")
        parts = match.groups()
        return cls(
            content = parts[0],
            taxon_id = int(parts[1]),
            assessment_id = int(parts[2]) if parts[2] is not None else None,
            season = parts[3],
            suffix = typed_filename.suffix,
        )

    def to_path(self) -> Path:
        assessment = f"A{self.assessment_id}" if self.assessment_id is not None else ""
        season = f"_{self.season}" if self.season is not None else ""
        return Path(f"{self.content}_T{self.taxon_id}{assessment}{season}{self.suffix}")
