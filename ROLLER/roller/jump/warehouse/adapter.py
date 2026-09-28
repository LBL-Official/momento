"""Read-only warehouse adapter. Canonical parquet is never written."""

from __future__ import annotations

from typing import Any, Protocol


class WarehouseAdapter(Protocol):
    def inspect(self) -> dict[str, Any]: ...

    def list_tables(self) -> list[dict[str, Any]]: ...

    def describe_table(self, table: str) -> dict[str, Any]: ...

    def columns(self, table: str) -> list[dict[str, Any]]: ...

    def preview_rows(
        self,
        table: str,
        *,
        columns: list[str] | None = None,
        limit: int = 100,
        page: int = 1,
        sort: str | None = None,
        order: str = "asc",
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    def stats(self, table: str, *, compute: bool = False) -> dict[str, Any]: ...

    def lineage(self, table: str) -> dict[str, Any]: ...

    def physical_files(self) -> dict[str, Any]: ...

    def dictionary(self) -> dict[str, Any]: ...

    def query(self, sql: str, *, limit: int = 100) -> dict[str, Any]: ...

    def refresh_metadata(self) -> dict[str, Any]: ...

    def validate(self) -> dict[str, Any]: ...
