import subprocess
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
import dotenv
import re
import os
import paramiko
import psycopg2
from psycopg2 import Error

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
dotenv.load_dotenv()

token = os.getenv('TOKEN')
ssh_host = os.getenv('RM_HOST')
ssh_port = os.getenv('RM_PORT')
ssh_user = os.getenv('RM_USER')
ssh_pass = os.getenv('RM_PASSWORD')

def ssh_connect():
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(
            hostname=ssh_host,
            port=ssh_port,
            username=ssh_user,
            password=ssh_pass
    )

    return ssh_client

ssh_client = ssh_connect()

EMAIL, PHONE, PASSWD, APT_CHOICE, ASK_WRITE, WRITE_TO_DB = range(6)

email_regex  = re.compile(r"\b([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b", re.IGNORECASE)
phone_regex  = re.compile(r"((\+7|8)[ -]?[(]?\d{3}[)]?[ -]?\d{3}[ -]?\d{2}[ -]?\d{2})")
passwd_regex = re.compile(r"(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])(?=.*[!@#\$%\^&\*()\.])(?=.{8,})")

choice_keyboard_email = [
    [
    InlineKeyboardButton("Да", callback_data="email_yes"),
    InlineKeyboardButton("Нет", callback_data="no")
    ]
]

choice_keyboard_phone = [
    [
    InlineKeyboardButton("Да", callback_data="phone_yes"),
    InlineKeyboardButton("Нет", callback_data="no")
    ]
]

obtained_data = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Привет! Я могу искать адреса электронной почты и телефоны в сообщениях.")


async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Отправьте мне текст с e-mail или /cancel для отмены.")
    return EMAIL


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Отправьте мне текст с номерами телефонов или /cancel для отмены.")
    return PHONE


async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Отправьте мне пароль для проверки.")
    return PASSWD


async def parse_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    r = email_regex.findall(msg)
    global obtained_data
    obtained_data = r
    emails = '\n'.join(r)
    if r:
        await update.message.reply_text(f"Найденные e-mail адреса в сообщении: {emails}")

        reply_markup = InlineKeyboardMarkup(choice_keyboard_email)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Хотите ли вы записать эти адреса в базу?", reply_markup=reply_markup)

    else:
        await update.message.reply_text("E-mail адреса не найдены!")

    return ConversationHandler.END


async def parse_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    r = phone_regex.findall(msg)
    global obtained_data
    obtained_data = r
    phones = '\n'.join([group[0] for group in r])
    if r:
        await update.message.reply_text(f"Найденные номера телефонов в сообщении:\n{phones}")

        reply_markup = InlineKeyboardMarkup(choice_keyboard_phone)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Хотите ли вы записать эти телефоны в базу?", reply_markup=reply_markup)

    else:
        await update.message.reply_text("Номера не найдены!")

    return ConversationHandler.END


async def verify_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    passwd = update.message.text
    r = passwd_regex.match(passwd)
    if r:
        await update.message.reply_text("Пароль сложный")
    else:
        await update.message.reply_text("Пароль простой")
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отмена.")
    return ConversationHandler.END

async def ssh_execute(update: Update, context: ContextTypes.DEFAULT_TYPE, command, message):
    stdin, stdout, stderr = ssh_client.exec_command(command)
    data = stdout.read() + stderr.read()
    data = data.decode("utf-8")
    data = [f"```\n{data[0+i:4000+i]}\n```" for i in range(0, len(data), 4000)]
    
    data[0] = f"{message}: " + data[0]
    for chunk in data:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk, parse_mode='MarkdownV2')
    return ConversationHandler.END

async def ssh_apt_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Напишите имя пакета, информацию о котором хотите получить, или 'все', чтобы получить полный список пакетов.")
    return APT_CHOICE

async def ssh_apt_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "все":
        await ssh_apt_list_all(update, context)
    elif update.message.text != None:
        await ssh_apt_list_one(update, context, update.message.text)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Я вас не понимаю.")

    return ConversationHandler.END

async def ssh_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "cat /etc/os-release", "Информация о релизе")

async def ssh_uname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "uname -a", "Информация об архитектуре")

async def ssh_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "uptime", "Время работы")

async def ssh_df(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "df", "Состояние файловой системы")

async def ssh_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "free", "Состояние оперативной памяти")

async def ssh_mpstat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "mpstat", "Производительность системы")

async def ssh_w(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "w", "Сейчас работают пользователи")

async def ssh_auths(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "last | head -10", "Последние 10 входов")

async def ssh_critical(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "cat /var/log/syslog /var/log/auth.log | grep error | tail -10", "Последние 10 ошибок")

async def ssh_ps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "ps -aux", "Запущенные процессы")

async def ssh_ss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "ss", "Используемые порты")

async def ssh_apt_list_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Выводим только установленные пользователем (--installed) - paramiko не может
    # дождаться полного списка, да и практическая польза от вывода 104'585 пакетов 
    # сомнительна :)
    return await ssh_execute(update, context, "apt list --installed", "Все установленные пакеты")

async def ssh_apt_list_one(update: Update, context: ContextTypes, package):
    return await ssh_execute(update, context, f"apt info {package}", f"Информация о пакете {package}")

async def ssh_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await ssh_execute(update, context, "systemctl --type=service --state=active", "Запущенные сервисы")

