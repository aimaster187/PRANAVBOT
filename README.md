# 🤖 Professional Telegram Bot

A production-ready Telegram Bot built with Python (`pyTelegramBotAPI`), SQLite3, and a modular architecture.

---

## ✨ Features

- **Interactive Inline Keyboards:** Multi-level responsive menu system (Services, User Profile, Analytics, FAQ, Support).
- **SQLite3 Database Integration:**
  - Automated database schema setup
  - User registration & tracking (`last_active`, `joined_at`)
  - Ban / Unban status enforcement
  - Audit logging of all actions
  - User feedback & ticketing system
- **Comprehensive Admin Panel:**
  - `/admin` — Inline control dashboard
  - `/stats` — Real-time user metrics & analytics
  - `/ban <user_id>` & `/unban <user_id>` — Immediate moderation
  - `/broadcast <msg>` — Send instant announcements to active users
  - Paginated user directory with status badges
- **Error Handling & Robust Logging:**
  - `safe_handler` decorator catches unexpected exceptions
  - Formatted logs to both console and `bot_activity.log` file
  - Graceful handling of blocked users during broadcasts
- **Environment Configurable:**
  - Works with environment variables or `config.py`

---

## 📁 Project Structure

