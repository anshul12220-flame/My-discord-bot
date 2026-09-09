import os
import re
import unicodedata
from datetime import timedelta

import discord
from discord.ext import commands
from discord import app_commands


# =========================================================
# CONFIGURATION
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

# Change this to the exact name of your staff/owner role.
OWNER_ROLE_NAME = "Owner"

# Minimum members required for every selected region
MIN_REGION_MEMBERS = 75

# Maximum number of regions an applicant can select
MAX_REGIONS = 3


# =========================================================
# INTENTS
# =========================================================

intents = discord.Intents.default()

intents.message_content = True
intents.members = True


# =========================================================
# BOT
# =========================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# REGISTRATION DATA
# =========================================================

pending_registrations = {}

registration_log_channels = {}

views_registered = False


# =========================================================
# FLEXIBLE REGION ROLE DETECTION
# =========================================================

REGION_KEYWORDS = {

    "Asia": [
        "asia"
    ],

    "North America": [
        "north america",
        "north-america",
        "north_america",
        "na"
    ],

    "South America": [
        "south america",
        "south-america",
        "south_america",
        "sa"
    ],

    "Europe": [
        "europe",
        "eu"
    ],

    "Oceanic": [
        "oceanic",
        "oceania",
        "oc"
    ]
}


def normalize_role_name(name):
    """
    Cleans a Discord role name so emoji,
    symbols and capitalization don't interfere.
    """

    name = unicodedata.normalize(
        "NFKC",
        name
    )

    name = name.lower()

    # Replace underscores and hyphens with spaces
    name = name.replace("_", " ")
    name = name.replace("-", " ")

    # Remove symbols / emoji
    name = re.sub(
        r"[^\w\s]",
        " ",
        name,
        flags=re.UNICODE
    )

    # Remove extra spaces
    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    return name


def find_region_roles(guild, region):
    """
    Finds ALL roles that appear to represent
    the selected region.

    A member will only be counted once per region,
    even if they have multiple matching roles.
    """

    keywords = REGION_KEYWORDS.get(
        region,
        []
    )

    matching_roles = []

    for role in guild.roles:

        if role.is_default():
            continue

        normalized_name = normalize_role_name(
            role.name
        )

        words = set(
            normalized_name.split()
        )

        for keyword in keywords:

            normalized_keyword = normalize_role_name(
                keyword
            )

            keyword_words = normalized_keyword.split()

            # Abbreviations such as NA / SA / EU / OC
            if normalized_keyword in {
                "na",
                "sa",
                "eu",
                "oc"
            }:

                if normalized_keyword in words:
                    matching_roles.append(role)
                    break

            # Multi-word region names
            elif len(keyword_words) > 1:

                if all(
                    word in words
                    for word in keyword_words
                ):
                    matching_roles.append(role)
                    break

            # Normal region names
            else:

                if normalized_keyword in words:
                    matching_roles.append(role)
                    break

    return matching_roles


def count_region_members(guild, region):
    """
    Counts members belonging to a region.

    If a member has multiple roles representing
    the same region, they are still counted only once.
    """

    roles = find_region_roles(
        guild,
        region
    )

    if not roles:
        return 0, []

    role_ids = {
        role.id
        for role in roles
    }

    count = 0

    for member in guild.members:

        # Count the member once if they have
        # ANY matching role.
        if any(
            role.id in role_ids
            for role in member.roles
        ):
            count += 1

    return count, roles


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_registration_log_channel(guild):

    channel_id = registration_log_channels.get(
        guild.id
    )

    if not channel_id:
        return None

    return guild.get_channel(
        channel_id
    )


async def send_registration_log(
    guild,
    embed
):

    channel = get_registration_log_channel(
        guild
    )

    if channel is None:
        return

    try:

        await channel.send(
            embed=embed
        )

    except discord.Forbidden:
        pass


# =========================================================
# CLAN NAME MODAL
# =========================================================

