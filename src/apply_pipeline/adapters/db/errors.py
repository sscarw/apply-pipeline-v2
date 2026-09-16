class CorruptedRowError(Exception):
    """Raised when a database value cannot be converted to the domain model."""

    def __init__(
        self,
        table: str,
        row_id: int | None,
        field: str,
        value: object,
    ) -> None:
        self.table = table
        self.row_id = row_id
        self.field = field
        self.value = value

        message = f"{table} row {row_id}: invalid {field} {value!r}"
        super().__init__(message)