async def db_query(update: Update, context: ContextTypes, query, message):
    connection = None
    data = None

    try:
        connection = psycopg2.connect(
            user=os.getenv("DB_USER"), 
            password=os.getenv("DB_PASSWORD"), 
            host=os.getenv("DB_HOST"), 
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_DATABASE"))
    
        cursor = connection.cursor()
        cursor.execute(query)
        data = cursor.fetchall()
    
    except (Exception, Error) as error:
        logging.error("Ошибка при работе с PostgreSQL: %s", error)
    finally:
        if connection is not None:
            cursor.close()
            connection.close()

    if data != []:
        data = '\n'.join([' '.join([str(x) for x in row]) for row in data])

        data = [f"```\n{data[0+i:4000+i]}\n```" for i in range(0, len(data), 4000)]

        data[0] = f"{message}: {data[0]}"
        for chunk in data:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk, parse_mode="MarkdownV2")

    return ConversationHandler.END
    
async def db_insert(query, tupl):
    connection = None
    success = False

    try:
        connection = psycopg2.connect(
            user=os.getenv("DB_USER"), 
            password=os.getenv("DB_PASSWORD"), 
            host=os.getenv("DB_HOST"), 
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_DATABASE"))
    
        cursor = connection.cursor()
        cursor.executemany(query, tupl)
        connection.commit()

        success = True
    
    except (Exception, Error) as error:
        logging.error("Ошибка при работе с PostgreSQL: %s", error)
    finally:
        if connection is not None:
            cursor.close()
            connection.close()

    return success
    
async def db_repl_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    #await ssh_execute(update, context, 'cat /var/log/postgresql/postgresql.log | grep "repl_user" | grep -F "$(date +%Y-%m-%d)"', "Логи за последние сутки")
    try:
        res = subprocess.run(['bash', '-c', 'cat /var/log/postgresql/postgresql.log | grep "repl" | tail -10  | grep -F "$(date +%Y-%m-%d)"'], capture_output=True, text=True)
        log = res.stdout
        if res.stdout:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Логи за последние сутки: {log}")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Логи отсутствуют!")
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Произошла ошибка: {e}")

async def db_get_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db_query(update, context, "SELECT email FROM Почта;", "Адреса почт в БД")

async def db_get_phones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db_query(update, context, "SELECT phone FROM Телефоны;", "Номера телефонов")

async def handle_db_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    global obtained_data
    if query.data == "email_yes":
        flat_data = tuple([(email,) for email in obtained_data])
        res = await db_insert(f"INSERT INTO Почта (email) VALUES (%s)", flat_data)

        if res:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Адреса были успешно записаны в БД!")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Произошла ошибка: не удалось записать данные.")

    elif query.data == "phone_yes":
        phones = []
        for p in obtained_data:
            phone = re.sub(r'[\(\)\- ]', '', p[0])
            phone = re.sub(r'\+7', '8', phone)
            phones.append(phone)

        flat_data = tuple([(phone,) for phone in phones])
        res = await db_insert(f"INSERT INTO Телефоны (phone) VALUES (%s)", flat_data)

        if res:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Телефоны были успешно записаны в БД!")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Произошла ошибка: не удалось записать данные.")
    
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Хорошо, данные не были сохранены.")

    obtained_data = []



if __name__ == '__main__':
    application = ApplicationBuilder().token(token).build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    email_handler = ConversationHandler(
        entry_points=[CommandHandler("find_email", get_email)],
        states={
            EMAIL: [MessageHandler(filters.TEXT & (~filters.COMMAND), parse_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    phone_handler = ConversationHandler(
        entry_points=[CommandHandler("find_phone", get_phone)],
        states={
            PHONE: [MessageHandler(filters.TEXT & (~filters.COMMAND), parse_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    verify_pass_handler = ConversationHandler(
        entry_points=[CommandHandler("verify_password", get_password)],
        states={
            PASSWD: [MessageHandler(filters.TEXT & (~filters.COMMAND), verify_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    ssh_cmd_handler = ConversationHandler(
        entry_points=[CommandHandler("get_release", ssh_release),
                      CommandHandler("get_uname", ssh_uname),
                      CommandHandler("get_uptime", ssh_uptime),
                      CommandHandler("get_df", ssh_df),
                      CommandHandler("get_free", ssh_free),
                      CommandHandler("get_mpstat", ssh_mpstat),
                      CommandHandler("get_w", ssh_w),
                      CommandHandler("get_auths", ssh_auths),
                      CommandHandler("get_critical", ssh_critical),
                      CommandHandler("get_ps", ssh_ps),
                      CommandHandler("get_ss", ssh_ss),
                      CommandHandler("get_services", ssh_services),

                      CommandHandler("get_apt_list", ssh_apt_list)],
        states={
            APT_CHOICE: [MessageHandler(filters.TEXT & (~filters.COMMAND), ssh_apt_choice)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    db_log_handler = CommandHandler("get_repl_logs", db_repl_log)
    db_email_handler = CommandHandler("get_emails", db_get_emails)
    db_phone_handler = CommandHandler("get_phone_numbers", db_get_phones)

    application.add_handler(email_handler)
    application.add_handler(phone_handler)
    application.add_handler(verify_pass_handler)
    application.add_handler(ssh_cmd_handler)

    application.add_handler(db_log_handler)
    application.add_handler(db_email_handler)
    application.add_handler(db_phone_handler)

    application.add_handler(CallbackQueryHandler(handle_db_choice))

    application.run_polling()
