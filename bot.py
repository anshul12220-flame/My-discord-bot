import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")
@bot.tree.command(name="ping")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")
@bot.tree.command(name="serverinfo")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild

    await interaction.response.send_message(
        f"**Server Info**\n"
        f"Name: {guild.name}\n"
        f"Members: {guild.member_count}\n"
        f"Owner: <@{guild.owner_id}>"
    )
import os

bot.run(os.getenv("DISCORD_TOKEN"))
