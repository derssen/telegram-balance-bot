# Telegram Balance Monitoring Bot

A robust asynchronous Telegram bot designed to monitor financial balances across various API services (**Zadarma**, **DIDWW**, **Make**) and manual subscription services (**Wazzup**, **Streamtele**, **Callii**).

The bot runs background scheduled tasks to check for low balances, calculates credit "runway" (burn rate), and notifies a specific administrative chat.

## Features

* **API Integration**:
    * **Zadarma & DIDWW**: Real-time balance checking.
    * **Make (Integromat)**: Monitoring of "Operations" credits, automatic subscription date synchronization, and advanced "Burn Rate" calculation (predicts if credits will run out before the monthly reset).
* **Manual Tracking**: State management for services without APIs (Wazzup, Callii) via FSM (Finite State Machine).
* **Recurring Payments**: Automatic tracking of monthly subscriptions and daily usage costs.
* **Smart Alerts**:
    * Low balance notifications.
    * Monthly payment reminders (1 day in advance).
    * "Friday Look-ahead": Checks if funds will last through the weekend.
    * Daily top-up reminders for high-consumption services.
* **Security**: Restricted access to a specific target chat ID.

## Tech Stack

* **Python 3.10+**
* **aiogram 3.x**: Asynchronous framework for Telegram Bot API.
* **SQLAlchemy + aiosqlite**: Asynchronous ORM for SQLite database.
* **aiohttp**: Asynchronous HTTP client for API requests.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/derssen/telegram-balance-bot.git](https://github.com/derssen/telegram-balance-bot.git)
    cd telegram-balance-bot
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration:**
    Create a `.env` file in the root directory:
    ```env
    # Telegram
    BOT_TOKEN=your_bot_token
    TARGET_CHAT_ID=your_admin_chat_id

    # Database
    DATABASE_URL=sqlite+aiosqlite:///bot_db.sqlite3

    # API Credentials (leave empty to disable service)
    ZADARMA_KEY=
    ZADARMA_SECRET=
    DIDWW_KEY=

    # Make (Integromat)
    MAKE_API_KEY=your_token
    MAKE_ORG_ID=your_org_id
    MAKE_ZONE=eu1  # 'eu1' (default) or 'us1'

    # Manual Services Costs
    WAZZUP_DAILY_COST=400.0
    CALLII_DAILY_COST=2.2
    ```

5.  **Run the bot:**
    ```bash
    python main.py
    ```

## Project Structure

* `main.py`: Entry point and scheduler loop.
* `config.py`: Configuration and environment variable management.
* `db/`: Database models and initialization.
* `handlers/`: Telegram message and callback handlers.
* `services/`: External API clients (Zadarma, DIDWW, Make).
* `scheduler/`: Background job logic (API checks, daily deductions, planned alerts).

## License

This project is open-source and available under the MIT License.