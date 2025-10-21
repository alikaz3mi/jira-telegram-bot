# Bug/Improvement Sync Configuration

This file maps Google Sheets to Jira boards for syncing bugs and improvements.

## Configuration Format

```json
{
  "mappings": [
    {
      "spreadsheet_id": "Google Sheets ID from the URL",
      "sheet_name": "Name of the sheet/tab",
      "board_key": "Jira board/project key",
      "gid": "Sheet tab GID from the URL"
    }
  ]
}
```

## How to Configure

1. **Get Spreadsheet ID**: From the Google Sheets URL:
   ```
   https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit#gid=[GID]
   ```

2. **Get Sheet Name**: The name of the tab at the bottom of the spreadsheet

3. **Get GID**: The `gid` parameter from the URL when you select the tab

4. **Set Board Key**: The Jira project key (e.g., "PROJ", "DEV", etc.)

## Example

For the URL:
```
https://docs.google.com/spreadsheets/d/1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4/edit?gid=1945361091#gid=1945361091
```

Configuration would be:
```json
{
  "spreadsheet_id": "1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4",
  "sheet_name": "Sheet1",
  "board_key": "PROJ",
  "gid": 1945361091
}
```

## Multiple Boards

You can configure multiple boards by adding more objects to the `mappings` array:

```json
{
  "mappings": [
    {
      "spreadsheet_id": "...",
      "sheet_name": "Bugs - Project A",
      "board_key": "PROJA",
      "gid": 123456
    },
    {
      "spreadsheet_id": "...",
      "sheet_name": "Bugs - Project B",
      "board_key": "PROJB",
      "gid": 789012
    }
  ]
}
```
