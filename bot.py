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
    await interaction.response.send_message(embed=embed)
@bot.tree.command(name="kick", description="Kick any member from server!")
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
@bot.tree.command(name="ban", description="Ban any member from server!")
@commands.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member == interaction.user:
        await interaction.response.send_message(
            "❌ You can't ban yourself.", ephemeral=True
        )
        return

    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(
            f"🔨 {member.mention} has been banned.\n**Reason:** {reason}"
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to ban this member.", ephemeral=True
)
@bot.tree.command(name="timeout", description="Timeout a member for a specified duration")
@commands.has_permissions(moderate_members=True)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: int,
    reason: str = "No reason provided"
):
    if minutes <= 0:
        await interaction.response.send_message(
            "❌ Duration must be greater than 0 minutes.",
            ephemeral=True
        )
        return

    if member == interaction.user:
        await interaction.response.send_message(
            "❌ You can't timeout yourself.",
            ephemeral=True
        )
        return

    duration = timedelta(minutes=minutes)

    try:
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(
            f"⏱️ {member.mention} has been timed out for **{minutes} minutes**.\n"
            f"**Reason:** {reason}"
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to timeout this member.",
            ephemeral=True
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

    
import os

bot.run(os.getenv("DISCORD_TOKEN"))
