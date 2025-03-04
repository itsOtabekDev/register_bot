import logging
import pymysql
import os
from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from geo_name import get_location_name

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Функция для создания соединения с MySQL (глобальная, чтобы избежать дублирования)
def get_db_connection():
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQLHOST"),
            port=int(os.getenv("MYSQLPORT", 3306)),  # Порт MySQL по умолчанию 3306
            database=os.getenv("MYSQLDATABASE"),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD")
        )
        return conn
    except Exception as e:
        logging.error(f"Ошибка подключения к базе: {e}")
        raise

# Инициализация соединения (будет создаваться при необходимости)
conn = None

def start(update, context):
    global conn
    if conn is None or not conn.open:
        conn = get_db_connection()  # Создаём соединение, если его нет или оно закрыто
    reply_text = 'Salom! Telefon raqamingizni kiriting:'
    reply_markup = ReplyKeyboardMarkup([
        [KeyboardButton(text="Telefon kontaktinngizni ulashing", request_contact=True)]
    ], resize_keyboard=True, one_time_keyboard=True)
    context.bot.send_message(chat_id=update.effective_user.id, text=reply_text, reply_markup=reply_markup)
    logging.info(f"user - {update.effective_user.id} started")

    return 'PHONE_NUMBER'

def phone_number(update, context):
    global conn
    if conn is None or not conn.open:
        conn = get_db_connection()
    phone_number = update.message.contact.phone_number
    context.user_data['phone_number'] = phone_number
    update.message.reply_text('Rahmat! Ismingiz nima?')
    return 'FIRST_NAME'

def first_name(update, context):
    global conn
    if conn is None or not conn.open:
        conn = get_db_connection()
    first_name = update.message.text
    context.user_data['first_name'] = first_name
    update.message.reply_text('Rahmat! Familyangiz nima?')
    return 'LAST_NAME'

def last_name(update, context):
    global conn
    if conn is None or not conn.open:
        conn = get_db_connection()
    last_name = update.message.text
    context.user_data['last_name'] = last_name
    update.message.reply_text('Rahmat! Yoshingiz?')
    return 'AGE'

def age(update, context):
    global conn
    if conn is None or not conn.open:
        conn = get_db_connection()
    age = update.message.text
    context.user_data['age'] = age
    update.message.reply_text('Rahmat! Jinsingiz: erkak/ayol?')
    return 'GENDER'

def gender(update, context):
    global conn
    if conn is None or not conn.open:
        conn = get_db_connection()
    gender = update.message.text
    context.user_data['gender'] = gender
    reply_markup = ReplyKeyboardMarkup([
        [KeyboardButton(text="Lokatsiyanngizni ulashing", request_location=True)]
    ], resize_keyboard=True, one_time_keyboard=True)
    context.bot.send_message(chat_id=update.effective_user.id, text="Lokatsiyanngizni ulashing:", reply_markup=reply_markup)
    return 'GEOLOCATION'

def geolocation(update, context):
    global conn
    if conn is None or not conn.open:
        conn = get_db_connection()
    latitude = update.message.location.latitude
    longitude = update.message.location.longitude
    address = get_location_name(latitude, longitude)
    context.user_data['latitude'] = latitude
    context.user_data['longitude'] = longitude
    context.user_data['address'] = address

    # Сохраняем данные в MySQL
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (phone_number, first_name, last_name, age, gender, address, latitude, longitude) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE first_name=VALUES(first_name), last_name=VALUES(last_name), age=VALUES(age), gender=VALUES(gender), address=VALUES(address), latitude=VALUES(latitude), longitude=VALUES(longitude)", (
        context.user_data['phone_number'],
        context.user_data['first_name'],
        context.user_data['last_name'],
        context.user_data['age'],
        context.user_data['gender'],
        context.user_data['address'],
        context.user_data['latitude'],
        context.user_data['longitude'],
    ))
    conn.commit()
    logging.info("User Registered")
    update.message.reply_text("Ro'yxatdan o'tganingiz uchun Rahmat!")
    update.message.reply_text(f"""
        phone: {context.user_data['phone_number']},
        first_name: {context.user_data['first_name']},
        last_name: {context.user_data['last_name']},
        age: {context.user_data['age']},
        gender: {context.user_data['gender']},
        address: {context.user_data['address']},
        """)
    return ConversationHandler.END

def cancel(update, context):
    global conn
    if conn and conn.open:
        conn.close()
    update.message.reply_text(text='Bekor qilindi!')
    return ConversationHandler.END

def main():
    global conn
    try:
        conn = get_db_connection()
        updater = Updater(token="8184862679:AAFqSCRU_GGR3ukBLzwFKC_Fn4XjmXp2Mj8")
        dispatcher = updater.dispatcher

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                'PHONE_NUMBER': [MessageHandler(Filters.contact & ~Filters.command, phone_number)],
                'FIRST_NAME': [MessageHandler(Filters.text & ~Filters.command, first_name)],
                'LAST_NAME': [MessageHandler(Filters.text & ~Filters.command, last_name)],
                'AGE': [MessageHandler(Filters.text & ~Filters.command, age)],
                'GENDER': [MessageHandler(Filters.text & ~Filters.command, gender)],
                'GEOLOCATION': [MessageHandler(Filters.location & ~Filters.command, geolocation)],
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        dispatcher.add_handler(conv_handler)
        updater.start_polling()
        updater.idle()
    except Exception as e:
        logging.error(f"Ошибка в main: {e}")
    finally:
        if conn and conn.open:
            conn.close()

if __name__ == '__main__':
    main()