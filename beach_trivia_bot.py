# beach_trivia_bot.py
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os

# XP roles as given
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

# Sample questions - add or replace with your own
QUESTIONS = [
    {
        "question": "What is the best way to protect your skin from the sun?",
        "choices": ["A) Sunscreen", "B) Tanning bed", "C) No protection", "D) Water"],
        "answer": "A"
    },
    {
        "question": "Which jellyfish sting is the most painful?",
        "choices": ["A) Moon Jellyfish", "B) Box Jellyfish", "C) Bluebottle", "D) Lion's Mane"],
        "answer": "B"
    },
    {
        "question": "What is the common cause of sunburn?",
        "choices": ["A) UV rays", "B) Water", "C) Sand", "D) Salt"],
        "answer": "A"
    },
    # Add more questions here
]

XP_PER_CORRECT = 25
DATA_FILE = "beachtrivia_data.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Load or initialize XP data
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
    # Find highest role threshold the user qualifies for
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

# For tracking ongoing trivia sessions: user_id -> current_question_index
active_sessions = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# /beachtrivia command to start quiz
@bot.tree.command(name="beachtrivia", description="Start a beach trivia quiz")
async def beachtrivia(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    if user_id in active_sessions:
        await interaction.response.send_message("You're already in an active trivia session! Answer the current question first.", ephemeral=True)
        return

    # Start trivia session at question 0
    active_sessions[user_id] = 0

    # Welcome embed message
    embed = discord.Embed(
        title="🏖️ Welcome to BeachTrivia! 🏖️",
        description="Get ready for a fun beach-themed trivia quiz! For every correct answer, you earn 25 XP and climb the ranks.\nLet's start!",
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/685/685686.png")  # Summer/beach emoji image or your custom icon

    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Send first question
    await send_question(interaction.channel, interaction.user)

async def send_question(channel, user):
    user_id = str(user.id)
    idx = active_sessions[user_id]
    question = QUESTIONS[idx]

    # Build question embed
    embed = discord.Embed(
        title=f"Question {idx + 1}",
        description=question["question"],
        color=discord.Color.gold()
    )
    embed.set_footer(text="Reply with A, B, C, or D")

    # Add choices
    choices_text = "\n".join(question["choices"])
    embed.add_field(name="Choices:", value=choices_text, inline=False)

    # Send message and wait for answer
    trivia_msg = await channel.send(f"{user.mention}", embed=embed)

    def check(m: discord.Message):
        return (
            m.author == user and
            m.channel == channel and
            m.content.upper() in ["A", "B", "C", "D"]
        )

    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
    except:
        await channel.send(f"{user.mention} Time's up! The trivia session has ended.")
        active_sessions.pop(user_id, None)
        return

    # Check answer
    if msg.content.upper() == question["answer"]:
        add_xp(user_id, XP_PER_CORRECT)
        new_xp = get_user_xp(user_id)
        role_name = get_role_for_xp(new_xp)
        await channel.send(f"Correct, {user.mention}! You earned 25 XP. Total XP: {new_xp}. Your current rank: {role_name}")
    else:
        await channel.send(f"Oops, wrong answer, {user.mention}. The correct answer was {question['answer']}.")

    # Next question or end
    if idx + 1 < len(QUESTIONS):
        active_sessions[user_id] = idx + 1
        await send_question(channel, user)
    else:
        await channel.send(f"{user.mention} You've completed the Beach Trivia! Thanks for playing.")
        active_sessions.pop(user_id, None)

# /leaderboard command to show XP leaderboard
@bot.tree.command(name="leaderboard", description="Show the Beach Trivia XP leaderboard")
async def leaderboard(interaction: discord.Interaction):
    # Get all members with XP in this guild
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    # Map user IDs to member names
    member_xp = []
    for user_id_str, xp in xp_data.items():
        member = guild.get_member(int(user_id_str))
        if member:
            member_xp.append((member.display_name, xp))

    if not member_xp:
        await interaction.response.send_message("No XP data found yet!", ephemeral=True)
        return

    # Sort by XP descending
    member_xp.sort(key=lambda x: x[1], reverse=True)

    embed = get_rank_embed(member_xp)
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("Please set your bot token in DISCORD_TOKEN environment variable.")
    else:
        bot.run(TOKEN)
