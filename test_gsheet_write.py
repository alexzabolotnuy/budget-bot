import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Авторизація
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
client = gspread.authorize(creds)

# Відкриття таблиці по ID
sheet = client.open_by_key("1y039e2_zew51s0kQFUijIiX6_bq29Jx4U-7upo1nTts")
worksheet = sheet.sheet1  # або .worksheet("назва вкладки")

# Підготовка даних
row = [
    datetime.now().strftime("%Y-%m-%d %H:%M"),
    "Alexey",                # або ім’я користувача з Telegram
    "Харчування",            # категорія
    "250",                   # сума
    "тестовий запис з GPT"   # коментар (необов’язково)
]

# Запис у таблицю
worksheet.append_row(row)
print("✅ Витрату додано до Google Sheets!")
