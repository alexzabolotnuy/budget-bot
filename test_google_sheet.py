import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Крок 1: Задаємо обсяг доступів
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Крок 2: Підключаємо JSON-файл
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

# Крок 3: Авторизуємось і відкриваємо таблицю
client = gspread.authorize(creds)
spreadsheet = client.open_by_key("1y039e2_zew51s0kQFUijIiX6_bq29Jx4U-7upo1nTts")
worksheet = spreadsheet.sheet1  # або .worksheet("НазваСторінки")

# Крок 4: Виводимо перший рядок
print("Перший рядок у Google Sheet:")
print(worksheet.row_values(1))
