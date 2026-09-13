import os
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Logged in as {bot.user}")
        print(f"Connected to {len(bot.guilds)} server(s)")
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Sync error: {e}")


@bot.tree.command(name="ping", description="Check if the bot is online")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🏓 Pong! `{round(bot.latency * 1000)}ms`"
    )
@bot.tree.command(name="blacklist", description="Blacklist a member from the server")
async def blacklist(
    interaction: discord.Interaction,
    member: discord.Member,
    channel: discord.TextChannel,
    reason: str = "No reason provided"
):
    staff_role = discord.utils.get(
        interaction.guild.roles,
        name="Staff"
    )

    if staff_role is None:
        await interaction.response.send_message(
            "❌ The **Staff** role doesn't exist.",
            ephemeral=True
        )
        return

    # Staff and higher roles can use this command
    if not any(
        role.position >= staff_role.position
        for role in interaction.user.roles
    ):
        await interaction.response.send_message(
            "❌ You need the **Staff** role or a higher role to use this command.",
            ephemeral=True
        )
        return

    blacklist_role = discord.utils.get(
        interaction.guild.roles,
        name="Blacklist"
    )

    if blacklist_role is None:
        await interaction.response.send_message(
            "❌ The **Blacklist** role doesn't exist.",
            ephemeral=True
        )
        return

    try:
        # Remove all current roles except @everyone
        roles_to_remove = [
            role for role in member.roles
            if role != interaction.guild.default_role
        ]

        if roles_to_remove:
            await member.remove_roles(
                *roles_to_remove,
                reason=reason
            )

        # Give Blacklist role
        await member.add_roles(
            blacklist_role,
            reason=reason
        )

        # Change nickname automatically
        await member.edit(
            nick=f"[blacklisted] {member.display_name}",
            reason=reason
        )

        # Create blacklist embed
        embed = discord.Embed(
            title="Member Blacklist",
            color=discord.Color.red()
        )

        embed.add_field(
            name="Blacklist User",
            value=member.mention,
            inline=False
        )

        embed.add_field(
            name="Blacklist By",
            value=interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )

        # Send embed to the channel selected by moderator
        await channel.send(embed=embed)

        await interaction.response.send_message(
            f"🔨 {member.mention} has been blacklisted.\n"
            f"Log sent to {channel.mention}.",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to manage this member or send the log.",
            ephemeral=True
        )
@bot.tree.command(name="unblacklist", description="Remove the blacklist from a member")
async def unblacklist(
    interaction: discord.Interaction,
    member: discord.Member,
    channel: discord.TextChannel,
    reason: str = "No reason provided"
):
    staff_role = discord.utils.get(
        interaction.guild.roles,
        name="Staff"
    )

    if staff_role is None:
        await interaction.response.send_message(
            "❌ The **Staff** role doesn't exist.",
            ephemeral=True
        )
        return

    # Staff and higher roles can use this command
    if not any(
        role.position >= staff_role.position
        for role in interaction.user.roles
    ):
        await interaction.response.send_message(
            "❌ You need the **Staff** role or a higher role to use this command.",
            ephemeral=True
        )
        return

    blacklist_role = discord.utils.get(
        interaction.guild.roles,
        name="Blacklist"
    )

    if blacklist_role is None:
        await interaction.response.send_message(
            "❌ The **Blacklist** role doesn't exist.",
            ephemeral=True
        )
        return

    try:
        # Remove Blacklist role
        if blacklist_role in member.roles:
            await member.remove_roles(
                blacklist_role,
                reason=reason
            )

        # Remove [blacklisted] from nickname
        if member.display_name.startswith("[blacklisted] "):
            new_nickname = member.display_name[len("[blacklisted] "):]
            await member.edit(
                nick=new_nickname,
                reason=reason
            )

        # Create unblacklist embed
        embed = discord.Embed(
            title="Member Unblacklist",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Unblacklist User",
            value=member.mention,
            inline=False
        )

        embed.add_field(
            name="Unblacklist By",
            value=interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )

        # Send embed to selected channel
        await channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ {member.mention} has been unblacklisted.\n"
            f"Log sent to {channel.mention}.",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to manage this member's role or nickname.",
            ephemeral=True
        )
        
bot.run(TOKEN)
