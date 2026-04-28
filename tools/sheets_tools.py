from tools.auth import get_google_service


def read_range(spreadsheet_id: str, range_notation: str) -> dict:
    service = get_google_service("sheets", "v4")
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_notation,
    ).execute()
    values = result.get("values", [])
    return {
        "spreadsheet_id": spreadsheet_id,
        "range": result.get("range", range_notation),
        "row_count": len(values),
        "values": values,
    }


def append_row(spreadsheet_id: str, sheet_name: str, values: list) -> dict:
    service = get_google_service("sheets", "v4")
    range_notation = f"{sheet_name}!A1"
    body = {"values": [values]}
    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range_notation,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()
    updates = result.get("updates", {})
    return {
        "updated_range": updates.get("updatedRange", ""),
        "rows_appended": updates.get("updatedRows", 1),
        "status": "appended",
    }


def update_cell(spreadsheet_id: str, cell_notation: str, value: str) -> dict:
    service = get_google_service("sheets", "v4")
    body = {"values": [[value]]}
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=cell_notation,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()
    return {
        "updated_range": result.get("updatedRange", cell_notation),
        "status": "updated",
    }
