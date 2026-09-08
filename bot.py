import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
print("Slash commands synced!")
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
@bot.tree.command(name="userinfo")
async def userinfo(interaction: discord.Interaction, member: discord.Member):
    roles = [role.mention for role in member.roles if role.name != "@everyone"]

    embed = discord.Embed(
        title=f"User Info — {member}",
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(
        name="Username",
        value=str(member),
        inline=True
    )

    embed.add_field(
        name="User ID",
        value=str(member.id),
        inline=True
    )

    embed.add_field(
        name="Account Created",
        value=f"<t:{int(member.created_at.timestamp())}:F>",
        inline=False
    )

    if member.joined_at:
        embed.add_field(
            name="Joined Server",
            value=f"<t:{int(member.joined_at.timestamp())}:F>",
            inline=False
        )

    embed.add_field(
        name="Roles",
        value=" ".join(roles) if roles else "No roles",
        inline=False
    )
@bot.tree.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member == interaction.user:
        await interaction.response.send_message("You can't kick yourself.", ephemeral=True)
        return

    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(
            f"✅ {member.mention} has been kicked.\n**Reason:** {reason}"
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to kick this member.", ephemeral=True
        )

    await interaction.response.send_message(embed=embed)
import os

bot.run(os.getenv("DISCORD_TOKEN"))
