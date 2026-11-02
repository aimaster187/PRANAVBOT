"""
Professional Telegram Bot Script
Features:
- Telebot framework with robust error handling decorators
- SQLite database integration
- Interactive Inline Keyboards and stateful navigation
- Admin management (Stats, Broadcast, Ban, Unban, User Audit)
- Detailed logging to console & file
"""
import os
import sys
import logging
import functools
import math
from typing import Callable, Any

import telebot
from telebot import types

import config
from database import Database
import keyboards

# Configure Logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("ProfessionalBot")

# Initialize Database and Bot
db = Database(config.DB_NAME)
bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML")

# In-memory temporary state tracker (e.g. for broadcast/feedback prompts)
user_states = {}


# ============================================================================
# HELPER DECORATORS & GUARDS
# ============================================================================

def safe_handler(func: Callable) -> Callable:
    """Decorator to catch unexpected exceptions gracefully and log them."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except telebot.apihelper.ApiTelegramException as tg_err:
            logger.error(f"Telegram API error in {func.__name__}: {tg_err}")
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {e}")
    return wrapper


def check_banned(handler_func: Callable) -> Callable:
    """Guard to prevent banned users from interacting."""
    @functools.wraps(handler_func)
    def wrapper(message_or_call, *args, **kwargs) -> Any:
        user_id = message_or_call.from_user.id
        if db.is_user_banned(user_id):
            ban_notice = "🚫 <b>Account Suspended</b>\n\nYour account has been restricted from using this service. Please contact support if you believe this is an error."
            if isinstance(message_or_call, types.CallbackQuery):
                bot.answer_callback_query(message_or_call.id, "Access Denied: You are banned.", show_alert=True)
                try:
                    bot.edit_message_text(ban_notice, message_or_call.message.chat.id, message_or_call.message.message_id)
                except Exception:
                    pass
            else:
                bot.send_message(message_or_call.chat.id, ban_notice)
            return None
        return handler_func(message_or_call, *args, **kwargs)
    return wrapper


def admin_only(handler_func: Callable) -> Callable:
    """Guard to ensure only admins can execute commands/callbacks."""
    @functools.wraps(handler_func)
    def wrapper(message_or_call, *args, **kwargs) -> Any:
        user_id = message_or_call.from_user.id
        user_data = db.get_user(user_id)
        is_admin = (user_id in config.ADMIN_IDS) or (user_data and user_data.get("is_admin") == 1)

        if not is_admin:
            msg = "⛔ <b>Permission Denied</b>\nThis action requires administrative privileges."
            if isinstance(message_or_call, types.CallbackQuery):
                bot.answer_callback_query(message_or_call.id, "Access Denied: Admins Only.", show_alert=True)
            else:
                bot.reply_to(message_or_call, msg)
            return None
        return handler_func(message_or_call, *args, **kwargs)
    return wrapper


# ============================================================================
# USER COMMAND HANDLERS
# ============================================================================

@bot.message_handler(commands=["start"])
@safe_handler
@check_banned
def command_start(message: types.Message):
    """Registers user and displays the welcome message with inline menu."""
    user = message.from_user
    is_admin = user.id in config.ADMIN_IDS
    
    is_new = db.register_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_admin=is_admin
    )
    
    greeting = f"👋 Welcome, <b>{user.first_name}</b>!" if not is_new else f"✨ Welcome aboard, <b>{user.first_name}</b>!"
    welcome_text = (
        f"{greeting}\n\n"
        f"I am <b>{config.BOT_NAME}</b> (v{config.BOT_VERSION}), designed to give you "
        f"a fast, seamless experience.\n\n"
        f"📌 <b>Features:</b>\n"
        f"• Interactive service catalog\n"
        f"• Account profile and status\n"
        f"• Live statistics and direct support\n\n"
        f"Select an option below to get started:"
    )
    
    markup = keyboards.main_menu_keyboard(is_admin=is_admin)
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)
    db.log_activity(user.id, "/start", "Started bot")


@bot.message_handler(commands=["help"])
@safe_handler
@check_banned
def command_help(message: types.Message):
    """Sends command reference and usage guidance."""
    help_text = (
        f"ℹ️ <b>Command Reference & Guide</b>\n\n"
        f"<b>General Commands:</b>\n"
        f"/start - Launch the interactive dashboard\n"
        f"/help - View this help documentation\n"
        f"/profile - View your user profile details\n"
        f"/support &lt;msg&gt; - Submit feedback or open a support request\n\n"
        f"<b>Admin Commands:</b>\n"
        f"/admin - Open administrator control dashboard\n"
        f"/stats - Instant real-time database metrics\n"
        f"/ban &lt;user_id&gt; - Restrict user from bot access\n"
        f"/unban &lt;user_id&gt; - Restore banned user access\n"
        f"/broadcast &lt;message&gt; - Send announcement to active users\n\n"
        f"Need custom assistance? Reach out to {config.SUPPORT_USERNAME}."
    )
    bot.send_message(message.chat.id, help_text, reply_markup=keyboards.back_to_main_keyboard())


@bot.message_handler(commands=["profile"])
@safe_handler
@check_banned
def command_profile(message: types.Message):
    """Shows user registration and status information."""
    user = message.from_user
    data = db.get_user(user.id)
    if not data:
        db.register_or_update_user(user.id, user.username, user.first_name, user.last_name)
        data = db.get_user(user.id)

    joined_date = data["joined_at"][:19] if data.get("joined_at") else "N/A"
    role = "🛡️ Administrator" if data.get("is_admin") else "👤 Standard Member"

    profile_text = (
        f"👤 <b>Your Account Profile</b>\n\n"
        f"<b>User ID:</b> <code>{data['user_id']}</code>\n"
        f"<b>Name:</b> {data.get('first_name') or ''} {data.get('last_name') or ''}\n"
        f"<b>Username:</b> @{data['username'] if data.get('username') else 'None'}\n"
        f"<b>Account Role:</b> {role}\n"
        f"<b>Member Since:</b> {joined_date} UTC\n"
        f"<b>Status:</b> 🟢 Active"
    )
    bot.send_message(message.chat.id, profile_text, reply_markup=keyboards.back_to_main_keyboard())


@bot.message_handler(commands=["support"])
@safe_handler
@check_banned
def command_support(message: types.Message):
    """Allows user to submit feedback directly via command."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(
            message,
            "⚠️ Please include your message.\n<b>Usage:</b> <code>/support My question or feedback here</code>"
        )
        return

    feedback_text = args[1].strip()
    ticket_id = db.add_feedback(message.from_user.id, feedback_text)
    bot.reply_to(
        message,
        f"✅ <b>Feedback Received!</b>\nTicket ID: <code>#{ticket_id}</code>\nOur team has been notified. Thank you!"
    )
    db.log_activity(message.from_user.id, "FEEDBACK", f"Ticket #{ticket_id}")


