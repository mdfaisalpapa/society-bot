# Society Bot 🏢

A Flask-based Telegram bot middleware designed to interface seamlessly with ERPNext for comprehensive property and society management.

This bot acts as a conversational interface for residents, allowing them to manage their profiles, register tenants, raise maintenance tickets with photo attachments, and invite visitors—all routed directly into your backend ERPNext database.

## 🌟 Key Features

* **Resident Onboarding:** Secure, phone-number-verified registration workflow mapping Telegram users to their ERPNext flat records.
* **Maintenance Ticketing:** Interactive wizard to raise tickets by category, complete with multipart photo upload support directly to ERPNext document attachments.
* **Tenant & Visitor Management:** Step-by-step conversational flows to capture structured data (dates, relationships, contact info) and save it as Customer/Visitor records.
* **Profile Dashboard:** An inline-keyboard hub for users to view their active status, parking slots, and update their contact details.
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
