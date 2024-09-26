## DAO Governance Assistant Bot Documentation

### Overview

This Telegram bot is designed to assist with managing governance for DAOs, specifically focused on **Snapshot** (off-chain voting) and **Decent** (an on-chain voting framework using Safe). While today it serves primarily as a reminder bot, it includes a key feature—**users can switch off reminders once they've voted**, providing flexibility and control over notifications.

The vision for this bot extends far beyond reminders. Eventually, it aims to become a **general DAO governance assistant** that leverages **LLM (Large Language Models)** and **agent frameworks** to:
- **Summarize proposals** for easier comprehension,
- **Automate voting** based on pre-set conditions or preferences,
- **Assist in writing proposals** for DAO governance.

For now, the bot focuses on notifying users about governance proposals on Snapshot and Decent, ensuring timely participation while minimizing unnecessary notifications.

---

### Features

- **Supports Snapshot and Decent**: Tracks both Snapshot (off-chain) proposals and Decent (on-chain) voting via Safe.
- **Customizable Reminders**: Reminders can be set to notify users at specific intervals after a proposal starts or before it ends.
- **Inline Buttons for Interaction**: Users can mark a proposal as "voted" to stop receiving reminders, or set new reminder intervals.
- **Stop Reminders on Voting**: Once a user confirms they've voted, all future reminders for that specific proposal are automatically canceled.
- **HTML-formatted Messages**: Ensures messages are displayed correctly on Telegram using HTML.

### Future Vision

The long-term goal is to evolve this bot into a fully-fledged **DAO governance assistant** with the following capabilities:
- **Proposal Summarization**: Automatically generate summaries of long or complex proposals using advanced language models.
- **Automated Voting**: Provide smart voting features based on user preferences and predetermined conditions.
- **Proposal Creation**: Help DAOs draft and refine proposals, automating much of the governance process.

This future would allow DAO participants to focus on high-level decision-making while the assistant handles tedious governance tasks.

---

### Setup Instructions

#### Prerequisites

- **Python**: Ensure you have Python 3.7 or higher installed.
- **Telegram Bot API Token**: Create a bot using BotFather on Telegram and obtain the API token.
- **Infura Project ID**: For Ethereum interaction, create an Infura project and get your Project ID.
- **Etherscan API Key**: Create an Etherscan account and obtain an API key for fetching smart contract data.
- **Additional Requirements**: Install the required Python packages using `pip install -r requirements.txt`.

#### Configuration

The bot uses a `config.ini` file to manage API keys, contract addresses, and other settings. The configuration file should look like this:

```ini
[web3]
infura_url = https://mainnet.infura.io/v3/<your_infura_project_id>

[etherscan]
api_url = https://api.etherscan.io/api
api_key = <your_etherscan_api_key>

[dao]
event_monitoring_contract_address = <your_contract_address>
frontend_display_contract_address = <your_frontend_contract_address>

[telegram]
bot_token = <your_telegram_bot_token>
chat_id = <your_telegram_chat_id>

[links]
dev_base_url = https://app.decentdao.org/
non_dev_base_url = https://app.decentdao.org/
environment = dev

[snapshot]
space = <your_snapshot_space>
poll_interval = 60  # In seconds

[reminders]
reminders_from_start = 0, 1, 2
reminders_before_end = 24, 4
button_reminders = 0.5, 1, 2
```

---

### Running the Bot

1. **Clone the Repository**:
   ```bash
   git clone <repository_url>
   cd <repository_directory>
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Bot**:
   ```bash
   python bot.py
   ```

The bot will start running, monitoring the Snapshot space and Decent-based on-chain proposals, while automatically scheduling reminders for users.

---

### Key Functions

#### 1. `button_callback`
Handles user interactions with inline buttons (e.g., "I have already voted" or "Remind me in 1 hour").

- **Usage**:
  When a user clicks an inline button, this function processes the request. If the user marks a proposal as voted, it cancels all future reminders for that proposal.

#### 2. `schedule_reminders`
Schedules reminders for both on-chain (Decent) and Snapshot proposals based on configuration settings.

- **Usage**:
  When a new proposal is detected, this function is responsible for scheduling reminders at the specified intervals. It tracks the jobs to allow for cancellation when necessary.

#### 3. `send_reminder_message`
Sends a reminder message to users at a scheduled time, displaying the current status of the proposal and offering inline buttons for interaction.

- **Usage**:
  This function is called by the job scheduler to remind users to vote on proposals. It uses HTML formatting for proper display in Telegram.

#### 4. `monitor_snapshot_proposals`
Monitors a Snapshot space for new proposals by querying the Snapshot API. If a new proposal is detected, it schedules reminders for the users.

- **Usage**:
  This function runs periodically (based on the `poll_interval` in the config file) to check for new Snapshot proposals.

#### 5. `monitor_new_proposals_async`
Monitors Decent-based on-chain proposals via Ethereum, fetching new events from the DAO's smart contract. Reminders are scheduled accordingly.

- **Usage**:
  Similar to Snapshot proposals, this function continuously checks for new on-chain proposals and schedules reminders based on block timing.

---

### User Interaction

#### Commands

- **/start**: Adds the user to the reminder list for DAO votes.
  - The bot sends a confirmation message using HTML formatting to confirm the user has been added.

- **/testproposal**: Creates a test proposal and schedules reminders.
  - This command simulates a proposal and schedules reminders for testing purposes.

#### Inline Buttons

- **I have already voted**: Cancels all future reminders for the specific proposal.
- **Remind me in X hour(s)**: Schedules a follow-up reminder for the user at the specified interval.

---

### Handling Errors

The bot logs all errors using Python’s `logging` module. If an error occurs (e.g., when removing a job that no longer exists), the bot logs the details to help with debugging without disrupting the main functionality.

Example error logging:

```python
logging.error(f"Error removing job {job}: {e}")
```

Ensure to check the logs for detailed information when debugging issues.

---

### Future Improvements

The long-term goal for this bot is to evolve into a **general DAO governance assistant**, capable of:
- **Summarizing proposals** using advanced language models (LLMs) to provide easily digestible insights for DAO participants.
- **Automating voting** based on preset conditions or user preferences.
- **Writing proposals**: Assist DAOs in drafting and automating the creation of governance proposals.

By integrating features like proposal summarization, automated voting, and proposal writing, this bot aims to handle most of the tedious governance tasks, allowing DAO members to focus on strategic decision-making.