class ClanNameModal(discord.ui.Modal):

    def __init__(self):

        super().__init__(
            title="Register Clan"
        )

        self.clan_name = discord.ui.TextInput(
            label="Clan Name",
            placeholder="Enter your clan name",
            min_length=1,
            max_length=100,
            required=True
        )

        self.add_item(
            self.clan_name
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        pending_registrations[
            interaction.user.id
        ] = {
            "clan_name": self.clan_name.value,
            "regions": []
        }

        await interaction.response.send_message(
            "Select the regions your clan wants to register for.",
            view=RegionSelectView(
                interaction.user.id
            ),
            ephemeral=True
        )


# =========================================================
# REGISTER CLAN BUTTON
# =========================================================

class ClanRegistrationView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Register Clan",
        style=discord.ButtonStyle.primary,
        custom_id="flame_register_clan"
    )
    async def register_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.send_modal(
            ClanNameModal()
        )


# =========================================================
# REGION SELECT
# =========================================================

class RegionSelect(
    discord.ui.Select
):

    def __init__(self, user_id):

        self.user_id = user_id

        options = [

            discord.SelectOption(
                label="Asia",
                value="Asia",
                description="Asia region"
            ),

            discord.SelectOption(
                label="North America",
                value="North America",
                description="North America region"
            ),

            discord.SelectOption(
                label="South America",
                value="South America",
                description="South America region"
            ),

            discord.SelectOption(
                label="Europe",
                value="Europe",
                description="Europe region"
            ),

            discord.SelectOption(
                label="Oceanic",
                value="Oceanic",
                description="Oceanic region"
            )

        ]

        super().__init__(
            placeholder="Select your regions",
            min_values=1,
            max_values=MAX_REGIONS,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "This registration menu belongs to another user.",
                ephemeral=True
            )

            return

        data = pending_registrations.get(
            self.user_id
        )

        if data is None:

            await interaction.response.send_message(
                "Your registration session expired. Please start again.",
                ephemeral=True
            )

            return

        data["regions"] = self.values

        await interaction.response.edit_message(
            content=(
                "**Regions selected:**\n"
                + "\n".join(
                    f"• {region}"
                    for region in self.values
                )
                + "\n\n"
                "**Next step:**\n"
                "Add this bot to your clan's Discord server "
                "and then press **Continue Verification**."
            ),
            view=ServerVerificationView(
                self.user_id
            )
        )


class RegionSelectView(
    discord.ui.View
):

    def __init__(self, user_id):

        super().__init__(
            timeout=300
        )

        self.add_item(
            RegionSelect(user_id)
        )


# =========================================================
# SERVER VERIFICATION
# =========================================================

