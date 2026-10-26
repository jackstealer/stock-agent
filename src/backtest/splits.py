import pandas as pd

from ..data.schema import TZ


def get_split(df: pd.DataFrame, cfg: dict, part: str,
              allow_test: bool = False) -> pd.DataFrame:
    """Slice bars by date. The test split refuses to load unless explicitly unlocked."""
    if part == "test" and not allow_test:
        raise PermissionError(
            "The test split is locked. It is opened once, at the very end.")
    train_end = pd.Timestamp(cfg["splits"]["train_end"], tz=TZ)
    val_end = pd.Timestamp(cfg["splits"]["val_end"], tz=TZ)
    ts = df["timestamp"]
    masks = {"train": ts <= train_end,
             "val": (ts > train_end) & (ts <= val_end),
             "test": ts > val_end}
    return df[masks[part]]