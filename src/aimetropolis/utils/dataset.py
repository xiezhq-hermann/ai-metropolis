"""Locate the replay traces, which ship separately from the code (see dataset/README.md)."""
import os
from pathlib import Path


def dataset_root() -> Path:
    override = os.environ.get("AIMETROPOLIS_DATASET")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "dataset"


def replay_path(*parts: str) -> str:
    path = dataset_root().joinpath("replay", *parts)
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing. Run `python dataset/download.py` from the repository root, "
                                "or point AIMETROPOLIS_DATASET at an extracted copy of the dataset.")
    return str(path)