class ServerVerificationView(
    discord.ui.View
):

    def __init__(self, user_id):

        super().__init__(
            timeout=300
        )

        self.user_id = user_id

    @discord.ui.button(
        label="Continue Verification",
        style=discord.ButtonStyle.success
    )
    async def continue_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "This verification belongs to another user.",
                ephemeral=True
            )

            return

        data = pending_registrations.get(
            self.user_id
        )

        if data is None:

            await interaction.response.send_message(
                "Your registration session expired.",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        # -------------------------------------------------
        # FIND SERVER OWNED BY APPLICANT
        # -------------------------------------------------

        owned_server = None

        for guild in bot.guilds:

            if guild.owner_id == interaction.user.id:

                owned_server = guild
                break

        # -------------------------------------------------
        # NOT SERVER OWNER
        # -------------------------------------------------

        if owned_server is None:

            embed = discord.Embed(
                title="Clan Registration Denied",
                description=(
                    "You must be the **actual owner** of your clan's "
                    "Discord server.\n\n"
                    "Having an Owner/Admin role is not enough."
                ),
                color=discord.Color.red()
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )

            log_embed = discord.Embed(
                title="❌ Clan Registration Denied",
                color=discord.Color.red()
            )

            log_embed.add_field(
                name="Applicant",
                value=(
                    f"{interaction.user.mention}\n"
                    f"`{interaction.user.id}`"
                ),
                inline=False
            )

            log_embed.add_field(
                name="Clan",
                value=data["clan_name"],
                inline=True
            )

            log_embed.add_field(
                name="Reason",
                value="Applicant is not the Discord server owner.",
                inline=False
            )

            await send_registration_log(
                interaction.guild,
                log_embed
            )

            pending_registrations.pop(
                self.user_id,
                None
            )

            return

        # -------------------------------------------------
        # CHUNK SERVER MEMBERS
        # -------------------------------------------------

        try:

            await owned_server.chunk(
                cache=True
            )

        except Exception:
            pass

        # -------------------------------------------------
        # VERIFY REGIONS
        # -------------------------------------------------

        results = []

        failed = False

        for region in data["regions"]:

            count, roles = count_region_members(
                owned_server,
                region
            )

            role_names = ", ".join(
                role.name
                for role in roles
            )

            if not roles:

                failed = True

                results.append(
                    (
                        region,
                        0,
                        "❌ No matching region role found"
                    )
                )

            elif count < MIN_REGION_MEMBERS:

                failed = True

                results.append(
                    (
                        region,
                        count,
                        f"❌ Need {MIN_REGION_MEMBERS}"
                    )
                )

            else:

                results.append(
                    (
                        region,
                        count,
                        "✅ Passed"
                    )
                )

        # -------------------------------------------------
        # FAILED
        # -------------------------------------------------

        if failed:

            description = ""

            for region, count, status in results:

                description += (
                    f"**{region}** — "
                    f"`{count}/{MIN_REGION_MEMBERS}` "
                    f"{status}\n"
                )

            embed = discord.Embed(
                title="Clan Registration Denied",
                description=description,
                color=discord.Color.red()
            )

            embed.add_field(
                name="Clan",
                value=data["clan_name"],
                inline=True
            )

            embed.add_field(
                name="Server",
                value=owned_server.name,
                inline=True
            )

            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )

            # Log
            log_embed = discord.Embed(
                title="❌ Clan Registration Failed",
                color=discord.Color.red()
            )

            log_embed.add_field(
                name="Clan",
                value=data["clan_name"],
                inline=True
            )

            log_embed.add_field(
                name="Applicant",
                value=(
                    f"{interaction.user.mention}\n"
                    f"`{interaction.user.id}`"
                ),
                inline=True
            )

            log_embed.add_field(
                name="Discord Server",
                value=(
                    f"{owned_server.name}\n"
                    f"`{owned_server.id}`"
                ),
                inline=False
            )

            region_text = ""

            for region, count, status in results:

                region_text += (
                    f"**{region}:** "
                    f"{count}/{MIN_REGION_MEMBERS} "
                    f"{status}\n"
                )

            log_embed.add_field(
                name="Region Verification",
                value=region_text,
                inline=False
            )

            await send_registration_log(
                interaction.guild,
                log_embed
            )

            # Leave clan server immediately
            try:

                await owned_server.leave()

            except Exception:
                pass

            pending_registrations.pop(
                self.user_id,
                None
            )

            return

        # -------------------------------------------------
        # PASSED
        # -------------------------------------------------

        result_text = ""

        for region, count, status in results:

            result_text += (
                f"**{region}** — "
                f"`{count}/{MIN_REGION_MEMBERS}` "
                f"✅\n"
            )

        embed = discord.Embed(
            title="Clan Registration Approved",
            description=(
                f"**Clan:** {data['clan_name']}\n\n"
                f"{result_text}\n"
                "Your clan has successfully passed verification."
            ),
            color=discord.Color.green()
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

        # -------------------------------------------------
        # APPROVAL LOG
        # -------------------------------------------------

        log_embed = discord.Embed(
            title="✅ Clan Registration Approved",
            color=discord.Color.green()
        )

        log_embed.add_field(
            name="Clan",
            value=data["clan_name"],
            inline=True
        )

        log_embed.add_field(
            name="Applicant",
            value=(
                f"{interaction.user.mention}\n"
                f"`{interaction.user.id}`"
            ),
            inline=True
        )

        log_embed.add_field(
            name="Discord Server",
            value=(
                f"{owned_server.name}\n"
                f"`{owned_server.id}`"
            ),
            inline=False
        )

        log_embed.add_field(
            name="Server Owner",
            value=(
                f"{interaction.user.mention}\n"
                "👑 Actual Server Owner"
            ),
            inline=False
        )

        region_text = ""

        for region, count, status in results:

            _, roles = count_region_members(
                owned_server,
                region
            )

            role_names = ", ".join(
                f"`{role.name}`"
                for role in roles
            )

            region_text += (
                f"**{region}:** "
                f"`{count}/{MIN_REGION_MEMBERS}` ✅\n"
                f"Roles detected: {role_names}\n\n"
            )

        log_embed.add_field(
            name="Region Verification",
            value=region_text,
            inline=False
        )

        log_embed.set_footer(
            text="FLAME Clan Registration System"
        )

        await send_registration_log(
            interaction.guild,
            log_embed
        )

        # -------------------------------------------------
        # LEAVE SERVER
        # -------------------------------------------------

        try:

            await owned_server.leave()

        except Exception:
            pass

        pending_registrations.pop(
            self.user_id,
            None
        )


# =========================================================
# LOG CHANNEL SELECTOR
# =========================================================

class RegistrationLogChannelSelect(
    discord.ui.ChannelSelect
):

    def __init__(self):

        super().__init__(
            placeholder="Select registration log channel",
            channel_types=[
                discord.ChannelType.text
            ],
            min_values=1,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        channel = self.values[0]

        registration_log_channels[
            interaction.guild.id
        ] = channel.id

        await interaction.response.edit_message(
            content=(
                f"✅ Registration log channel set to "
                f"{channel.mention}\n\n"
                "The clan registration panel will use this "
                "channel for verification logs."
            ),
            view=None
        )


class RegistrationLogView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=300
        )

        self.add_item(
            RegistrationLogChannelSelect()
        )


# =========================================================
# POST GROUP
# =========================================================

post_group = app_commands.Group(
    name="post",
    description="Post FLAME system panels."
)


clan_group = app_commands.Group(
    name="clan",
    description="Clan related systems.",
    parent=post_group
)


# =========================================================
# /post clan registration
# =========================================================

@clan_group.command(
    name="registration",
    description="Post the BLED clan registration panel."
)
@app_commands.describe(
    channel="Channel where the registration panel will be posted."
)
async def clan_registration(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    # -----------------------------------------------------
    # ADMIN CHECK
    # -----------------------------------------------------

    if not interaction.user.guild_permissions.administrator:

        await interaction.response.send_message(
            "❌ You need **Administrator** permission to use this command.",
            ephemeral=True
        )

        return

    # -----------------------------------------------------
    # OWNER ROLE CHECK
    # -----------------------------------------------------

    owner_role = discord.utils.get(
        interaction.guild.roles,
        name=OWNER_ROLE_NAME
    )

    if owner_role is None:

        await interaction.response.send_message(
            (
                f"❌ The configured Owner role "
                f"`{OWNER_ROLE_NAME}` does not exist.\n\n"
                "Change `OWNER_ROLE_NAME` at the top of the code "
                "to your actual Owner role name."
            ),
            ephemeral=True
        )

        return

    if owner_role not in interaction.user.roles:

        await interaction.response.send_message(
            "❌ You need the **Owner** role to use this command.",
            ephemeral=True
        )

        return

    # -----------------------------------------------------
    # REGISTRATION EMBED
    # -----------------------------------------------------

    embed = discord.Embed(
        title="Registery Clan",
        description=(
            "**Requirements for your BLED clan:**\n\n"
            "• The clan must have at least **75 members** "
            "for each selected region.\n"
            "• Available regions: **Asia / NA / SA / EU / OC**.\n"
            "• You must be the **actual owner** of your clan's "
            "Discord server.\n\n"
            "Click the button below to register your clan."
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="BLED Clan Registration"
    )

    # -----------------------------------------------------
    # SEND PANEL
    # -----------------------------------------------------

    try:

        await channel.send(
            embed=embed,
            view=ClanRegistrationView()
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            (
                f"❌ I don't have permission to send messages "
                f"in {channel.mention}."
            ),
            ephemeral=True
        )

        return

    # -----------------------------------------------------
    # ASK FOR LOG CHANNEL
    # -----------------------------------------------------

    await interaction.response.send_message(
        (
            f"✅ Registration panel posted in {channel.mention}.\n\n"
            "Now select the channel where registration logs "
            "should be sent."
        ),
        view=RegistrationLogView(),
        ephemeral=True
    )


# =========================================================
# ADD COMMAND GROUP
# =========================================================

bot.tree.add_command(
    post_group
)


# =========================================================
# !ping
# =========================================================

@bot.command()
async def ping(ctx):

    await ctx.send(
        f"🏓 Pong! `{round(bot.latency * 1000)}ms`"
    )


# =========================================================
# /ping
# =========================================================

@bot.tree.command(
    name="ping",
    description="Check bot latency."
)
async def slash_ping(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        f"🏓 Pong! `{round(bot.latency * 1000)}ms`"
    )


# =========================================================
# /serverinfo
# =========================================================

@bot.tree.command(
    name="serverinfo",
    description="Show server information."
)
async def serverinfo(
    interaction: discord.Interaction
):

    guild = interaction.guild

    if guild is None:

        await interaction.response.send_message(
            "This command can only be used inside a server.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title=guild.name,
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Server ID",
        value=f"`{guild.id}`",
        inline=False
    )

    embed.add_field(
        name="Members",
        value=str(guild.member_count),
        inline=True
    )

    embed.add_field(
        name="Channels",
        value=str(len(guild.channels)),
        inline=True
    )

    embed.add_field(
        name="Roles",
        value=str(len(guild.roles)),
        inline=True
    )

    if guild.owner:

        embed.add_field(
            name="Owner",
            value=guild.owner.mention,
            inline=False
        )

    if guild.icon:

        embed.set_thumbnail(
            url=guild.icon.url
        )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /userinfo
# =========================================================

@bot.tree.command(
    name="userinfo",
    description="Show information about a user."
)
@app_commands.describe(
    user="User to inspect."
)
async def userinfo(
    interaction: discord.Interaction,
    user: discord.Member
):

    embed = discord.Embed(
        title=f"User Info — {user}",
        color=user.color
    )

    embed.add_field(
        name="Username",
        value=user.name,
        inline=True
    )

    embed.add_field(
        name="ID",
        value=f"`{user.id}`",
        inline=True
    )

    embed.add_field(
        name="Joined Server",
        value=(
            discord.utils.format_dt(
                user.joined_at,
                style="F"
            )
            if user.joined_at
            else "Unknown"
        ),
        inline=False
    )

    embed.add_field(
        name="Account Created",
        value=discord.utils.format_dt(
            user.created_at,
            style="F"
        ),
        inline=False
    )

    if user.avatar:

        embed.set_thumbnail(
            url=user.avatar.url
        )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /kick
# =========================================================

@bot.tree.command(
    name="kick",
    description="Kick a member."
)
@app_commands.describe(
    user="Member to kick.",
    reason="Reason for kicking."
)
@app_commands.checks.has_permissions(
    kick_members=True
)
async def kick(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str = "No reason provided"
):

    if user == interaction.user:

        await interaction.response.send_message(
            "❌ You cannot kick yourself.",
            ephemeral=True
        )

        return

    try:

        await user.kick(
            reason=reason
        )

        await interaction.response.send_message(
            f"✅ {user.mention} has been kicked.\nReason: `{reason}`"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot kick that member.",
            ephemeral=True
        )


# =========================================================
# /ban
# =========================================================

@bot.tree.command(
    name="ban",
    description="Ban a member."
)
@app_commands.describe(
    user="Member to ban.",
    reason="Reason for banning."
)
@app_commands.checks.has_permissions(
    ban_members=True
)
async def ban(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str = "No reason provided"
):

    if user == interaction.user:

        await interaction.response.send_message(
            "❌ You cannot ban yourself.",
            ephemeral=True
        )

        return

    try:

        await user.ban(
            reason=reason
        )

        await interaction.response.send_message(
            f"🔨 {user.mention} has been banned.\nReason: `{reason}`"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot ban that member.",
            ephemeral=True
        )


# =========================================================
# /timeout
# =========================================================

@bot.tree.command(
    name="timeout",
    description="Timeout a member."
)
@app_commands.describe(
    user="Member to timeout.",
    minutes="Timeout duration in minutes.",
    reason="Reason for timeout."
)
@app_commands.checks.has_permissions(
    moderate_members=True
)
async def timeout(
    interaction: discord.Interaction,
    user: discord.Member,
    minutes: int,
    reason: str = "No reason provided"
):

    if minutes < 1:

        await interaction.response.send_message(
            "❌ Duration must be at least 1 minute.",
            ephemeral=True
        )

        return

    if minutes > 40320:

        await interaction.response.send_message(
            "❌ Maximum timeout is 28 days.",
            ephemeral=True
        )

        return

    try:

        duration = timedelta(
            minutes=minutes
        )

        await user.timeout(
            duration,
            reason=reason
        )

        await interaction.response.send_message(
            (
                f"⏱️ {user.mention} has been timed out "
                f"for `{minutes}` minutes.\n"
                f"Reason: `{reason}`"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I cannot timeout that member.",
            ephemeral=True
        )


# =========================================================
# /blacklist
# =========================================================

@bot.tree.command(
    name="blacklist",
    description="Blacklist a user."
)
@app_commands.describe(
    user="User to blacklist.",
    reason="Reason for blacklist."
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def blacklist(
    interaction: discord.Interaction,
    user: discord.Member,
    reason: str = "No reason provided"
):

    await interaction.response.send_message(
        (
            f"🚫 {user.mention} has been blacklisted.\n"
            f"Reason: `{reason}`"
        )
    )


# =========================================================
# /unblacklist
# =========================================================

@bot.tree.command(
    name="unblacklist",
    description="Remove a user from blacklist."
)
@app_commands.describe(
    user="User to remove from blacklist."
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def unblacklist(
    interaction: discord.Interaction,
    user: discord.Member
):

    await interaction.response.send_message(
        f"✅ {user.mention} has been removed from the blacklist."
    )


# =========================================================
# COMMAND ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )

        return

    print(
        f"Slash command error: {error}"
    )

    if not interaction.response.is_done():

        await interaction.response.send_message(
            "❌ An unexpected error occurred.",
            ephemeral=True
        )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    global views_registered

    if not views_registered:

        bot.add_view(
            ClanRegistrationView()
        )

        views_registered = True

    print(
        f"Logged in as {bot.user} "
        f"(ID: {bot.user.id})"
    )

    print(
        f"Connected to {len(bot.guilds)} server(s)"
    )

    try:

        synced = await bot.tree.sync()

        print(
            f"Synced {len(synced)} slash command(s)"
        )

    except Exception as e:

        print(
            f"Slash command sync error: {e}"
        )


# =========================================================
# START BOT
# =========================================================

if not TOKEN:

    raise RuntimeError(
        "DISCORD_TOKEN environment variable is missing."
    )

bot.run(TOKEN)
