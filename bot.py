import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==============================
# CLAN REGISTRATION SYSTEM
# ==============================

OWNER_ROLE_NAME = "Owner"


class ClanNameModal(discord.ui.Modal, title="Register Your Clan"):
    clan_name = discord.ui.TextInput(
        label="Clan Name",
        placeholder="Enter your clan name",
        required=True,
        min_length=2,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        clan_name = self.clan_name.value.strip()

        await interaction.response.send_message(
            f"✅ **Clan Name Received**\n\n"
            f"**Clan:** `{clan_name}`\n\n"
            f"Next step will be the region selection.",
            ephemeral=True
        )


class ClanRegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Register Clan",
        style=discord.ButtonStyle.primary,
        custom_id="clan_register_button"
    )
    async def register_clan(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(ClanNameModal())


@bot.tree.command(
    name="post",
    description="Post a clan registration panel."
)
@app_commands.describe(
    channel="The channel where the clan registration panel will be posted."
)
async def post(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    # Must be used inside a server
    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )
        return

    # Check Administrator permission
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ You need the **Administrator** permission to use this command.",
            ephemeral=True
        )
        return

    # Check Owner role
    owner_role = discord.utils.get(
        interaction.guild.roles,
        name=OWNER_ROLE_NAME
    )

    if owner_role is None:
        await interaction.response.send_message(
            f"❌ The **{OWNER_ROLE_NAME}** role does not exist.",
            ephemeral=True
        )
        return

    if owner_role not in interaction.user.roles:
        await interaction.response.send_message(
            f"❌ You need the **{OWNER_ROLE_NAME}** role to use this command.",
            ephemeral=True
        )
        return

    # Registration embed
    embed = discord.Embed(
        title="Registery Clan",
        description=(
            "**Requirements for your BLED clan:**\n\n"
            "The clan must have **75 members for each region** "
            "(Asia/NA/SA/EU/OC).\n"
            "You must be the **owner of your clan**.\n\n"
            "Click the button below to register."
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="BLED Clan Registration"
    )

    try:
        await channel.send(
            embed=embed,
            view=ClanRegistrationView()
        )

        await interaction.response.send_message(
            f"✅ Clan registration panel posted in {channel.mention}.",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to send messages in that channel.",
            ephemeral=True
        )
@bot.event
async def on_ready():
    bot.add_view(ClanRegistrationView())

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

    
import os

bot.run(os.getenv("DISCORD_TOKEN"))
