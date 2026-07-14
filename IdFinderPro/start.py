import os
import asyncio 
import pyrogram
import glob
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, UserAlreadyParticipant, InviteHashExpired, UsernameNotOccupied, UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message 
from config import API_ID, API_HASH, ERROR_MESSAGE, FORCE_SUB_CHANNEL, FORCE_SUB_CHANNEL_ID, ADMINS, LOG_CHANNEL_ID
from database.db import db
from IdFinderPro.strings import HELP_TXT

# Force subscription check
async def check_force_sub(client: Client, user_id: int):
    """Check if user has joined the force subscription channel"""
    try:
        member = await client.get_chat_member(FORCE_SUB_CHANNEL_ID, user_id)
        return member.status not in ["left", "kicked"]
    except UserNotParticipant:
        return False
    except Exception as e:
        print(f"Force sub check error: {e}")
        return True  # Don't block if error checking

class batch_temp(object):
    IS_BATCH = {}

# Active download processes tracking
active_processes = {}
# Structure: {message_id: {'user_id': int, 'user_name': str, 'filename': str, 'start_time': float, 'status': str}}

# Cleanup function to remove old status files and downloads on startup
def cleanup_old_files():
    """Remove old status files and downloads folder contents"""
    try:
        # Remove status files
        for file in glob.glob("*status.txt"):
            try:
                os.remove(file)
            except:
                pass
        
        # Clean downloads folder but keep the folder
        if os.path.exists("downloads"):
            for file in os.listdir("downloads"):
                file_path = os.path.join("downloads", file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except:
                    pass
        else:
            os.makedirs("downloads", exist_ok=True)
        
        print("[OK] Cleanup completed - old files removed")
    except Exception as e:
        print(f"[WARNING] Cleanup warning: {e}")

# Run cleanup on module load
cleanup_old_files()

async def downstatus(client, statusfile, message, chat):
    while True:
        if os.path.exists(statusfile):
            break

        await asyncio.sleep(3)
      
    while os.path.exists(statusfile):
        with open(statusfile, "r") as downread:
            txt = downread.read()
        try:
            await client.edit_message_text(chat, message.id, f"📥 **Downloading:** {txt}")
            await asyncio.sleep(10)
        except:
            await asyncio.sleep(5)


# upload status
async def upstatus(client, statusfile, message, chat):
    while True:
        if os.path.exists(statusfile):
            break

        await asyncio.sleep(3)      
    while os.path.exists(statusfile):
        with open(statusfile, "r") as upread:
            txt = upread.read()
        try:
            await client.edit_message_text(chat, message.id, f"📤 **Uploading:** {txt}")
            await asyncio.sleep(10)
        except:
            await asyncio.sleep(5)


# progress writer
def progress(current, total, message, type):
    with open(f'{message.id}{type}status.txt', "w") as fileup:
        fileup.write(f"{current * 100 / total:.1f}%")


# start command
@Client.on_message(filters.command(["start"]))
async def send_start(client: Client, message: Message):
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
    
    # Get user status
    user_data = await db.get_session(message.from_user.id)
    is_premium_user = await db.is_premium(message.from_user.id)
    downloads_today = await db.get_download_count(message.from_user.id)
    
    login_emoji = "✅" if user_data else "❌"
    premium_emoji = "💎" if is_premium_user else "🆓"
    limit = "Unlimited" if is_premium_user else 10
    
    start_text = f"""👋 **Welcome {message.from_user.first_name}!**

**📥 Restricted Content Download Bot**

{login_emoji} Login: {'Yes' if user_data else 'No - Use /login'}
{premium_emoji} Plan: {'Premium' if is_premium_user else 'Free'}
📊 Usage: {downloads_today}/{limit} downloads today

**Quick Start:**
1. Must join @{FORCE_SUB_CHANNEL}
2. Use /login to authenticate
3. Send any Telegram post link
4. Get your content!

**Commands:** Use /help
"""
    
    buttons = [[
        InlineKeyboardButton("📖 Help", callback_data="help"),
        InlineKeyboardButton("💎 Premium", callback_data="premium_info")
    ],[
        InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/tataa_sumo"),
        InlineKeyboardButton("📢 Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL}")
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await client.send_message(
        chat_id=message.chat.id, 
        text=start_text, 
        reply_markup=reply_markup, 
        reply_to_message_id=message.id
    )
    return


# help command
@Client.on_message(filters.command(["help"]))
async def send_help(client: Client, message: Message):
    from IdFinderPro.strings import HELP_TXT
    buttons = [[
        InlineKeyboardButton("📥 Download Guide", callback_data="download_help"),
        InlineKeyboardButton("💎 Premium Info", callback_data="premium_help")
    ],[
        InlineKeyboardButton("⚙️ Commands", callback_data="commands_help"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="start")
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await client.send_message(
        chat_id=message.chat.id, 
        text=HELP_TXT,
        reply_markup=reply_markup
    )

# cancel command
@Client.on_message(filters.command(["cancel"]))
async def send_cancel(client: Client, message: Message):
    batch_temp.IS_BATCH[message.from_user.id] = True
    await client.send_message(
        chat_id=message.chat.id, 
        text="✅ **Batch Download Cancelled Successfully!**\n\nYou can now start a new download."
    )

# Admin command
@Client.on_message(filters.command(["admin"]) & filters.user(ADMINS))
async def admin_panel(client: Client, message: Message):
    from config import ADMINS
    total_users = await db.total_users_count()
    premium_users = await db.get_all_premium_users()
    banned_users = await db.get_all_banned_users()
    
    admin_text = f"""**🔧 ADMIN PANEL**

📊 **Statistics:**
• Total Users: {total_users}
• Premium Users: {len(premium_users)}
• Banned Users: {len(banned_users)}
• Active Processes: {len(active_processes)}

**Commands:**
/generate - Generate redeem codes
/premiumlist - Manage premium users
/broadcast - Broadcast message
/processes - View active downloads
/exportdata - Export user database
/ban - Ban a user
/unban - Unban a user
/banlist - View banned users

**Quick Actions:**
"""
    buttons = [[
        InlineKeyboardButton("🎟️ Generate Code", callback_data="admin_generate"),
        InlineKeyboardButton("💎 Premium List", callback_data="admin_premiumlist")
    ],[
        InlineKeyboardButton("⚙️ Processes", callback_data="admin_processes"),
        InlineKeyboardButton("📊 Export Data", callback_data="admin_export")
    ],[
        InlineKeyboardButton("🚫 Ban List", callback_data="admin_banlist"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="start")
    ]]
    await message.reply(admin_text, reply_markup=InlineKeyboardMarkup(buttons))

# Ban user command
@Client.on_message(filters.command(["ban"]) & filters.user(ADMINS))
async def ban_user_cmd(client: Client, message: Message):
    """Ban a user from using the bot"""
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            return await message.reply("**Usage:** `/ban <user_id> [reason]`\n\nExample: `/ban 123456789 Downloading adult content`")
        
        user_id = int(parts[1])
        reason = parts[2] if len(parts) > 2 else "No reason provided"
        
        # Ban the user
        success = await db.ban_user(user_id, reason, message.from_user.id)
        
        if not success:
            return await message.reply(f"❌ **User `{user_id}` is already banned!**")
        
        # Try to notify the banned user
        try:
            await client.send_message(
                user_id,
                f"""🚫 **You have been banned from using this bot.**

**Reason:** {reason}

If you believe this is a mistake, please contact admin @tataa_sumo for unban.
"""
            )
            notified = "✅ User notified"
        except:
            notified = "⚠️ Could not notify user (they may have blocked the bot)"
        
        await message.reply(f"""✅ **User Banned Successfully!**

**User ID:** `{user_id}`
**Reason:** {reason}
**Status:** {notified}
""")
    
    except ValueError:
        await message.reply("❌ **Invalid user ID!** Please provide a valid numeric user ID.")
    except Exception as e:
        await message.reply(f"❌ **Error:** `{e}`")

# Unban user command
@Client.on_message(filters.command(["unban"]) & filters.user(ADMINS))
async def unban_user_cmd(client: Client, message: Message):
    """Unban a user"""
    try:
        parts = message.text.split()
        if len(parts) < 2:
            return await message.reply("**Usage:** `/unban <user_id>`\n\nExample: `/unban 123456789`")
        
        user_id = int(parts[1])
        
        # Unban the user
        success = await db.unban_user(user_id)
        
        if not success:
            return await message.reply(f"❌ **User `{user_id}` is not banned!**")
        
        # Try to notify the unbanned user
        try:
            await client.send_message(
                user_id,
                """✅ **You have been unbanned!**

You can now use this bot again. Welcome back!

Use /start to begin.
"""
            )
            notified = "✅ User notified"
        except:
            notified = "⚠️ Could not notify user (they may have blocked the bot)"
        
        await message.reply(f"""✅ **User Unbanned Successfully!**

**User ID:** `{user_id}`
**Status:** {notified}
""")
    
    except ValueError:
        await message.reply("❌ **Invalid user ID!** Please provide a valid numeric user ID.")
    except Exception as e:
        await message.reply(f"❌ **Error:** `{e}`")

# Banlist command
@Client.on_message(filters.command(["banlist"]) & filters.user(ADMINS))
async def banlist_cmd(client: Client, message: Message):
    """View all banned users"""
    from datetime import datetime
    
    banned_users = await db.get_all_banned_users()
    
    if not banned_users:
        return await message.reply("📭 **No banned users found.**")
    
    banlist_text = f"**🚫 BANNED USERS ({len(banned_users)})**\n\n"
    
    for i, user in enumerate(banned_users[:20], 1):  # Show first 20
        user_id = user.get('user_id')
        reason = user.get('reason', 'No reason')
        banned_at = user.get('banned_at')
        
        if banned_at:
            date_str = datetime.fromtimestamp(banned_at).strftime('%Y-%m-%d')
        else:
            date_str = 'Unknown'
        
        banlist_text += f"**{i}.** `{user_id}`\n   📝 {reason}\n   📅 {date_str}\n\n"
    
    if len(banned_users) > 20:
        banlist_text += f"\n_... and {len(banned_users) - 20} more_"
    
    await message.reply(banlist_text)


# Callback query handler for inline buttons
@Client.on_callback_query()
async def callback_handler(client: Client, query):
    from IdFinderPro.strings import HELP_TXT, DOWNLOAD_HELP, PREMIUM_HELP, COMMANDS_HELP
    data = query.data
    
    if data == "check_joined":
        # Check if user joined
        is_subscribed = await check_force_sub(client, query.from_user.id)
        if is_subscribed:
            await query.answer("✅ You're subscribed! Now send a link to download.", show_alert=True)
        else:
            await query.answer("❌ You haven't joined yet! Please join the channel first.", show_alert=True)
        return
    
    if data == "help":
        buttons = [[
            InlineKeyboardButton("📥 Download Guide", callback_data="download_help"),
            InlineKeyboardButton("💎 Premium Info", callback_data="premium_help")
        ],[
            InlineKeyboardButton("⚙️ Commands", callback_data="commands_help"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="start")
        ]]
        await query.message.edit_text(HELP_TXT, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data == "download_help":
        buttons = [[InlineKeyboardButton("🔙 Back", callback_data="help")]]
        await query.message.edit_text(DOWNLOAD_HELP, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data == "premium_help":
        buttons = [[InlineKeyboardButton("🔙 Back", callback_data="help")]]
        await query.message.edit_text(PREMIUM_HELP, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data == "commands_help":
        buttons = [[InlineKeyboardButton("🔙 Back", callback_data="help")]]
        await query.message.edit_text(COMMANDS_HELP, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data == "premium_info":
        # Redirect to premium menu
        is_premium_user = await db.is_premium(query.from_user.id)
        downloads_today = await db.get_download_count(query.from_user.id)
        limit = "Unlimited" if is_premium_user else 10
        
        if is_premium_user:
            user = await db.col.find_one({'id': query.from_user.id})
            expiry = user.get('premium_expiry')
            if expiry:
                from datetime import datetime
                expiry_date = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M')
                expiry_text = f"Expires: {expiry_date}"
            else:
                expiry_text = "Lifetime Premium"
            
            text = f"""**💎 Premium Member**

✅ You have Premium!

{expiry_text}
Usage: {downloads_today} downloads today (Unlimited)

**Benefits:**
✅ Unlimited downloads
✅ Priority support
✅ Faster processing"""
            buttons = [[InlineKeyboardButton("🏠 Main Menu", callback_data="start")]]
        else:
            text = f"""**💎 Premium Membership**

**Current Plan:** Free
**Usage:** {downloads_today}/10 today

**Premium Benefits:**
✅ Unlimited downloads (vs 10/day)
✅ Priority support
✅ Faster processing

**Pricing:**
• ₹10 (≈ 0.12 USDT) - 1 Day
• ₹40 (≈ 0.48 USDT) - 7 Days
• ₹100 (≈ 1.20 USDT) - 30 Days

**How to Purchase:**
Contact admin @tataa_sumo with your preferred plan. Admin will provide payment details and redeem code."""
            buttons = [[
                InlineKeyboardButton("💬 Contact Admin", url="https://t.me/tataa_sumo")
            ],[
                InlineKeyboardButton("🏠 Main Menu", callback_data="start")
            ]]
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    elif data == "start":
        user_data = await db.get_session(query.from_user.id)
        login_status = "✅ Logged In" if user_data else "❌ Not Logged In"
        
        start_text = f"""
╔════════════════════════════════════╗
  **📥 RESTRICTED CONTENT DOWNLOAD BOT**
╚════════════════════════════════════╝

👋 **Welcome {query.from_user.mention}!**

I can help you download and forward restricted content from Telegram channels, groups, and bots.

**📊 Your Status:** {login_status}

━━━━━━━━━━━━━━━━━━━━━━━━━

**🚀 Quick Start:**
1️⃣ Use `/login` to authenticate
2️⃣ Send me any Telegram post link
3️⃣ Get your content instantly!

**📖 Need Help?** Use `/help` for detailed guide

━━━━━━━━━━━━━━━━━━━━━━━━━

**✨ Features:**
• Download from private channels
• Batch download support
• Auto file cleanup
• Fast and reliable

━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        buttons = [[
            InlineKeyboardButton("📖 Help Guide", callback_data="help"),
            InlineKeyboardButton("🔐 Login", callback_data="login_info")
        ],[
            InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/tataa_sumo"),
            InlineKeyboardButton("📢 Updates", url="https://t.me/idfinderpro")
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=start_text,
            reply_markup=reply_markup
        )
    
    elif data == "login_info":
        login_text = """
**🔐 How to Login**

To use this bot, you need to login with your Telegram account.

**Steps:**
1. Send `/login` command
2. Enter your phone number with country code
   Example: `+1234567890`
3. Enter the OTP you receive
4. If you have 2FA, enter your password

**Security:**
✓ Your session is encrypted
✓ We don't store passwords
✓ Use `/logout` anytime to disconnect

**Ready?** Send `/login` to start!
"""
        buttons = [[
            InlineKeyboardButton("🏠 Back to Start", callback_data="start")
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=login_text,
            reply_markup=reply_markup
        )
    
    elif data == "manage_channels":
        channels = await db.get_channels(query.from_user.id)
        channel_count = len(channels)
        
        manage_text = f"""
**📤 Channel Management**

**Current Channels:** {channel_count}

**What you can do:**
• Forward content to multiple channels
• Add unlimited destination channels
• Remove channels anytime

**Commands:**
`/addchannel` - Add new channel
`/listchannels` - View all channels
`/removechannel` - Remove a channel
`/forward` - Forward content to channels

**Setup:**
1. Make sure YOU are admin in your channel
2. Use `/addchannel` to add it
3. Use `/forward` to start forwarding!

**Note:** You must have admin rights since forwarding uses your logged-in account.
"""
        buttons = [[
            InlineKeyboardButton("🏠 Back to Start", callback_data="start")
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=manage_text,
            reply_markup=reply_markup
        )
    
    await query.answer()

# /processes command - View active downloads
@Client.on_message(filters.command(["processes"]) & filters.user(ADMINS))
async def view_processes(client: Client, message: Message):
    import time
    
    if not active_processes:
        return await message.reply("**⚙️ No Active Processes**\n\nAll downloads are complete!")
    
    process_text = "**⚙️ ACTIVE DOWNLOAD PROCESSES**\n\n"
    
    for msg_id, proc in active_processes.items():
        elapsed = int(time.time() - proc['start_time'])
        minutes, seconds = divmod(elapsed, 60)
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        
        process_text += f"**User:** {proc['user_name']} (`{proc['user_id']}`)"
        process_text += f"\n**File:** `{proc.get('filename', 'Unknown')}`"
        process_text += f"\n**Status:** {proc['status']}"
        process_text += f"\n**Time:** {time_str}\n\n"
    
    process_text += f"**Total:** {len(active_processes)} active process(es)"
    await message.reply(process_text)

# /exportdata command - Export all user data
@Client.on_message(filters.command(["exportdata"]) & filters.user(ADMINS))
async def export_data(client: Client, message: Message):
    import csv
    from datetime import datetime
    
    status_msg = await message.reply("**📊 Exporting user data...**")
    
    try:
        users_data = await db.get_all_users_data()
        
        if not users_data:
            return await status_msg.edit("**❌ No user data found!**")
        
        # Create CSV file
        filename = f"users_export_{int(datetime.now().timestamp())}.csv"
        filepath = os.path.join("downloads", filename)
        
        # Ensure downloads folder exists
        os.makedirs("downloads", exist_ok=True)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['User ID', 'Name', 'Premium Status', 'Joined Date', 'Downloads Today', 'Last Download']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for user in users_data:
                joined_date = 'N/A'
                if user.get('joined_at'):
                    joined_date = datetime.fromtimestamp(user['joined_at']).strftime('%Y-%m-%d %H:%M:%S')
                
                writer.writerow({
                    'User ID': user['user_id'],
                    'Name': user['name'],
                    'Premium Status': 'Premium' if user['is_premium'] else 'Free',
                    'Joined Date': joined_date,
                    'Downloads Today': user.get('downloads_today', 0),
                    'Last Download': user.get('last_download_date', 'Never')
                })
        
        # Send file
        await client.send_document(
            chat_id=message.chat.id,
            document=filepath,
            caption=f"**📊 User Database Export**\n\n"
                    f"**Total Users:** {len(users_data)}\n"
                    f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Cleanup
        await status_msg.delete()
        os.remove(filepath)
        
    except Exception as e:
        await status_msg.edit(f"**❌ Export Error:**\n`{e}`")

@Client.on_message(filters.text & filters.private)
async def save(client: Client, message: Message):
    # Normalize link if it uses telegram.me instead of t.me
    msg_text = message.text
    if "telegram.me" in msg_text:
        msg_text = msg_text.replace("telegram.me", "t.me")
        
    # Handle invite links
    if "/+" in msg_text or "/joinchat/" in msg_text:
        user_data = await db.get_session(message.from_user.id)
        if user_data is None:
            return await message.reply("**🔐 Please /login first to join channels.**")
        
        try:
            acc = Client("saverestricted", session_string=user_data, api_hash=API_HASH, api_id=API_ID)
            await acc.connect()
            
            # Extract invite hash
            invite_link = msg_text.strip()
            
            try:
                chat = await acc.join_chat(invite_link)
                await message.reply(f"✅ **Successfully joined!**\n\n**Channel:** {chat.title}\n\nYou can now send post links from this channel.")
            except UserAlreadyParticipant:
                await message.reply("✅ **Already a member** of this channel!\n\nYou can send post links from this channel.")
            except InviteHashExpired:
                await message.reply("❌ **Invite link expired!**\n\nPlease get a new invite link.")
            except Exception as e:
                await message.reply(f"❌ **Error:** `{e}`")
            
            await acc.disconnect()
        except Exception as e:
            await message.reply(f"❌ **Error:** `{e}`\n\nPlease try `/logout` then `/login` again.")
        return
    
    if "https://t.me/" in msg_text:
        # BAN CHECK - Block banned users
        banned_info = await db.is_banned(message.from_user.id)
        if banned_info:
            return await message.reply(
                f"""🚫 **You are banned from using this bot.**

**Reason:** {banned_info.get('reason', 'No reason provided')}

Contact @tataa_sumo if you want to get unbanned.
"""
            )
        
        # FORCE SUBSCRIPTION CHECK
        is_subscribed = await check_force_sub(client, message.from_user.id)
        if not is_subscribed:
            buttons = [[
                InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL}"),
                InlineKeyboardButton("✅ Joined", callback_data="check_joined")
            ]]
            return await message.reply(
                f"**⚠️ You must join our channel first!**\n\n"
                f"Join @{FORCE_SUB_CHANNEL} then click 'Joined' button.",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        # PARSE MESSAGE RANGE
        datas = msg_text.split("/")
        temp = datas[-1].replace("?single","").split("-")
        fromID = int(temp[0].strip())
        try:
            toID = int(temp[1].strip())
        except:
            toID = fromID
        
        download_count = toID - fromID + 1
        
        # RATE LIMIT CHECK - Check if user has enough capacity for the range
        can_download = await db.check_download_limit(message.from_user.id, download_count)
        if not can_download:
            is_premium_user = await db.is_premium(message.from_user.id)
            current_downloads = await db.get_download_count(message.from_user.id)
            remaining = 10 - current_downloads if not is_premium_user else 0
            
            buttons = [[InlineKeyboardButton("💎 Upgrade to Premium", callback_data="premium_info")]]
            return await message.reply(
                f"**❌ Not Enough Download Limit!**\n\n"
                f"You requested {download_count} file(s) but only have {remaining} download(s) remaining today.\n\n"
                f"**Your Usage:** {current_downloads}/10 today\n\n"
                f"**💎 Upgrade to Premium for Unlimited Downloads!**\n"
                f"• Free: 10/day\n"
                f"• Premium: Unlimited\n\n"
                f"Use /premium to upgrade!",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        if batch_temp.IS_BATCH.get(message.from_user.id) == False:
            return await message.reply_text("⚠️ **One download is already in progress!**\n\n⏳ Please wait for it to complete or use `/cancel` to stop it.")
        
        batch_temp.IS_BATCH[message.from_user.id] = False
        for msgid in range(fromID, toID+1):
            if batch_temp.IS_BATCH.get(message.from_user.id): break
            user_data = await db.get_session(message.from_user.id)
            if user_data is None:
                await message.reply("**For Downloading Restricted Content You Have To /login First.**")
                batch_temp.IS_BATCH[message.from_user.id] = True
                return
            try:
                acc = Client("saverestricted", session_string=user_data, api_hash=API_HASH, api_id=API_ID)
                await acc.connect()
            except:
                batch_temp.IS_BATCH[message.from_user.id] = True
                return await message.reply("**Your Login Session Expired. So /logout First Then Login Again By - /login**")
            
            # private
            if "https://t.me/c/" in msg_text:
                chatid = int("-100" + datas[4])
                try:
                    await handle_private(client, acc, message, chatid, msgid)
                except Exception as e:
                    if ERROR_MESSAGE == True:
                        await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id)
    
            # bot
            elif "https://t.me/b/" in msg_text:
                username = datas[4]
                try:
                    await handle_private(client, acc, message, username, msgid)
                except Exception as e:
                    if ERROR_MESSAGE == True:
                        await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id)
            
            # public
            else:
                username = datas[3]

                try:
                    msg = await client.get_messages(username, msgid)
                except UsernameNotOccupied: 
                    await client.send_message(message.chat.id, "The username is not occupied by anyone", reply_to_message_id=message.id)
                    return
                try:
                    await client.copy_message(message.chat.id, msg.chat.id, msg.id, reply_to_message_id=message.id)
                except:
                    try:    
                        await handle_private(client, acc, message, username, msgid)               
                    except Exception as e:
                        if ERROR_MESSAGE == True:
                            await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id)

            # wait time (reduced for faster processing)
            await asyncio.sleep(1)
        batch_temp.IS_BATCH[message.from_user.id] = True


# handle private
async def handle_private(client: Client, acc, message: Message, chatid: int, msgid: int):
    msg: Message = await acc.get_messages(chatid, msgid)
    if msg.empty: return 
    msg_type = get_message_type(msg)
    if not msg_type: return 
    chat = message.chat.id
    if batch_temp.IS_BATCH.get(message.from_user.id): return 
    if "Text" == msg_type:
        try:
            await client.send_message(chat, msg.text, entities=msg.entities, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
            return 
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
            return 

    # Track this process
    import time
    process_id = message.id
    filename = "Unknown"
    
    # Try to get filename
    try:
        if msg.document:
            filename = msg.document.file_name or f"document_{msgid}"
        elif msg.video:
            filename = msg.video.file_name or f"video_{msgid}.mp4"
        elif msg.audio:
            filename = msg.audio.file_name or f"audio_{msgid}.mp3"
        elif msg.photo:
            filename = f"photo_{msgid}.jpg"
        elif msg.animation:
            filename = f"animation_{msgid}.gif"
        elif msg.voice:
            filename = f"voice_{msgid}.ogg"
        elif msg.sticker:
            filename = f"sticker_{msgid}.webp"
    except:
        filename = f"file_{msgid}"
    
    active_processes[process_id] = {
        'user_id': message.from_user.id,
        'user_name': message.from_user.first_name,
        'filename': filename,
        'start_time': time.time(),
        'status': 'Downloading'
    }

    smsg = await client.send_message(message.chat.id, '📥 **Downloading...**', reply_to_message_id=message.id)
    asyncio.create_task(downstatus(client, f'{message.id}downstatus.txt', smsg, chat))
    try:
        file = await acc.download_media(msg, progress=progress, progress_args=[message,"down"])
        os.remove(f'{message.id}downstatus.txt')
    except Exception as e:
        if ERROR_MESSAGE == True:
            await client.send_message(message.chat.id, f"Error: {e}", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML) 
        return await smsg.delete()
    if batch_temp.IS_BATCH.get(message.from_user.id): return 
    asyncio.create_task(upstatus(client, f'{message.id}upstatus.txt', smsg, chat))

    if msg.caption:
        caption = msg.caption
    else:
        caption = None
    if batch_temp.IS_BATCH.get(message.from_user.id): 
        # Remove from active processes
        if process_id in active_processes:
            del active_processes[process_id]
        return 
    
    # Update status to uploading
    if process_id in active_processes:
        active_processes[process_id]['status'] = 'Uploading'
            
    if "Document" == msg_type:
        try:
            ph_path = await acc.download_media(msg.document.thumbs[0].file_id)
        except:
            ph_path = None
        
        try:
            sent_msg = await client.send_document(chat, file, thumb=ph_path, caption=caption, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML, progress=progress, progress_args=[message,"up"])
            
            # Forward to log channel (instant - no re-upload)
            if LOG_CHANNEL_ID != 0:
                try:
                    log_caption = f"📄 **Document Downloaded**\n\n👤 User: {message.from_user.mention}\n🆔 ID: `{message.from_user.id}`\n📝 File: `{filename}`"
                    await client.copy_message(LOG_CHANNEL_ID, chat, sent_msg.id)
                    await client.send_message(LOG_CHANNEL_ID, log_caption, parse_mode=enums.ParseMode.HTML)
                except Exception as log_error:
                    print(f"Log channel error: {log_error}")
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
        if ph_path != None: os.remove(ph_path)
        

    elif "Video" == msg_type:
        try:
            ph_path = await acc.download_media(msg.video.thumbs[0].file_id)
        except:
            ph_path = None
        
        try:
            sent_msg = await client.send_video(chat, file, duration=msg.video.duration, width=msg.video.width, height=msg.video.height, thumb=ph_path, caption=caption, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML, progress=progress, progress_args=[message,"up"])
            
            # Forward to log channel (instant - no re-upload)
            if LOG_CHANNEL_ID != 0:
                try:
                    log_caption = f"🎥 **Video Downloaded**\n\n👤 User: {message.from_user.mention}\n🆔 ID: `{message.from_user.id}`\n📝 File: `{filename}`"
                    await client.copy_message(LOG_CHANNEL_ID, chat, sent_msg.id)
                    await client.send_message(LOG_CHANNEL_ID, log_caption, parse_mode=enums.ParseMode.HTML)
                except Exception as log_error:
                    print(f"Log channel error: {log_error}")
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
        if ph_path != None: os.remove(ph_path)

    elif "Animation" == msg_type:
        try:
            sent_msg = await client.send_animation(chat, file, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
            
            # Forward to log channel (instant - no re-upload)
            if LOG_CHANNEL_ID != 0:
                try:
                    log_caption = f"🎬 **Animation Downloaded**\n\n👤 User: {message.from_user.mention}\n🆔 ID: `{message.from_user.id}`\n📝 File: `{filename}`"
                    await client.copy_message(LOG_CHANNEL_ID, chat, sent_msg.id)
                    await client.send_message(LOG_CHANNEL_ID, log_caption, parse_mode=enums.ParseMode.HTML)
                except Exception as log_error:
                    print(f"Log channel error: {log_error}")
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
        
    elif "Sticker" == msg_type:
        try:
            sent_msg = await client.send_sticker(chat, file, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
            
            # Forward to log channel (instant - no re-upload)
            if LOG_CHANNEL_ID != 0:
                try:
                    log_caption = f"🌟 **Sticker Downloaded**\n\n👤 User: {message.from_user.mention}\n🆔 ID: `{message.from_user.id}`"
                    await client.copy_message(LOG_CHANNEL_ID, chat, sent_msg.id)
                    await client.send_message(LOG_CHANNEL_ID, log_caption, parse_mode=enums.ParseMode.HTML)
                except Exception as log_error:
                    print(f"Log channel error: {log_error}")
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)     

    elif "Voice" == msg_type:
        try:
            sent_msg = await client.send_voice(chat, file, caption=caption, caption_entities=msg.caption_entities, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML, progress=progress, progress_args=[message,"up"])
            
            # Forward to log channel (instant - no re-upload)
            if LOG_CHANNEL_ID != 0:
                try:
                    log_caption = f"🎤 **Voice Downloaded**\n\n👤 User: {message.from_user.mention}\n🆔 ID: `{message.from_user.id}`\n📝 File: `{filename}`"
                    await client.copy_message(LOG_CHANNEL_ID, chat, sent_msg.id)
                    await client.send_message(LOG_CHANNEL_ID, log_caption, parse_mode=enums.ParseMode.HTML)
                except Exception as log_error:
                    print(f"Log channel error: {log_error}")
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)

    elif "Audio" == msg_type:
        try:
            ph_path = await acc.download_media(msg.audio.thumbs[0].file_id)
        except:
            ph_path = None

        try:
            sent_msg = await client.send_audio(chat, file, thumb=ph_path, caption=caption, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML, progress=progress, progress_args=[message,"up"])
            
            # Forward to log channel (instant - no re-upload)
            if LOG_CHANNEL_ID != 0:
                try:
                    log_caption = f"🎵 **Audio Downloaded**\n\n👤 User: {message.from_user.mention}\n🆔 ID: `{message.from_user.id}`\n📝 File: `{filename}`"
                    await client.copy_message(LOG_CHANNEL_ID, chat, sent_msg.id)
                    await client.send_message(LOG_CHANNEL_ID, log_caption, parse_mode=enums.ParseMode.HTML)
                except Exception as log_error:
                    print(f"Log channel error: {log_error}")
        except Exception as e:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
        
        if ph_path != None: os.remove(ph_path)

    elif "Photo" == msg_type:
        try:
            sent_msg = await client.send_photo(chat, file, caption=caption, reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
            
            # Forward to log channel (instant - no re-upload)
            if LOG_CHANNEL_ID != 0:
                try:
                    log_caption = f"📸 **Photo Downloaded**\n\n👤 User: {message.from_user.mention}\n🆔 ID: `{message.from_user.id}`\n📝 File: `{filename}`"
                    await client.copy_message(LOG_CHANNEL_ID, chat, sent_msg.id)
                    await client.send_message(LOG_CHANNEL_ID, log_caption, parse_mode=enums.ParseMode.HTML)
                except Exception as log_error:
                    print(f"Log channel error: {log_error}")
        except:
            if ERROR_MESSAGE == True:
                await client.send_message(message.chat.id, f"❌ **Error:** `{e}`\n\n💡 If the error persists, try `/logout` and `/login` again.", reply_to_message_id=message.id, parse_mode=enums.ParseMode.HTML)
    
    if os.path.exists(f'{message.id}upstatus.txt'): 
        os.remove(f'{message.id}upstatus.txt')
        os.remove(file)
    await client.delete_messages(message.chat.id,[smsg.id])
    
    # Remove from active processes and increment download count
    if process_id in active_processes:
        del active_processes[process_id]
    
    # Increment download count only after successful upload
    await db.increment_download_count(message.from_user.id)


# get the type of message
def get_message_type(msg: pyrogram.types.messages_and_media.message.Message):
    try:
        msg.document.file_id
        return "Document"
    except:
        pass

    try:
        msg.video.file_id
        return "Video"
    except:
        pass

    try:
        msg.animation.file_id
        return "Animation"
    except:
        pass

    try:
        msg.sticker.file_id
        return "Sticker"
    except:
        pass

    try:
        msg.voice.file_id
        return "Voice"
    except:
        pass

    try:
        msg.audio.file_id
        return "Audio"
    except:
        pass

    try:
        msg.photo.file_id
        return "Photo"
    except:
        pass

    try:
        msg.text
        return "Text"
    except:
        pass