#!/usr/bin/env python
# pylint: disable=W0613, C0116
# type: ignore[union-attr]

import logging

from dotenv import load_dotenv
import os
load_dotenv()

import mysql.connector

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
import telegram
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_DOMAIN= os.getenv("TELEGRAM_DOMAIN")
TELEGRAM_ADMIN_GROUP_ID = int(os.getenv("TELEGRAM_ADMIN_GROUP_ID"))


db = mysql.connector.connect(
    host=os.getenv("MYSQL_HOSTNAME"),
    user=os.getenv("MYSQL_USERNAME"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE")
)

def start(update: Update, context: CallbackContext) -> None:

    if update.effective_chat.id == TELEGRAM_ADMIN_GROUP_ID:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Olet admin. Botti on rikki jos osallistut vaihtoon ja näet tämän! SOS!!!")
        return

    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Tervemenoa avaruusmatkalle!\n\nLennonjohtoon saat yhteyden lähettämällä tähän keskusteluun tekstiä, kuvia tai videoita.")

        sql = "INSERT INTO `users` (id, username) VALUES (%s, %s) ON DUPLICATE KEY UPDATE username=%s"
        val = (update.message.from_user.id, update.message.from_user.username, update.message.from_user.username)
        c.execute(sql, val)
        db.commit()

        return


def saveMessageMetaData(messageId, forwardedMessageId, originalMessageSentBy) -> None:
    c = db.cursor()
    sql = "INSERT INTO messages (message_id, forwarded_message_id, original_message_sent_by) VALUES (%s, %s, %s)"
    val = (messageId, forwardedMessageId, originalMessageSentBy)
    c.execute(sql, val)
    db.commit()
    c.close()

def getUserId(username) -> int:
    c = db.cursor()
    sql = "SELECT id FROM users WHERE username = %s"
    val = (username,)
    c.execute(sql, val)
    data = c.fetchone()
    db.commit()
    c.close()

    if not data:
        userId = 0
        print("User %s not found from database" % username)
    else:
        userId = data[0]

    return userId


def handleMessage(update: Update, context: CallbackContext) -> None:
    if update.message.chat_id == TELEGRAM_ADMIN_GROUP_ID:
        if update.message.reply_to_message:
            reply(update, context) 
            return
        else:
            message(update, context)
            return
    forwardMessage(update, context)
    return


def forwardMessage(update: Update, context: CallbackContext) -> None:
    forwardedMessage = context.bot.forwardMessage(chat_id=TELEGRAM_ADMIN_GROUP_ID, from_chat_id=update.message.from_user.id, message_id=update.message.message_id)
    saveMessageMetaData(update.message.message_id, forwardedMessage.message_id, update.message.from_user.id)

    return


def reply(update: Update, context: CallbackContext) -> None:
    c = db.cursor(dictionary=True)
    sql = "SELECT original_message_sent_by, message_id FROM messages WHERE forwarded_message_id = %s"
    val = (update.message.reply_to_message.message_id,)
    c.execute(sql, val)
    data = c.fetchone()
    db.commit()
    c.close()

    context.bot.send_message(chat_id=data["original_message_sent_by"], reply_to_message_id=data["message_id"], text=update.message.text)

    return


def message(update: Update, context: CallbackContext) -> None:
    if context.args:
        if (context.args[0][0] == "@"):
            username = context.args[0][1:]
        else: 
            username = context.args[0]

        userId = getUserId(username)

        if userId == 0:
            sendToAdmins(update, context, "Käyttäjää %s ei löytynyt! Viestiä ei lähetetty." % username)
        else:
            context.bot.send_message(chat_id=userId, text=" ".join(context.args[1:]))
        return

    if update.message.photo:
        args = update.message.caption.split(" ")
        if args[0][0] == "/":
            if (args[1][0] == "@"):
                username = args[1][1:]
            else: 
                username = args[1]

            userId = getUserId(username)

            if userId == 0:
                sendToAdmins(update, context, "Käyttäjää %s ei löytynyt! Viestiä ei lähetetty." % username)
            else:
                context.bot.send_photo(chat_id=userId, photo=update.message.photo[0].file_id, caption=" ".join(args[2:]))
            return

    if update.message.video:
        args = update.message.caption.split(" ")
        if args[0][0] == "/":
            if (args[1][0] == "@"):
                username = args[1][1:]
            else: 
                username = args[1]

            userId = getUserId(username)

            if userId == 0:
                sendToAdmins(update, context, "Käyttäjää %s ei löytynyt! Viestiä ei lähetetty." % username)
            else:
                context.bot.send_video(chat_id=userId, video=update.message.video.file_id, caption=" ".join(args[2:]))
            return

    context.bot.send_message(chat_id=TELEGRAM_ADMIN_GROUP_ID, text="Lähetä viesti yhdelle käyttäjälle:\n/message <nick> <viesti>")
    return


def broadcast(update: Update, context: CallbackContext) -> None:
    if not context.args:
        context.bot.send_message(chat_id=TELEGRAM_ADMIN_GROUP_ID, text="Lähetä viesti kaikille:\n/broadcast <viesti>")
        return
    
    c = db.cursor()
    sql = "SELECT id FROM users"
    c.execute(sql)
    users = c.fetchall()
    db.commit()
    c.close()

    for user in users:
        context.bot.send_message(chat_id=user[0], text=" ".join(context.args[0:]))
    return


def sendToAdmins(update: Update, context: CallbackContext, message) -> None:
    context.bot.send_message(chat_id=TELEGRAM_ADMIN_GROUP_ID, text=message)
    return


def main() -> None:
    # Create the Updater and pass it your bot's token.
    updater = Updater(TELEGRAM_TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher


    # user tools
    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))

    dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, handleMessage))

    # admin tools
    dispatcher.add_handler(CommandHandler("message", message))
    dispatcher.add_handler(CommandHandler("broadcast", broadcast))


    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()