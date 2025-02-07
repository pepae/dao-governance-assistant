import json
import logging
import time
import os
import configparser
import asyncio
from telegram import Bot

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Telegram Bot Token from config
TELEGRAM_BOT_TOKEN = config['telegram']['bot_token']

# Preferences file location
PREFERENCES_FILE = 'user_preferences.json'

# Message file
MESSAGE_FILE = 'custom_message.txt'


def load_user_preferences():
    """Load user preferences from the JSON file."""
    if not os.path.exists(PREFERENCES_FILE):
        logging.error(f"Preferences file {PREFERENCES_FILE} not found.")
        return {}
    with open(PREFERENCES_FILE, 'r') as file:
        return json.load(file)


def get_registered_chat_ids():
    """Retrieve all registered chat IDs from the preferences file."""
    preferences = load_user_preferences()
    return list(preferences.get("reminders", {}).keys())


def get_custom_message():
    """Retrieve the custom message from the user or from a file."""
    if os.path.exists(MESSAGE_FILE):
        with open(MESSAGE_FILE, 'r', encoding='utf-8') as file:  # Specify UTF-8 encoding
            message = file.read().strip()
            logging.info(f"Loaded message from {MESSAGE_FILE}.")
            return message
    else:
        logging.info(f"{MESSAGE_FILE} not found. Prompting user for input.")
        return input("Enter your custom message (supports Telegram HTML formatting): ").strip()



async def send_message_to_user(bot, chat_id, message_text):
    """Send a message to a single user asynchronously."""
    try:
        await bot.send_message(chat_id=chat_id, text=message_text, parse_mode='HTML')
        logging.info(f"Message sent to chat_id {chat_id}")
    except Exception as e:
        logging.error(f"Failed to send message to chat_id {chat_id}: {e}")


async def send_messages(bot, chat_ids, message_text):
    """Send a custom message to all specified chat IDs asynchronously."""
    for chat_id in chat_ids:
        await send_message_to_user(bot, chat_id, message_text)
        await asyncio.sleep(0.1)  # Respect rate limit


async def mass_send(bot):
    """Handle mass sending of messages to all registered users."""
    # Load registered chat IDs
    chat_ids = get_registered_chat_ids()
    if not chat_ids:
        logging.warning("No registered users found.")
        return

    # Display the list of chat IDs to the user
    print("The following user IDs are registered:")
    for chat_id in chat_ids:
        print(chat_id)

    # Confirm before proceeding
    confirmation = input("Do you want to send the message to all these users? (yes/no): ").strip().lower()
    if confirmation != "yes":
        logging.info("Operation cancelled by the user.")
        return

    # Get the custom message
    message_text = get_custom_message()
    if not message_text:
        logging.error("Message text is empty. Exiting.")
        return

    logging.info("Sending messages to registered users...")

    # Send messages to all registered chat IDs
    await send_messages(bot, chat_ids, message_text)

    logging.info("All messages sent.")


async def individual_send(bot):
    """Handle sending a message to a specific user asynchronously."""
    specific_chat_id = input("Enter a user ID to send a message to a specific user: ").strip()
    if specific_chat_id:
        specific_message = input("Enter the message to send to this user: ").strip()
        if specific_message:
            await send_message_to_user(bot, specific_chat_id, specific_message)
        else:
            logging.warning("No message entered for the specific user. Skipping.")
    else:
        logging.warning("No user ID entered. Skipping.")


async def main():
    # Initialize the bot
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    # Ask the user to choose the operation
    print("Choose an option:")
    print("1. Send a message to all registered users.")
    print("2. Send a message to a specific user.")
    choice = input("Enter your choice (1/2): ").strip()

    if choice == "1":
        await mass_send(bot)
    elif choice == "2":
        await individual_send(bot)
    else:
        logging.warning("Invalid choice. Exiting.")


if __name__ == '__main__':
    asyncio.run(main())