# ============================================================================
# ADMIN COMMANDS
# ============================================================================

@bot.message_handler(commands=["admin"])
@safe_handler
@check_banned
@admin_only
def command_admin(message: types.Message):
    """Opens administrative control dashboard."""
    counts = db.count_users()
    admin_text = (
        f"🛡️ <b>Administrator Control Center</b>\n\n"
        f"<b>Total Users:</b> {counts['total']}\n"
        f"<b>Active Users:</b> {counts['active']}\n"
        f"<b>Banned Users:</b> {counts['banned']}\n"
        f"<b>Administrators:</b> {counts['admins']}\n\n"
        f"Use the buttons below to perform administrative actions:"
    )
    bot.send_message(message.chat.id, admin_text, reply_markup=keyboards.admin_panel_keyboard())


@bot.message_handler(commands=["stats"])
@safe_handler
@check_banned
@admin_only
def command_stats(message: types.Message):
    """Shows detailed metrics."""
    counts = db.count_users()
    stats_msg = (
        f"📊 <b>System Analytics & Metrics</b>\n\n"
        f"👥 <b>Total Registered:</b> {counts['total']}\n"
        f"🟢 <b>Active Users:</b> {counts['active']}\n"
        f"🚫 <b>Banned Accounts:</b> {counts['banned']}\n"
        f"⭐ <b>Admin Staff:</b> {counts['admins']}\n"
        f"🗄️ <b>Database Engine:</b> SQLite3\n"
        f"🚀 <b>Bot Engine:</b> pyTelegramBotAPI"
    )
    bot.send_message(message.chat.id, stats_msg)


