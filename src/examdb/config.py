from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path
    vault: Path
    raw: Path
    processed: Path
    db: Path

    @classmethod
    def from_root(cls, root: Path | str = ".") -> "Paths":
        root_path = Path(root).resolve()
        return cls(
            root=root_path,
            vault=root_path / "vault",
            raw=root_path / "data" / "raw",
            processed=root_path / "data" / "processed",
            db=root_path / "data" / "db" / "examdb.sqlite",
        )

    def ensure(self) -> None:
        for path in [
            self.vault / "资料库" / "政策理论",
            self.vault / "题库" / "真题套卷",
            self.vault / "题库" / "题目卡片",
            self.vault / "刷题记录" / "错题本",
            self.vault / "刷题记录" / "周报",
            self.vault / "模板",
            self.raw,
            self.processed,
            self.db.parent,
        ]:
            path.mkdir(parents=True, exist_ok=True)
