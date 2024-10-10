import configparser
import logging
import requests
import json
import time
from web3 import Web3
import threading
import os
from datetime import datetime, timedelta, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
import asyncio
import uuid

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')

# Initialize Web3 connection using the Infura URL from config file
infura_url = config['web3']['infura_url']
w3 = Web3(Web3.HTTPProvider(infura_url))
logging.info("Web3 connection initialized")

# Fetch the ABI
etherscan_api_url = (
    f"{config['etherscan']['api_url']}?module=contract&action=getabi"
    f"&address={config['dao']['event_monitoring_contract_address']}"
    f"&format=raw"
    f"&apikey={config['etherscan']['api_key']}"
)
response = requests.get(etherscan_api_url)
if response.status_code == 200:
    dao_contract_abi = response.text
    logging.info("Successfully fetched contract ABI")
else:
    logging.error("Failed to fetch ABI")
    exit(1)

# Convert the ABI from string to JSON
dao_contract_abi = json.loads(dao_contract_abi)

# Event monitoring contract address from config
event_monitoring_contract_address = config['dao']['event_monitoring_contract_address']
checksum_address = Web3.to_checksum_address(event_monitoring_contract_address)

# Initialize DAO Contract for event monitoring
dao_contract = w3.eth.contract(address=checksum_address, abi=dao_contract_abi)
logging.info("DAO contract for event monitoring initialized")

# Frontend display contract address from config
frontend_display_contract_address = config['dao']['frontend_display_contract_address']

# Load link format from config
environment = config['links']['environment'].strip()
base_url_key = f"{environment}_base_url"
base_url = config['links'][base_url_key].strip()
if not base_url.endswith('/'):
    base_url += '/'
base_url += "proposals/"

# Determine the chain prefix based on the environment
if environment == 'dev':
    chain_prefix = 'eth'
else:
    chain_prefix = 'eth'

# Telegram configuration
telegram_bot_token = config['telegram']['bot_token']
telegram_chat_id = config['telegram']['chat_id']

# User preferences file
PREFERENCES_FILE = 'user_preferences.json'

# Read reminder intervals from config
def parse_intervals(value):
    value = value.split('#')[0]  # Remove any inline comments
    return [float(x.strip()) for x in value.split(',') if x.strip()]

reminders_from_start = parse_intervals(config['reminders']['reminders_from_start'])
reminders_before_end = parse_intervals(config['reminders']['reminders_before_end'])
button_reminder_times = parse_intervals(config['reminders']['button_reminders'])

# Snapshot configuration
snapshot_space = config['snapshot']['space']
snapshot_poll_interval = int(config['snapshot']['poll_interval'])

# Function to load user preferences
def load_user_preferences():
    if os.path.exists(PREFERENCES_FILE):
        with open(PREFERENCES_FILE, 'r') as file:
            return json.load(file)
    else:
        return {"reminders": {}}

# Function to save user preferences
def save_user_preferences(preferences):
    with open(PREFERENCES_FILE, 'w') as file:
        json.dump(preferences, file)

# Mapping file to store short IDs
PROPOSAL_ID_MAP_FILE = 'proposal_id_map.json'

def load_proposal_id_map():
    if os.path.exists(PROPOSAL_ID_MAP_FILE):
        with open(PROPOSAL_ID_MAP_FILE, 'r') as file:
            return json.load(file)
    else:
        return {}

def save_proposal_id_map(proposal_id_map):
    with open(PROPOSAL_ID_MAP_FILE, 'w') as file:
        json.dump(proposal_id_map, file)

# Dictionary to store scheduled jobs for each proposal and user
SCHEDULED_JOBS = {}

# Function to send reminder message
async def send_reminder_message(context):
    chat_id, proposal_id, message_text, buttons = context.job.data
    logging.info(f"Sending reminder to chat {chat_id} for proposal {proposal_id}")
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML'  # Use HTML mode for formatting
        )
    except Exception as e:
        logging.error(f"Failed to send message to chat {chat_id}: {e}")


# Function to cancel all scheduled reminders for a user and proposal
def cancel_scheduled_reminders(chat_id, proposal_id):
    if str(chat_id) in SCHEDULED_JOBS and proposal_id in SCHEDULED_JOBS[str(chat_id)]:
        jobs = SCHEDULED_JOBS[str(chat_id)][proposal_id]
        for job in jobs:
            try:
                # Check if the job still exists in the job queue before removing
                if job.removed is False:
                    job.schedule_removal()
                    logging.info(f"Job {job} for proposal {proposal_id} removed.")
                else:
                    logging.warning(f"Job {job} for proposal {proposal_id} already executed or removed.")
            except Exception as e:
                logging.error(f"Error removing job {job}: {e}")
        del SCHEDULED_JOBS[str(chat_id)][proposal_id]
        logging.info(f"Cancelled all scheduled reminders for chat_id {chat_id} and proposal {proposal_id}")
    else:
        logging.warning(f"No scheduled jobs found for chat_id {chat_id} and proposal {proposal_id}.")


