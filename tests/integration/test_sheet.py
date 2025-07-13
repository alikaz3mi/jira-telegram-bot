import gspread
from google.oauth2.service_account import Credentials

from jira_telegram_bot import DEFAULT_PATH

def test_google_sheets_connection():
    """Test Google Sheets API connection."""
    try:
        # Load credentials
        credentials = Credentials.from_service_account_file(
            f'{DEFAULT_PATH}/parschat-684f8662ca98.json',
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
        )
        
        # Create client
        client = gspread.authorize(credentials)
        
        # Test access to your sheet
        sheet = client.open_by_key('1TCvcE_IsP6jpHp3pVfjND9Kys8rfsB5fp2Sx0LILwm4')
        worksheet = sheet.sheet1
        
        print("✅ Google Sheets connection successful!")
        print(f"Sheet title: {sheet.title}")
        print(f"Worksheet title: {worksheet.title}")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_google_sheets_connection()