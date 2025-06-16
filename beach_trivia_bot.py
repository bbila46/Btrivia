# beach_trivia_bot.py
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from aiohttp import web

XP_ROLES = [
    (0, "🏖️ Beach First-Aid Trainee"),
    (75, "🩹 Sandy Bandage Applier"),
    (150, "☀️ Sunburn Relief Specialist"),
    (225, "🪼 Jellyfish Sting Soother"),
    (300, "🌊 Tidal Wound Healer"),
    (375, "🐚 Seashell Scrapes Medic"),
    (450, "🚤 Ocean Lifesaver"),
    (525, "🪸 Coral Cut Caretaker"),
    (600, "🏥 Beach ER Doctor"),
    (675, "🩺 Chief of Coastal Medicine"),
    (750, "🌟🏄 Legendary Surf Medic"),
]

CASES = [
    {
        "case_id": 1,
        "description": "🏝️ A child at the beach suddenly begins to scream in pain. His leg shows red tentacle-like marks, and he’s panicking from the sting. What’s your diagnosis?",
        "answer": "jellyfish sting"
    },
    {
        "case_id": 2,
        "description": "☀️ A teenager collapses after playing volleyball. He's dizzy, has dry skin, and feels extremely hot. What’s your diagnosis?",
        "answer": "heat stroke"
    },
    {
        "case_id": 3,
        "description": "🌊 A surfer is pulled underwater and later found coughing, confused, and breathing strangely. What’s the likely diagnosis?",
        "answer": "near drowning"
    }
]

XP_PER_CORRECT = 25
DATA_FILE = "beachtrivia_data.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
active_sessions = {}

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        xp_data = json.load(f)
else:
    xp_data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(xp_data, f, indent=4)

def get_user_xp(user_id: str):
    return xp_data.get(user_id, 0)

def add_xp(user_id: str, amount: int):
    xp_data[user_id] = get_user_xp(user_id) + amount
    save_data()

def get_role_for_xp(xp: int):
    role_name = XP_ROLES[0][1]
    for threshold, role in XP_ROLES:
        if xp >= threshold:
            role_name = role
        else:
            break
    return role_name

def get_rank_embed(member_xp_list):
    embed = discord.Embed(
        title="🏆 Beach Trivia Leaderboard 🏆",
        description="Top Beach Medics by XP",
        color=discord.Color.blue()
    )
    for i, (user, xp) in enumerate(member_xp_list[:10], 1):
        role_name = get_role_for_xp(xp)
        embed.add_field(name=f"{i}. {user}", value=f"XP: {xp} | Role: {role_name}", inline=False)
    return embed

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="beachcase", description="Post a beach emergency case for players to guess!")
async def beachcase(interaction: discord.Interaction):
    # Pick the next unsolved case
    case = next((c for c in CASES if str(c["case_id"]) not in active_cases), None)
    if not case:
        await interaction.response.send_message("All cases have already been solved!", ephemeral=True)
        return

    case_embed = discord.Embed(
        title=f"🔍 CASE {case['case_id']:03d} - ONGOING",
        description=case["description"] + "\n\n💬 **Guess the emergency by replying in chat!**",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    await interaction.response.send_message(embed=case_embed)

    # Listen for guesses
    def check(m):
        return (
            m.channel == interaction.channel
            and m.content.lower().strip() == case["answer"].lower()
            and str(case["case_id"]) not in active_cases
        )

    try:
        msg = await bot.wait_for("message", timeout=600.0, check=check)
        active_cases[str(case["case_id"])] = msg.author.id
        add_xp(str(msg.author.id), XP_PER_CORRECT)

        solved_embed = discord.Embed(
            title=f"✅ CASE {case['case_id']:03d} - SOLVED",
            description=f"Correct Diagnosis: **{case['answer'].title()}**",
            color=discord.Color.green()
        )
        solved_embed.add_field(
            name="🎉 Winner",
            value=f"Congrats {msg.author.mention}! You were the first to solve this case!\n🎁 DM me to claim your **Jellycat** plushie.",
            inline=False
        )
        solved_embed.set_footer(text="CASE closed. Stay tuned for the next one!")
        await interaction.channel.send(embed=solved_embed)

    except asyncio.TimeoutError:
        await interaction.channel.send(f"❌ Time's up! No one solved CASE {case['case_id']:03d}. The answer was `{case['answer']}`.")

@bot.tree.command(name="leaderboard", description="Show the Beach Trivia XP leaderboard")
async def leaderboard(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    member_xp = []
    for user_id_str, xp in xp_data.items():
        member = guild.get_member(int(user_id_str))
        if member:
            member_xp.append((member.display_name, xp))
    if not member_xp:
        await interaction.response.send_message("No XP data found yet!", ephemeral=True)
        return
    member_xp.sort(key=lambda x: x[1], reverse=True)
    embed = get_rank_embed(member_xp)
    await interaction.response.send_message(embed=embed)

# --- Minimal aiohttp web server for Render port ---

async def handle(request):
    return web.Response(text="Beach Trivia Bot is running!")

async def start_webserver():
    app = web.Application()
    app.router.add_get('/', handle)
    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Webserver started on port {port}")

async def main():
    await bot.login(os.getenv("DISCORD_TOKEN"))
    await start_webserver()
    await bot.connect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
