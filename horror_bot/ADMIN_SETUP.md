================================================================================
🔐 ADMIN & MODERATOR SYSTEM - SETUP GUIDE
================================================================================

✅ FIXED ISSUES:
================================================================================

1. ✅ Admin Permission Check
   PROBLEM: /setup command had permission issue, preventing server owner from using it
   SOLUTION: Replaced @app_commands.checks.has_permissions(administrator=True) 
            with custom is_admin_or_owner() method that checks:
            • Bot Owner
            • Hardcoded Admin ID (from .env)
            • Server Owner
            • User with Administrator permission

2. ✅ Hardcoded Admin Support
   ADDED: ADMIN_ID variable in .env file
   BENEFIT: Server owner can set their own Discord ID for guaranteed access
   EXAMPLE: ADMIN_ID=123456789012345678

3. ✅ Moderator Management System
   ADDED: Commands to add/remove moderators
   BENEFIT: Delegate bot management to trusted users


📋 NEW ADMIN COMMANDS:
================================================================================

/setup [category]
└─ Setup category for game rooms
└─ Permission: Bot Owner, Hardcoded Admin, Server Owner, Server Administrator
└─ Example: /setup game-rooms

/addmod [@user]
└─ Add user to moderator list
└─ Permission: Same as /setup
└─ Example: /addmod @TrustedFriend

/removemod [@user]
└─ Remove user from moderator list
└─ Permission: Same as /setup
└─ Example: /removemod @NoLongerMod

/modlist
└─ View all current moderators
└─ Permission: Same as /setup

/showdb [table]
└─ View database contents
└─ Tables: active_games, players, game_maps
└─ Permission: Same as /setup

/sync [guild]
└─ Sync slash commands with Discord
└─ Permission: Bot Owner only
└─ Example: /sync (syncs globally)


🔧 SETUP INSTRUCTIONS:
================================================================================

STEP 1: Get Your Discord ID
────────────────────────────
1. Open Discord Settings → Advanced
2. Enable "Developer Mode"
3. Right-click your username
4. Select "Copy User ID"
5. You should have a number like: 123456789012345678

STEP 2: Update .env File
────────────────────────
1. Open horror_bot/.env in your editor
2. Find line: ADMIN_ID=0
3. Replace with: ADMIN_ID=your_discord_id_here
   
   Example:
   ADMIN_ID=987654321098765432

4. Save the file

STEP 3: Restart Bot
───────────────────
1. Stop the bot (Ctrl+C)
2. Run: python main.py
3. Bot should start and print "✅ Admin Commands Cog sẵn sàng."

STEP 4: Test Setup Command
──────────────────────────
1. In Discord, create a Category for game rooms (e.g., "horror-games")
2. Run: /setup [drag category here]
3. You should see: "✅ Setup xong! Bot sẽ tạo game rooms trong category: #category-name"

STEP 5: Add Moderators (Optional)
─────────────────────────────────
1. Run: /addmod @username
2. They can now use admin commands (except /sync which is bot owner only)


👮 PERMISSION HIERARCHY:
================================================================================

Tier 1 (HIGHEST): Bot Owner
└─ Can use: /sync, /setup, /addmod, /removemod, /modlist, /showdb

Tier 2: Hardcoded Admin (ADMIN_ID in .env)
└─ Can use: /setup, /addmod, /removemod, /modlist, /showdb

Tier 3: Server Owner
└─ Can use: /setup, /addmod, /removemod, /modlist, /showdb

Tier 4: Server Administrator (has admin role/permission)
└─ Can use: /setup, /addmod, /removemod, /modlist, /showdb

Tier 5: Moderator (added via /addmod)
└─ Can use: /setup, /addmod, /removemod, /modlist, /showdb
└─ (Subject to future expansion)

Tier 6: Regular Users
└─ Can use: /newgame, /endgame (game commands only)


💡 USAGE EXAMPLES:
================================================================================

# Add someone as moderator
/addmod @trusted_person

# View all moderators
/modlist

# Remove a moderator
/removemod @untrusted_person

# Check database
/showdb players

# Setup game rooms (only need to do once per server)
/setup [drag-category-here]


⚠️ IMPORTANT NOTES:
================================================================================

1. Moderators are stored IN MEMORY during bot runtime
   - They reset when bot restarts
   - TODO: Persist to database for permanent storage

2. ADMIN_ID in .env is permanent unless you change it manually

3. Server Owner always has access regardless of settings

4. Each server with /setup can create game rooms independently

5. If bot owner (in app settings) runs commands, they work everywhere


❓ TROUBLESHOOTING:
================================================================================

Q: I'm server owner but still can't use /setup
A: Check that:
   • Bot has permission to create channels in the category
   • You're using the correct category when running /setup
   • Bot has Message Content intent enabled
   • Try restarting the bot

Q: Commands don't show up after setup
A: Run: /sync (if you're bot owner)
   Or wait 1 hour for Discord to refresh

Q: How do I remove admin access from myself?
A: You can't directly, but:
   • Change ADMIN_ID in .env to someone else
   • Restart bot
   • Now only that person has hardcoded admin access

Q: Can moderators use all commands?
A: Currently yes (same as admins)
   Future: Can add role-based permission tiers

================================================================================
