# Society Bot 🏢

A Flask-based Telegram bot middleware designed to interface seamlessly with ERPNext for comprehensive property and society management.

This bot acts as a conversational interface for residents, allowing them to manage their profiles, register tenants, raise maintenance tickets with photo attachments, and invite visitors—all routed directly into your backend ERPNext database.

## 🌟 Key Features

* **Resident Onboarding:** Secure, phone-number-verified registration workflow mapping Telegram users to their ERPNext flat records.(completed)
* **Maintenance Ticketing:** Interactive wizard to raise tickets by category, complete with multipart photo upload support directly to ERPNext document attachments.(completed)
* **Tenant & Visitor Management:** Step-by-step conversational flows to capture structured data (dates, relationships, contact info) and save it as Customer/Visitor records.(Work in Progress)
* **Profile Dashboard:** An inline-keyboard hub for users to view their active status, parking slots, and update their contact details.(Completed)
* **Webhook Architecture:** Built on Flask for instantaneous, push-based Telegram updates rather than slow polling.

---

## 🏗️ Architecture & Project Structure

The project follows a lean, layered middleware pattern:

```text
society-bot/
├── api/
│   └── erp.py                   # Handles all REST and Resource API calls to ERPNext
├── controllers/                 # Business logic and conversation wizards
│   ├── maintenance_controller.py
│   ├── profile_controller.py
│   ├── registration_controller.py
│   └── ...
├── conversation/                
│   ├── engine.py                # Parses incoming webhooks and routes to controllers
│   └── session.py               # Local SQLite session tracking for multi-step wizards
├── entities/
│   └── models.py                # Lightweight Python dataclasses (DTOs) for temporary state
├── services/                    # Outbound integrations and background tasks
│   ├── telegram.py              # Raw Telegram API calls (downloads, sending grids)
│   ├── messenger.py             # Abstraction layer for outbound messages
│   └── scheduler.py             # Background cron jobs (e.g., dues reminders)
├── utils/                       
│   ├── helpers.py               # Pure formatting functions (dates, text cleaning)
│   ├── keyboards.py             # Static Telegram inline button layouts
│   └── logger.py                # Centralized logging configuration
├── database/                    # Local SQLite storage for session state
├── .env                         # Environment variables (Ignored in git)
├── app.py                       # Main Flask webhook server
└── requirements.txt             # Python dependencies
```

---

## 🗄️ ERPNext Schema Requirements

To ensure the bot routes data correctly, your ERPNext instance must have the following Custom DocTypes and fields configured. 


### 1. DocType: `Resident Profile`
* `flat_number` (Data, Primary Key/Name)
* `display_name` (Data)
* `owner_phone` (Data)
* `tenant_phone` (Data)
* `is_rented` (Check)
* `active_email` (Data)
* `parking_slot` (Data)
* `telegram_chat_id` (Data - Used by the bot to link the user)

### 2. DocType: `Maintenance Ticket`
* `category` (Select: Plumbing, Electrical, Civil, Carpentry, Other)
* `description` (Small Text)
* `status` (Select: Open, In Progress, Closed)
* `photo` (Attach Image - Target for Telegram photo uploads)

### 3. DocType: `Visitor` (or Custom Visitor Log)
* `visitor_name` (Data)
* `mobile_no` (Data)
* `expected_arrival` (Datetime)

---

## ⚙️ Prerequisites

* Python 3.10+
* An active Telegram Bot Token (from [@BotFather](https://t.me/botfather))
* An ERPNext instance (tested with v15/v16) with API access enabled.
* API Key and API Secret generated for a user with appropriate permissions (e.g., System Manager) in ERPNext.

---

## 🚀 Installation

**1. Clone the repository and navigate to the directory:**
```bash
git clone [https://github.com/yourusername/society-bot.git](https://github.com/yourusername/society-bot.git)
cd society-bot
```

**2. Set up the Python virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configure your environment variables:**
Copy the example file and edit it with your live credentials.
```bash
cp .env.example .env
```

Ensure your `.env` looks like this:
```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ADMIN_CHAT_ID=your_admin_chat_id

# ERPNext Configuration
ERPNEXT_URL=[https://your-erpnext-instance.com](https://your-erpnext-instance.com)
ERPNEXT_API_KEY=your_api_key
ERPNEXT_API_SECRET=your_api_secret

# Flask Application
FLASK_PORT=5000
DEBUG=True

# Database
DATABASE_PATH=database/sessions.db
```

---

## 🛠️ Local Development & Testing

Because this bot uses webhooks rather than polling, Telegram needs a public URL to send messages to your local machine. 

**1. Start the Flask application:**
```bash
python3 app.py
```

**2. Expose your local server using ngrok:**
In a separate terminal window, run:
```bash
ngrok http 5000
```

**3. Register the Webhook with Telegram:**
Copy the `https://...` forwarding URL provided by ngrok and use your browser to register it:
```text
[https://api.telegram.org/bot](https://api.telegram.org/bot)<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_NGROK_URL>/webhook
```

---

## 🚢 Production Deployment

For production, it is recommended to run the Flask application using a production WSGI server like **Gunicorn** and manage the process using `systemd` or by containerizing the application with **Docker**. Ensure your web server (e.g., Nginx) is configured to handle SSL/TLS termination, as Telegram requires webhooks to be served over HTTPS.