# Button callback handler
async def button_callback(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    data = query.data.split('|')
    action = data[0]
    short_id = data[1]

    # Load the proposal ID map
    proposal_id_map = load_proposal_id_map()
    short_id_to_proposal_id = {v: k for k, v in proposal_id_map.items()}  # Reverse the map to get proposal_id from short_id

    if short_id not in short_id_to_proposal_id:
        logging.error(f"Short ID {short_id} not found in proposal ID map.")
        await query.answer(text="An error occurred. Please try again later.")
        return

    proposal_id = short_id_to_proposal_id[short_id]
    preferences = load_user_preferences()

    logging.info(f"Button callback received: action={action}, proposal_id={proposal_id}, chat_id={chat_id}")

    if action == 'voted':
        # Mark the proposal as voted for the user
        preferences["reminders"].setdefault(str(chat_id), {})[proposal_id] = "voted"
        save_user_preferences(preferences)

        # Cancel all future reminders for this proposal
        cancel_scheduled_reminders(chat_id, proposal_id)

        await context.bot.send_message(chat_id=chat_id, text="<b>Thanks for voting!</b> No more reminders for this vote.", parse_mode='HTML')
    elif action == 'remind_in':
        remind_in_hours = float(data[2])
        next_reminder_time = datetime.now(timezone.utc) + timedelta(hours=remind_in_hours)
    
        # Save reminder time in preferences
        preferences["reminders"].setdefault(str(chat_id), {})[proposal_id] = next_reminder_time.isoformat()
        save_user_preferences(preferences)

        # Schedule reminder
        logging.info(f"Scheduling a reminder for chat {chat_id} in {remind_in_hours} hours (at {next_reminder_time})")

        buttons = create_inline_buttons(short_id)
        message_text = (
            f"Reminder: Time to vote on '<b>{proposal_id}</b>'!\n\n"
            f"Proposal ID: <code>{proposal_id}</code>\n"
        )

        # Schedule the job in the job queue
        job = context.job_queue.run_once(
            send_reminder_message,
            when=next_reminder_time,
            data=(chat_id, proposal_id, message_text, buttons)
        )

         # Track job in SCHEDULED_JOBS
        if str(chat_id) not in SCHEDULED_JOBS:
            SCHEDULED_JOBS[str(chat_id)] = {}
        if proposal_id not in SCHEDULED_JOBS[str(chat_id)]:
            SCHEDULED_JOBS[str(chat_id)][proposal_id] = []

        SCHEDULED_JOBS[str(chat_id)][proposal_id].append(job)

        await context.bot.send_message(chat_id=chat_id, text=f"<b>Reminder set</b> for {remind_in_hours} hours from now.", parse_mode='HTML')
    else:
        logging.warning(f"Unknown action '{action}' in button callback.")

    await query.answer()

# Function to get reminder intervals (user-configurable or default)
def get_reminder_intervals(chat_id, proposal_id):
    preferences = load_user_preferences()
    user_reminders = preferences.get("reminders", {}).get(str(chat_id), {}).get(proposal_id, {})

    from_start = user_reminders.get('from_start', reminders_from_start)
    before_end = user_reminders.get('before_end', reminders_before_end)

    return from_start, before_end

# File to store known proposals
KNOWN_PROPOSALS_FILE = 'known_snapshot_proposals.json'

def load_known_proposals():
    if os.path.exists(KNOWN_PROPOSALS_FILE):
        with open(KNOWN_PROPOSALS_FILE, 'r') as file:
            return set(json.load(file))
    else:
        return set()

def save_known_proposals(known_proposals):
    with open(KNOWN_PROPOSALS_FILE, 'w') as file:
        json.dump(list(known_proposals), file)

# Snapshot monitoring function
async def monitor_snapshot_proposals(app):
    known_proposals = load_known_proposals()
    while True:
        try:
            logging.info("Checking for new Snapshot proposals...")
            url = "https://hub.snapshot.org/graphql"
            query = '''
            query Proposals($space: String!) {
                proposals(first: 3, skip: 0, where: {space_in: [$space]}, orderBy: "created", orderDirection: desc) {
                    id
                    title
                    start
                    end
                    created
                }
            }
            '''
            variables = {"space": snapshot_space}
            response = requests.post(url, json={'query': query, 'variables': variables})
            data = response.json()

            if 'errors' in data:
                logging.error(f"Snapshot API returned errors: {data['errors']}")
                await asyncio.sleep(snapshot_poll_interval)
                continue

            proposals = data.get('data', {}).get('proposals', [])
            logging.info(f"Fetched {len(proposals)} proposals from Snapshot.")

            for proposal in reversed(proposals):
                proposal_id = proposal['id']
                title = proposal['title']
                logging.info(f"Processing proposal: {title} ({proposal_id})")

                if proposal_id in known_proposals:
                    logging.info(f"Proposal {proposal_id} already processed.")
                    continue

                known_proposals.add(proposal_id)
                save_known_proposals(known_proposals)

                start_time = datetime.fromtimestamp(proposal['start'], tz=timezone.utc)
                end_time = datetime.fromtimestamp(proposal['end'], tz=timezone.utc)
                logging.info(f"New Snapshot proposal detected: {title} ({proposal_id})")
                await handle_new_proposal(proposal_id, title, start_time, end_time, app, proposal_type='snapshot')

            await asyncio.sleep(snapshot_poll_interval)
        except Exception as e:
            logging.error(f"Error in monitoring Snapshot proposals: {str(e)}")
            await asyncio.sleep(snapshot_poll_interval)

# Async function to monitor new on-chain proposals
async def monitor_new_proposals_async(event_filter, poll_interval, app):
    while True:
        try:
            logging.info("Checking for new on-chain proposals...")
            events = event_filter.get_new_entries()
            if events:
                logging.info(f"Found {len(events)} new on-chain proposal(s).")
            for event in events:
                proposal_id = event.args.proposalId
                voting_end_block = event.args.votingEndBlock
                logging.info(f"New on-chain proposal detected: Proposal ID {proposal_id}")

                # Estimate end_time from voting_end_block
                current_block = w3.eth.block_number
                blocks_remaining = voting_end_block - current_block
                average_block_time = 12  # Average Ethereum block time in seconds
                end_time = datetime.now(timezone.utc) + timedelta(seconds=blocks_remaining * average_block_time)
                start_time = datetime.now(timezone.utc)
                title = f"On-Chain Proposal {proposal_id}"

                await handle_new_proposal(str(proposal_id), title, start_time, end_time, app, proposal_type='on-chain')
            await asyncio.sleep(poll_interval)
        except Exception as e:
            logging.error(f"Error in monitoring on-chain proposals: {str(e)}")
            await asyncio.sleep(poll_interval)

# Handle new proposals and schedule reminders
async def handle_new_proposal(proposal_id, title, start_time, end_time, app, proposal_type):
    preferences = load_user_preferences()
    proposal_id_map = load_proposal_id_map()

    # Generate a short ID if not already generated
    if proposal_id not in proposal_id_map:
        short_id = str(uuid.uuid4())[:8]
        proposal_id_map[proposal_id] = short_id
        save_proposal_id_map(proposal_id_map)
        logging.info(f"Generated short ID {short_id} for proposal {proposal_id}")
    else:
        short_id = proposal_id_map[proposal_id]

    logging.info(f"Handling new proposal {proposal_id}. Registered users: {list(preferences['reminders'].keys())}")

    for chat_id in preferences["reminders"]:
        if proposal_id not in preferences["reminders"][chat_id]:
            preferences["reminders"][chat_id][proposal_id] = None
            logging.info(f"Scheduling reminders for chat_id {chat_id} and proposal {proposal_id}")
            await schedule_reminders(app, chat_id, proposal_id, short_id, title, start_time, end_time, proposal_type)
        else:
            logging.info(f"Reminders already scheduled for chat_id {chat_id} and proposal {proposal_id}")

    save_user_preferences(preferences)

# Function to create dynamic inline buttons based on config
def create_inline_buttons(short_id):
    buttons = [[InlineKeyboardButton("I have already voted", callback_data=f'voted|{short_id}')]]
    
    for hours in button_reminder_times:
        # Format hours as an integer if it's a whole number
        formatted_hours = int(hours) if hours.is_integer() else hours
        buttons.append([InlineKeyboardButton(f"Remind me in {formatted_hours} hour(s)", callback_data=f'remind_in|{short_id}|{hours}')])
    
    return buttons


# Function to schedule reminders
async def schedule_reminders(app, chat_id, proposal_id, short_id, title, start_time, end_time, proposal_type):
    job_queue = app.job_queue

    now = datetime.now(timezone.utc)
    logging.info(f"Scheduling reminders for chat_id {chat_id}, proposal {proposal_id}")

    # Get the intervals (default or user-configurable)
    from_start_intervals, before_end_intervals = get_reminder_intervals(chat_id, proposal_id)

    # Construct the proposal link
    if proposal_type == 'snapshot':
        proposal_link = f"https://snapshot.org/#/{snapshot_space}/proposal/{proposal_id}"
    elif proposal_type == 'on-chain':
        proposal_link = f"{base_url}{proposal_id}?dao={chain_prefix}:{frontend_display_contract_address}"
    else:
        proposal_link = ''

    # Store jobs for tracking
    if str(chat_id) not in SCHEDULED_JOBS:
        SCHEDULED_JOBS[str(chat_id)] = {}
    SCHEDULED_JOBS[str(chat_id)][proposal_id] = []

    # Reminders from start time
    for hours_after_start in from_start_intervals:
        when = start_time + timedelta(hours=hours_after_start)
        if when < now:
            logging.warning(f"Scheduled time {when} is in the past. Skipping reminder.")
            continue
        buttons = create_inline_buttons(short_id)
        
        
        
        message_text = (
            f"Voting has started for proposal '<b>{title}</b>'. Don't forget to vote!\n\n"
            f"Proposal ID: <code>{proposal_id}</code>\n"
            f"<a href='{proposal_link}'>View Proposal</a>"
        )

        job = job_queue.run_once(
            send_reminder_message,
            when=when,
            data=(chat_id, proposal_id, message_text, buttons)
        )
        SCHEDULED_JOBS[str(chat_id)][proposal_id].append(job)
        logging.info(f"Scheduled reminder for proposal {proposal_id} at {when.isoformat()} for chat {chat_id}")

    # Reminders before end time
    for hours_before_end in before_end_intervals:
        when = end_time - timedelta(hours=hours_before_end)
        if when < now:
            logging.warning(f"Scheduled time {when} is in the past. Skipping reminder.")
            continue
        buttons = create_inline_buttons(short_id)
        minutes_left = int(hours_before_end * 60)
        message_text = (
            f"{minutes_left} minutes left to vote on proposal '{title}'. Don't miss out!\n\n"
            f"Proposal ID: {proposal_id}\n"
            f"[View Proposal]({proposal_link})"
        )
        job = job_queue.run_once(
            send_reminder_message,
            when=when,
            data=(chat_id, proposal_id, message_text, buttons)
        )
        SCHEDULED_JOBS[str(chat_id)][proposal_id].append(job)
        logging.info(f"Scheduled reminder for proposal {proposal_id} at {when.isoformat()} for chat {chat_id}")

# Start command to add users to reminders list
async def start(update, context):
    chat_id = update.message.chat_id
    preferences = load_user_preferences()

    logging.info(f"Received /start command from chat_id: {chat_id}")

    if str(chat_id) not in preferences["reminders"]:
        preferences["reminders"][str(chat_id)] = {}
        save_user_preferences(preferences)
        logging.info(f"Added chat_id {chat_id} to user preferences.")
    else:
        logging.info(f"Chat_id {chat_id} is already registered.")

    await context.bot.send_message(chat_id=chat_id, text="<b>You've been added to the reminder list</b> for DAO votes!", parse_mode='HTML')

# Command to simulate a new proposal for testing
async def test_proposal(update, context):
    chat_id = update.message.chat_id
    proposal_id = 'test_proposal_id_' + str(uuid.uuid4())
    title = 'Test Proposal'
    start_time = datetime.now(timezone.utc) + timedelta(seconds=5)
    end_time = datetime.now(timezone.utc) + timedelta(minutes=2)

    logging.info(f"Creating test proposal with ID {proposal_id}.")

    await handle_new_proposal(proposal_id, title, start_time, end_time, context.application, proposal_type='snapshot')
    await context.bot.send_message(chat_id=chat_id, text=f"Test proposal created with ID {proposal_id} and reminders scheduled.")

# Post initialization function
async def post_init(application):
    proposal_initialized_filter = dao_contract.events.ProposalInitialized.create_filter(fromBlock="latest")
    logging.info("ProposalInitialized event filter created")
    on_chain_poll_interval = 10

    application.create_task(
        monitor_new_proposals_async(proposal_initialized_filter, on_chain_poll_interval, application)
    )
    logging.info("Started on-chain proposal monitoring task")

    application.create_task(
        monitor_snapshot_proposals(application)
    )
    logging.info("Started Snapshot proposal monitoring task")

# Main Execution
def main():
    app = ApplicationBuilder().token(telegram_bot_token).post_init(post_init).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('testproposal', test_proposal))
    app.add_handler(CallbackQueryHandler(button_callback))

    app.run_polling()

if __name__ == "__main__":
    main()