@bot.message_handler(commands=["ban"])
@safe_handler
@check_banned
@admin_only
def command_ban(message: types.Message):
    """Ban a user by ID."""
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/ban &lt;user_id&gt;</code>")
        return

    target_id = int(args[1])
    if target_id == message.from_user.id:
        bot.reply_to(message, "❌ You cannot ban yourself.")
        return

    target_user = db.get_user(target_id)
    if not target_user:
        bot.reply_to(message, f"❌ User ID <code>{target_id}</code> was not found in the database.")
        return

    db.set_user_ban_status(target_id, True)
    db.log_activity(message.from_user.id, "BAN_USER", f"Banned {target_id}")
    bot.reply_to(message, f"✅ User <code>{target_id}</code> has been banned successfully.")


@bot.message_handler(commands=["unban"])
@safe_handler
@check_banned
@admin_only
def command_unban(message: types.Message):
    """Unban a user by ID."""
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/unban &lt;user_id&gt;</code>")
        return

    target_id = int(args[1])
    target_user = db.get_user(target_id)
    if not target_user:
        bot.reply_to(message, f"❌ User ID <code>{target_id}</code> was not found.")
        return

    db.set_user_ban_status(target_id, False)
    db.log_activity(message.from_user.id, "UNBAN_USER", f"Unbanned {target_id}")
    bot.reply_to(message, f"✅ User <code>{target_id}</code> has been unbanned.")


