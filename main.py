import logging
import pymysql
import os
import urllib.parse
from telegram import BotCommand, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from geo_name import get_location_name

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


def get_db_connection():
    try:
        mysql_public_url = os.getenv("MYSQL_PUBLIC_URL")
        if not mysql_public_url:
            raise ValueError("MYSQL_PUBLIC_URL не определён в переменных окружения")

        parsed_url = urllib.parse.urlparse(mysql_public_url)
        user = parsed_url.username
        password = parsed_url.password
        host = parsed_url.hostname
        port = parsed_url.port or 3306
        database = parsed_url.path[1:]

        # Отладочный вывод
        logging.info(f"Host: {host}")
        logging.info(f"Port: {port}")
        logging.info(f"Database: {database}")
        logging.info(f"User: {user}")
        logging.info(f"Password: {password}")

        # Создаем подключение к MySQL
        conn = pymysql.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )

        # Создаем таблицу users, если она не существует
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone_number VARCHAR(20) PRIMARY KEY,
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                age INTEGER,
                gender VARCHAR(10),
                address TEXT,
                latitude REAL,
                longitude REAL
            )
        """)
        conn.commit()
        cursor.close()

        return conn
    except Exception as e:
        logging.error(f"Ошибка подключения к базе: {e}")
        raise


# Инициализация соединения (будет создаваться при необходимости)
conn = None

def start(update, context):
    # menu бота
    commands = [
        BotCommand(command='start', description="botga start berish!")
        BotCommand(command='cancel', description="bekor qilish!")
    ]
    context.bot.set_my_commands(commands=commands)
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

    # Если получен контакт
    if update.message.contact:
        phone_number = update.message.contact.phone_number
        context.user_data['phone_number'] = phone_number
        update.message.reply_text('Rahmat! Ismingiz nima?')
        return 'FIRST_NAME'
    # Если введён текст
    else:
        user_text = update.message.text
        if user_text.isdigit():
            context.user_data['phone_number'] = user_text
            update.message.reply_text('Rahmat! Ismingiz nima?')
            return 'FIRST_NAME'
        else:
            reply_markup = ReplyKeyboardMarkup([
                [KeyboardButton(text="Telefon kontaktinngizni ulashing", request_contact=True)]
            ], resize_keyboard=True, one_time_keyboard=True)
            context.bot.send_message(
                chat_id=update.message.chat_id,
                text='Siz raqam kiritmadingiz. Raqam kiriting yoki telefon kontaktinngizni ulashing:',
                reply_markup=reply_markup
            )
            return 'PHONE_NUMBER'  # Остаёмся в состоянии PHONE_NUMBER


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
    try:
        age_int = int(age)
        if age_int < 0:
            update.message.reply_text("Iltimos, musbat yosh kiriting (masalan, 18, 25, va hokazo). Qayta urining:")
            return 'AGE'
        if not (0 <= age_int <= 150):
            update.message.reply_text("Iltimos, realistik yosh kiriting (0-150 oraliqda). Qayta urining:")
            return 'AGE'
        context.user_data['age'] = age_int
        update.message.reply_text('Rahmat! Jinsingiz: erkak/ayol?')
        return 'GENDER'
    except ValueError:
        logging.warning(f"Некорректный ввод возраста от пользователя {update.effective_user.id}: {age}")
        update.message.reply_text("Iltimos, faqat raqam kiriting (masalan, 18, 25, va hokazo). Qayta urining:")
        return 'AGE'


def gender(update, context):
    global conn
    if conn is None or not conn.open:
        conn = get_db_connection()
    gender = update.message.text
    context.user_data['gender'] = gender
    reply_markup = ReplyKeyboardMarkup([
        [KeyboardButton(text="Lokatsiyanngizni ulashing", request_location=True)]
    ], resize_keyboard=True, one_time_keyboard=True)
    context.bot.send_message(chat_id=update.effective_user.id, text="Lokatsiyanngizni ulashing:",
                             reply_markup=reply_markup)
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

    # Проверяем, что age — это целое число (дополнительная проверка на случай ошибок)
    age = context.user_data['age']
    if not isinstance(age, int):
        try:
            age = int(age)
            context.user_data['age'] = age
            logging.info(f"Age converted to: {age}, type: {type(age)}")
        except (ValueError, TypeError):
            logging.error(f"Некорректное значение возраста от пользователя {update.effective_user.id}: {age}")
            update.message.reply_text(
                "Xatolik yuz berdi: yoshingiz noto'g'ri formatda. Iltimos, qayta /start buyrug'ini ishga tushiring.")
            return ConversationHandler.END

    # Сохраняем данные в MySQL
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (phone_number, first_name, last_name, age, gender, address, latitude, longitude) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE first_name=VALUES(first_name), last_name=VALUES(last_name), age=VALUES(age), gender=VALUES(gender), address=VALUES(address), latitude=VALUES(latitude), longitude=VALUES(longitude)",
        (
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
                'PHONE_NUMBER': [
                    MessageHandler(Filters.contact & ~Filters.command, phone_number),  # Контакт
                    MessageHandler(Filters.text & ~Filters.command, phone_number)  # Текст
                ],
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
