# Telegram Balance Monitoring Bot

A robust asynchronous Telegram bot designed to monitor financial balances across various API services (Zadarma, DIDWW) and manual subscription services (Wazzup, Streamtele, Callii). 

The bot runs background scheduled tasks to check for low balances and notifies a specific administrative chat.

## Features

* **API Integration**: Real-time balance checking for Zadarma and DIDWW.
* **Manual Tracking**: State management for services without APIs (Wazzup, Callii) via FSM (Finite State Machine).
* **Recurring Payments**: Automatic tracking of monthly subscriptions and daily usage costs.
* **Alerts**: 
    * Low balance notifications.
    * Monthly payment reminders.
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
    git clone <repository-url>
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
    Create a `.env` file in the root directory (see `.env.example`).

5.  **Run the bot:**
    ```bash
    python main.py
    ```

## Project Structure

* `main.py`: Entry point and scheduler loop.
* `config.py`: Configuration and environment variable management.
* `db/`: Database models and initialization.
* `handlers/`: Telegram message and callback handlers.
* `services/`: External API clients.
* `scheduler/`: Background job logic.