@bot.message_handler(commands=["broadcast"])
@safe_handler
@check_banned
@admin_only
def command_broadcast(message: types.Message):
    """Broadcast an announcement to all active users."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/broadcast Your message content here</code>")
        return

    broadcast_content = args[1].strip()
    user_ids = db.get_all_user_ids(active_only=True)
    
    status_msg = bot.send_message(message.chat.id, f"⏳ Broadcasting message to {len(user_ids)} users...")
    success_count = 0
    fail_count = 0

    for uid in user_ids:
        try:
            bot.send_message(
                uid,
                f"📢 <b>Announcement:</b>\n\n{broadcast_content}"
            )
            success_count += 1
        except telebot.apihelper.ApiTelegramException as e:
            # If user blocked bot, handle gracefully
            fail_count += 1
            logger.warning(f"Could not deliver broadcast to {uid}: {e}")
        except Exception as e:
            fail_count += 1
            logger.error(f"Error delivering to {uid}: {e}")

    db.log_activity(message.from_user.id, "BROADCAST", f"Sent: {success_count}, Failed: {fail_count}")
    bot.edit_message_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"• Delivered: <b>{success_count}</b>\n"
        f"• Failed/Blocked: <b>{fail_count}</b>\n"
        f"• Total attempted: <b>{len(user_ids)}</b>",
        chat_id=message.chat.id,
        message_id=status_msg.message_id
    )


# ============================================================================
# CALLBACK QUERY ROUTING (INLINE KEYBOARD ACTIONS)
# ============================================================================

@bot.callback_query_handler(func=lambda call: True)
@safe_handler
@check_banned
def handle_callbacks(call: types.CallbackQuery):
    """Processes interactive inline menu clicks."""
    user_id = call.from_user.id
    data = call.data
    logger.debug(f"Callback received from {user_id}: {data}")

    # No-operation button (used for pagination headers)
    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    # Return to Main Menu
    if data == "menu_main":
        user_info = db.get_user(user_id)
        is_admin = (user_id in config.ADMIN_IDS) or (user_info and user_info.get("is_admin") == 1)
        welcome_text = (
            f"👋 Welcome back, <b>{call.from_user.first_name}</b>!\n\n"
            f"I am <b>{config.BOT_NAME}</b>. What would you like to explore today?"
        )
        bot.edit_message_text(
            welcome_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.main_menu_keyboard(is_admin=is_admin)
        )
        bot.answer_callback_query(call.id)
        return

    # Services Catalog
    if data == "menu_services":
        text = (
            f"💼 <b>Our Available Services</b>\n\n"
            f"Select a service below to explore features, specifications, and integrations."
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.services_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    # Specific Service details
    if data in ["service_api", "service_security", "service_cloud"]:
        details = {
            "service_api": "⚡ <b>Fast API Integration:</b> High throughput endpoints, REST & GraphQL with sub-50ms latency.",
            "service_security": "🔒 <b>Security Audits:</b> End-to-end encryption checks, token rotators, and vulnerability scans.",
            "service_cloud": "☁️ <b>Cloud Deployments:</b> Zero-downtime containerized releases on AWS, GCP, and self-hosted nodes."
        }
        bot.edit_message_text(
            f"{details[data]}\n\nContact support to request provisioning.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.services_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    # User Profile
    if data == "menu_profile":
        user_row = db.get_user(user_id)
        joined_str = user_row["joined_at"][:19] if user_row and user_row.get("joined_at") else "N/A"
        role = "🛡️ Administrator" if (user_row and user_row.get("is_admin")) else "👤 Standard Member"
        
        text = (
            f"👤 <b>Your Account Details</b>\n\n"
            f"<b>ID:</b> <code>{user_id}</code>\n"
            f"<b>Username:</b> @{call.from_user.username or 'None'}\n"
            f"<b>Role:</b> {role}\n"
            f"<b>Joined:</b> {joined_str} UTC\n"
            f"<b>Status:</b> 🟢 Active"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.back_to_main_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    # Bot Stats
    if data == "menu_stats":
        counts = db.count_users()
        text = (
            f"📊 <b>Public Statistics</b>\n\n"
            f"• <b>Active Community:</b> {counts['active']} users\n"
            f"• <b>Platform Uptime:</b> 99.98%\n"
            f"• <b>Bot Version:</b> {config.BOT_VERSION}\n"
            f"• <b>Engine:</b> Telebot + SQLite"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.back_to_main_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    # FAQ
    if data == "menu_faq":
        text = (
            f"❓ <b>Frequently Asked Questions</b>\n\n"
            f"<b>Q: Is my data safe?</b>\n"
            f"A: Yes. All data stored in SQLite is isolated and not shared.\n\n"
            f"<b>Q: How do I submit feedback?</b>\n"
            f"A: Use the Contact Support button or write <code>/support [message]</code>.\n\n"
            f"<b>Q: How do I become an admin?</b>\n"
            f"A: Administrator roles are managed by the bot owner in config."
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.back_to_main_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    # Support / Feedback prompt
    if data == "menu_feedback":
        user_states[user_id] = "AWAITING_FEEDBACK"
        text = (
            f"📩 <b>Contact Support & Feedback</b>\n\n"
            f"Please type and send your inquiry directly as your next message.\n"
            f"Or type /start to cancel."
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.back_to_main_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    # Admin Panel callback
    if data == "admin_panel":
        user_data = db.get_user(user_id)
        if not (user_id in config.ADMIN_IDS or (user_data and user_data.get("is_admin") == 1)):
            bot.answer_callback_query(call.id, "⛔ Administrator privileges required.", show_alert=True)
            return

        counts = db.count_users()
        text = (
            f"🛡️ <b>Administrator Dashboard</b>\n\n"
            f"• Total Users: <b>{counts['total']}</b>\n"
            f"• Active Users: <b>{counts['active']}</b>\n"
            f"• Banned: <b>{counts['banned']}</b>\n"
            f"• Admins: <b>{counts['admins']}</b>\n\n"
            f"Choose an administrative tool below:"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.admin_panel_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    # Admin: Analytics
    if data == "admin_analytics":
        counts = db.count_users()
        text = (
            f"📈 <b>Database Deep Dive</b>\n\n"
            f"Database File: <code>{config.DB_NAME}</code>\n"
            f"Total Members: <b>{counts['total']}</b>\n"
            f"Allowed Members: <b>{counts['active']}</b>\n"
            f"Restricted Members: <b>{counts['banned']}</b>"
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.admin_panel_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    # Admin: Users Pagination
    if data.startswith("admin_users"):
        page = 0
        if data.startswith("admin_users_page_"):
            try:
                page = int(data.split("_")[-1])
            except ValueError:
                page = 0

        page_size = 5
        counts = db.count_users()
        total_pages = max(1, math.ceil(counts["total"] / page_size))
        page = max(0, min(page, total_pages - 1))

        users = db.get_users_list(limit=page_size, offset=page * page_size)
        text_lines = [f"👥 <b>Registered Users (Page {page+1}/{total_pages}):</b>\n"]
        for u in users:
            status = "🚫" if u.get("is_banned") else "🟢"
            admin_badge = " [ADMIN]" if u.get("is_admin") else ""
            uname = f"@{u['username']}" if u.get("username") else "NoHandle"
            text_lines.append(f"{status} <code>{u['user_id']}</code> | {uname}{admin_badge}")

        bot.edit_message_text(
            "\n".join(text_lines),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.admin_user_list_keyboard(page=page, total_pages=total_pages)
        )
        bot.answer_callback_query(call.id)
        return

    # Admin: Broadcast instruction prompt
    if data == "admin_broadcast_prompt":
        user_states[user_id] = "AWAITING_BROADCAST"
        text = (
            f"📢 <b>Broadcast Announcement</b>\n\n"
            f"Please send the message you wish to broadcast to all active members.\n"
            f"Or send /admin to cancel."
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.admin_panel_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    # Admin: Ban help
    if data == "admin_ban_help":
        text = (
            f"🚫 <b>User Moderation Instructions</b>\n\n"
            f"• To ban a user: <code>/ban &lt;user_id&gt;</code>\n"
            f"• To unban a user: <code>/unban &lt;user_id&gt;</code>\n\n"
            f"Banned users will immediately lose access to all bot handlers and inline actions."
        )
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=keyboards.admin_panel_keyboard()
        )
        bot.answer_callback_query(call.id)
        return

    bot.answer_callback_query(call.id, "Option processed.")


# ============================================================================
# STATEFUL MESSAGE HANDLER (SUPPORT / BROADCAST PROMPTS)
# ============================================================================

@bot.message_handler(func=lambda msg: not msg.text.startswith("/"))
@safe_handler
@check_banned
def handle_generic_text(message: types.Message):
    """Handles text submissions when in a specific conversational state."""
    user_id = message.from_user.id
    current_state = user_states.get(user_id)

    # State: Awaiting feedback
    if current_state == "AWAITING_FEEDBACK":
        ticket_id = db.add_feedback(user_id, message.text.strip())
        user_states.pop(user_id, None)
        bot.reply_to(
            message,
            f"✅ Thank you! Your ticket <code>#{ticket_id}</code> has been logged.\n"
            f"Our team will review your inquiry shortly.",
            reply_markup=keyboards.back_to_main_keyboard()
        )
        db.log_activity(user_id, "FEEDBACK_SUBMITTED", f"Ticket #{ticket_id}")
        return

    # State: Admin broadcast submission
    if current_state == "AWAITING_BROADCAST":
        user_data = db.get_user(user_id)
        is_admin = (user_id in config.ADMIN_IDS) or (user_data and user_data.get("is_admin") == 1)
        if not is_admin:
            user_states.pop(user_id, None)
            return

        user_states.pop(user_id, None)
        broadcast_content = message.text.strip()
        user_ids = db.get_all_user_ids(active_only=True)

        prog_msg = bot.send_message(message.chat.id, f"⏳ Delivering announcement to {len(user_ids)} users...")
        sent, failed = 0, 0
        for uid in user_ids:
            try:
                bot.send_message(uid, f"📢 <b>Announcement:</b>\n\n{broadcast_content}")
                sent += 1
            except Exception:
                failed += 1

        db.log_activity(user_id, "BROADCAST_STATE", f"Sent {sent}, Failed {failed}")
        bot.edit_message_text(
            f"✅ <b>Broadcast Completed!</b>\n\n• Delivered: {sent}\n• Failed: {failed}",
            chat_id=message.chat.id,
            message_id=prog_msg.message_id,
            reply_markup=keyboards.admin_panel_keyboard()
        )
        return

    # Default message response
    bot.reply_to(
        message,
        "👋 I received your message. Use /start to access the interactive menu.",
        reply_markup=keyboards.back_to_main_keyboard()
    )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    logger.info("Starting Telegram Bot application...")
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.warning(
            "⚠️ BOT_TOKEN is still set to placeholder 'YOUR_BOT_TOKEN_HERE'.\n"
            "Please configure your token via BOT_TOKEN environment variable or edit config.py."
        )

    logger.info(f"Connected to database: {config.DB_NAME}")
    logger.info("Bot polling is active. Press Ctrl+C to terminate.")
    
    # Start bot polling with resilience
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=20)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot polling gracefully terminated.")
    except Exception as e:
        logger.critical(f"Fatal error during bot polling: {e}", exc_info=True)


if __name__ == "__main__":
    main()
