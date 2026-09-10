import os
import re
import unicodedata
import asyncio
from datetime import timedelta

import discord
from discord.ext import commands
from discord import app_commands


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

FLAME_APPLICATION_ID = "1546783120676884490"

OWNER_ROLE_NAME = "Owner"

MIN_REGION_MEMBERS = 75
MAX_REGIONS = 3


# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ============================================================
# STORAGE
# ============================================================

pending_registrations = {}

registration_log_channels = {}

blacklisted_users = set()


# ============================================================
# REGION KEYWORDS
# ============================================================

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


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def normalize_role_name(name: str):

    name = unicodedata.normalize(
        "NFKC",
        name
    ).lower()

    name = name.replace(
        "_",
        " "
    )

    name = name.replace(
        "-",
        " "
    )

    name = re.sub(
        r"[^\w\s]",
        " ",
        name,
        flags=re.UNICODE
    )

    return re.sub(
        r"\s+",
        " ",
        name
    ).strip()


def find_region_roles(
    guild: discord.Guild,
    region: str
):

    matches = []

    for role in guild.roles:

        if role.is_default():
            continue

        normalized = normalize_role_name(
            role.name
        )

        words = set(
            normalized.split()
        )

        for keyword in REGION_KEYWORDS.get(
            region,
            []
        ):

            key = normalize_role_name(
                keyword
            )

            # Multi-word region
            if " " in key:

                if all(
                    word in words
                    for word in key.split()
                ):

                    matches.append(role)

                    break

            # Single-word region
            else:

                if key in words:

                    matches.append(role)

                    break

    return list(
        dict.fromkeys(matches)
    )


def count_region_members(
    guild: discord.Guild,
    region: str
):

    roles = find_region_roles(
        guild,
        region
    )

    role_ids = {
        role.id
        for role in roles
    }

    if not role_ids:

        return 0, roles

    count = sum(
        1
        for member in guild.members
        if any(
            role.id in role_ids
            for role in member.roles
        )
    )

    return count, roles


def owner_role_and_admin(
    member: discord.Member
):

    return (
        member.guild_permissions.administrator
        and any(
            role.name.lower()
            == OWNER_ROLE_NAME.lower()
            for role in member.roles
        )
    )


def make_embed(
    title,
    description,
    color
):

    return discord.Embed(
        title=title,
        description=description,
        color=color
    )


async def send_registration_log(
    source_guild: discord.Guild,
    embed: discord.Embed
):

    if source_guild is None:
        return

    channel_id = registration_log_channels.get(
        source_guild.id
    )

    if not channel_id:
        return

    channel = source_guild.get_channel(
        channel_id
    )

    if channel is None:
        return

    try:

        await channel.send(
            embed=embed
        )

    except Exception as e:

        print(
            f"Registration log error: {e}"
        )


async def leave_guild(
    guild: discord.Guild
):

    try:

        await guild.leave()

        print(
            f"FLAME left guild "
            f"{guild.id} ({guild.name})"
        )

    except Exception as e:

        print(
            f"Could not leave guild "
            f"{guild.id}: {e}"
        )


# ============================================================
# REGISTRATION SESSION
# ============================================================

class RegistrationSession:

    def __init__(
        self,
        user_id: int,
        source_guild_id: int
    ):

        self.user_id = user_id

        self.source_guild_id = source_guild_id

        self.clan_name = None

        self.regions = []


# ============================================================
# CLAN NAME MODAL
# ============================================================

class ClanNameModal(
    discord.ui.Modal,
    title="Register Clan"
):

    clan_name = discord.ui.TextInput(
        label="Clan Name",
        placeholder="Enter your clan name",
        min_length=1,
        max_length=100,
        required=True
    )

    def __init__(
        self,
        session: RegistrationSession
    ):

        super().__init__()

        self.session = session

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        if (
            interaction.user.id
            != self.session.user_id
        ):

            await interaction.response.send_message(
                "❌ This registration belongs to another user.",
                ephemeral=True
            )

            return

        self.session.clan_name = (
            self.clan_name.value.strip()
        )

        pending_registrations[
            self.session.user_id
        ] = self.session

        await interaction.response.send_message(
            "Select **1–3 regions** for your clan.",
            view=RegionSelectView(
                self.session
            ),
            ephemeral=True
        )


# ============================================================
# MAIN REGISTER BUTTON
# ============================================================

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

        if (
            interaction.user.id
            in blacklisted_users
        ):

            await interaction.response.send_message(
                "❌ You are blacklisted from clan registration.",
                ephemeral=True
            )

            return

        session = RegistrationSession(
            interaction.user.id,
            interaction.guild.id
            if interaction.guild
            else 0
        )

        await interaction.response.send_modal(
            ClanNameModal(
                session
            )
        )


# ============================================================
# REGION SELECT
# ============================================================

class RegionSelect(
    discord.ui.Select
):

    def __init__(
        self,
        session: RegistrationSession
    ):

        self.session = session

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
            placeholder="Select 1–3 regions",
            min_values=1,
            max_values=MAX_REGIONS,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if (
            interaction.user.id
            != self.session.user_id
        ):

            await interaction.response.send_message(
                "❌ This registration belongs to another user.",
                ephemeral=True
            )

            return

        self.session.regions = list(
            self.values
        )

        pending_registrations[
            self.session.user_id
        ] = self.session

        selected = ", ".join(
            self.session.regions
        )

        await interaction.response.edit_message(

            content=(

                f"**Clan:** "
                f"{self.session.clan_name}\n"

                f"**Regions:** "
                f"{selected}\n\n"

                "You have to add **FLAME** "
                "to your clan so we can scan your clan!\n\n"

                "After adding FLAME to your clan server, "
                "click **I've Added FLAME**."
            ),

            view=AddBotView(
                self.session.user_id
            )
        )


class RegionSelectView(
    discord.ui.View
):

    def __init__(
        self,
        session: RegistrationSession
    ):

        super().__init__(
            timeout=600
        )

        self.add_item(
            RegionSelect(
                session
            )
        )


# ============================================================
# ADD FLAME + VERIFY
# ============================================================

class AddBotView(
    discord.ui.View
):

    def __init__(
        self,
        user_id: int
    ):

        super().__init__(
            timeout=600
        )

        self.user_id = user_id

        invite_url = (

            "https://discord.com/oauth2/authorize"

            f"?client_id={FLAME_APPLICATION_ID}"

            "&permissions=0"

            "&scope=bot%20applications.commands"
        )

        self.add_item(

            discord.ui.Button(
                label="Add FLAME to Clan",
                style=discord.ButtonStyle.link,
                url=invite_url
            )
        )


    @discord.ui.button(
        label="I've Added FLAME",
        style=discord.ButtonStyle.success
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if (
            interaction.user.id
            != self.user_id
        ):

            await interaction.response.send_message(
                "❌ This registration belongs to another user.",
                ephemeral=True
            )

            return

        session = pending_registrations.get(
            self.user_id
        )

        if (
            session is None
            or not session.clan_name
            or not session.regions
        ):

            await interaction.response.send_message(
                "❌ Your registration session expired. Start again.",
                ephemeral=True
            )

            return

        if (
            self.user_id
            in blacklisted_users
        ):

            await interaction.response.send_message(
                "❌ You are blacklisted from clan registration.",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        # ====================================================
        # FIND SERVER OWNED BY APPLICANT
        # ====================================================

        owned_servers = [

            guild

            for guild in bot.guilds

            if guild.owner_id
            == interaction.user.id

        ]

        if not owned_servers:

            await interaction.followup.send(

                embed=make_embed(

                    "❌ Clan Server Not Found",

                    (
                        "FLAME could not find a server where "
                        "you are the actual Discord owner.\n\n"

                        "Make sure:\n"
                        "• You are the actual server owner.\n"
                        "• FLAME is inside your clan server.\n"
                        "• You have the **👑 yellow owner crown**.\n"
                        "• You clicked **I've Added FLAME** "
                        "after adding the bot."
                    ),

                    discord.Color.red()
                ),

                ephemeral=True
            )

            pending_registrations.pop(
                self.user_id,
                None
            )

            return


        # ====================================================
        # FIND BEST OWNED SERVER
        # ====================================================

        clan_server = owned_servers[0]

        if len(owned_servers) > 1:

            scored_servers = []

            for guild in owned_servers:

                score = 0

                for region in session.regions:

                    if find_region_roles(
                        guild,
                        region
                    ):

                        score += 1

                scored_servers.append(
                    (
                        score,
                        guild
                    )
                )

            clan_server = max(
                scored_servers,
                key=lambda item: item[0]
            )[1]


        # ====================================================
        # MEMBER LOADING
        # ====================================================

        await interaction.followup.send(

            "🔎 **FLAME is scanning your clan server...**\n\n"
            "Loading clan members. Please wait...\n\n"
            "The scan can take up to **90 seconds**.",

            ephemeral=True
        )


        try:

            # Give Discord more time to send
            # all member chunks.
            await asyncio.wait_for(

                clan_server.chunk(
                    cache=True
                ),

                timeout=90

            )


        except asyncio.TimeoutError:

            print(
                f"Member scan timed out "
                f"for {clan_server.id}"
            )

            await interaction.followup.send(

                "❌ **Scan timed out.**\n\n"

                "Discord did not finish loading "
                "the clan members within **90 seconds**.\n\n"

                "Make sure **Server Members Intent** "
                "is enabled for FLAME and try again.",

                ephemeral=True
            )

            pending_registrations.pop(
                self.user_id,
                None
            )

            return


        except Exception as e:

            print(
                f"Member chunk error "
                f"for {clan_server.id}: {e}"
            )

            await interaction.followup.send(

                "❌ **Scan failed.**\n\n"

                "FLAME couldn't load the clan members.\n\n"

                f"Error: `{type(e).__name__}`",

                ephemeral=True
            )

            pending_registrations.pop(
                self.user_id,
                None
            )

            return


        # ====================================================
        # VERIFY MEMBER CACHE
        # ====================================================

        expected_members = (
            clan_server.member_count
        )

        cached_members = len(
            clan_server.members
        )


        if expected_members is None:

            await interaction.followup.send(

                "❌ Discord did not provide "
                "the server member count.\n\n"

                "Please try again.",

                ephemeral=True
            )

            pending_registrations.pop(
                self.user_id,
                None
            )

            return


        if cached_members < expected_members:

            await interaction.followup.send(

                (
                    "❌ **Member scan incomplete.**\n\n"

                    f"Discord reports "
                    f"**{expected_members:,}** members, "

                    f"but FLAME loaded only "
                    f"**{cached_members:,}**.\n\n"

                    "Make sure **Server Members Intent** "
                    "is enabled in the Discord Developer Portal "
                    "and try again."
                ),

                ephemeral=True
            )

            pending_registrations.pop(
                self.user_id,
                None
            )

            return


        # ====================================================
        # REGION SCAN
        # ====================================================

        region_results = {}

        for region in session.regions:

            count, roles = count_region_members(

                clan_server,

                region

            )

            region_results[region] = {

                "count": count,

                "roles": roles

            }


        failed_regions = {

            region: data["count"]

            for region, data
            in region_results.items()

            if data["count"]
            < MIN_REGION_MEMBERS

        }


        # ====================================================
        # FAILED REGISTRATION
        # ====================================================

        if failed_regions:

            result_lines = []

            for region, data in region_results.items():

                role_names = ", ".join(

                    role.name

                    for role
                    in data["roles"]

                )

                if not role_names:

                    role_names = (
                        "No matching region role found"
                    )


                status = (

                    "❌"

                    if data["count"]
                    < MIN_REGION_MEMBERS

                    else "✅"

                )


                result_lines.append(

                    f"{status} **{region}:** "
                    f"{data['count']}/{MIN_REGION_MEMBERS} members\n"

                    f"   Roles: `{role_names}`"

                )


            result_text = "\n".join(
                result_lines
            )


            denial_embed = make_embed(

                "❌ Clan Registration Denied",

                (
                    f"**Clan:** "
                    f"{session.clan_name}\n\n"

                    f"**Server:** "
                    f"{clan_server.name}\n\n"

                    "**Region Scan:**\n"

                    f"{result_text}\n\n"

                    f"Every selected region must have "
                    f"at least **{MIN_REGION_MEMBERS} members**."
                ),

                discord.Color.red()
            )


            await interaction.followup.send(

                embed=denial_embed,

                ephemeral=True
            )


            log = make_embed(

                "Clan Registration Denied",

                (
                    f"**Applicant:** "
                    f"{interaction.user.mention}\n"

                    f"**Applicant ID:** "
                    f"`{interaction.user.id}`\n"

                    f"**Clan:** "
                    f"{session.clan_name}\n"

                    f"**Clan Server:** "
                    f"{clan_server.name} "
                    f"(`{clan_server.id}`)\n\n"

                    "**Ownership:** "
                    "👑 Actual Discord Server Owner\n"

                    f"**Member Scan:** "
                    f"`{cached_members}/{expected_members}`\n\n"

                    f"**Region Results:**\n"
                    f"{result_text}"
                ),

                discord.Color.red()
            )


            await send_registration_log(

                interaction.guild,

                log

            )


            await leave_guild(
                clan_server
            )


            pending_registrations.pop(
                self.user_id,
                None
            )

            return


        # ====================================================
        # APPROVED REGISTRATION
        # ====================================================

        result_lines = []

        for region, data in region_results.items():

            role_names = ", ".join(

                role.name

                for role
                in data["roles"]

            )

            if not role_names:

                role_names = "No matching role"


            result_lines.append(

                f"✅ **{region}:** "
                f"{data['count']} members\n"

                f"   Roles: `{role_names}`"

            )


        result_text = "\n".join(
            result_lines
        )


        approval_embed = make_embed(

            "✅ Clan Registration Approved",

            (
                f"**Clan:** "
                f"{session.clan_name}\n\n"

                f"**Server:** "
                f"{clan_server.name}\n\n"

                "**Region Scan:**\n"

                f"{result_text}\n\n"

                "Your clan has passed "
                "all registration requirements."
            ),

            discord.Color.green()
        )


        await interaction.followup.send(

            embed=approval_embed,

            ephemeral=True
        )


        log = make_embed(

            "Clan Registration Approved",

            (
                f"**Applicant:** "
                f"{interaction.user.mention}\n"

                f"**Applicant ID:** "
                f"`{interaction.user.id}`\n"

                f"**Clan:** "
                f"{session.clan_name}\n"

                f"**Clan Server:** "
                f"{clan_server.name} "
                f"(`{clan_server.id}`)\n\n"

                "**Ownership:** "
                "👑 Actual Discord Server Owner\n"

                f"**Member Scan:** "
                f"`{cached_members}/{expected_members}`\n\n"

                f"**Region Results:**\n"
                f"{result_text}"
            ),

            discord.Color.green()
        )


        await send_registration_log(

            interaction.guild,

            log

        )


        # Leave the clan server after scan
        await leave_guild(
            clan_server
        )


        pending_registrations.pop(
            self.user_id,
            None
        )


# ============================================================
# /POST CLAN
# ============================================================

post_group = app_commands.Group(
    name="post",
    description="Post FLAME panels"
)


@post_group.command(
    name="clan",
    description="Post the clan registration panel"
)
@app_commands.describe(
    channel="Channel where the registration panel will be posted"
)
async def post_clan(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    if not owner_role_and_admin(
        interaction.user
    ):

        await interaction.response.send_message(

            "❌ You need the **Owner** role "
            "and **Administrator** permission.",

            ephemeral=True
        )

        return


    embed = discord.Embed(

        title="Registery Clan",

        description=(

            "Registery clan\n\n"

            "**Requirements for your clan:**\n"

            "• The clan must have **75 members "
            "for each selected region**.\n"

            "• Supported regions: "
            "**Asia / NA / SA / EU / OC**.\n"

            "• You must be the **actual owner "
            "of your clan's Discord server**.\n\n"

            "Click the button below to register."
        ),

        color=discord.Color.blurple()
    )


    try:

        await channel.send(

            embed=embed,

            view=ClanRegistrationView()

        )


        await interaction.response.send_message(

            f"✅ Registration panel posted "
            f"in {channel.mention}.",

            ephemeral=True
        )


    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I don't have permission to send "
            "messages or embeds in that channel.",

            ephemeral=True
        )


bot.tree.add_command(
    post_group
)


# ============================================================
# PING
# ============================================================

@bot.tree.command(
    name="ping",
    description="Check bot latency"
)
async def slash_ping(
    interaction: discord.Interaction
):

    latency = round(
        bot.latency * 1000
    )

    await interaction.response.send_message(

        f"🏓 Pong! `{latency}ms`"

    )


@bot.command(
    name="ping"
)
async def prefix_ping(
    ctx: commands.Context
):

    latency = round(
        bot.latency * 1000
    )

    await ctx.send(

        f"🏓 Pong! `{latency}ms`"

    )


# ============================================================
# SERVER INFO
# ============================================================

@bot.tree.command(
    name="serverinfo",
    description="Show server information"
)
async def serverinfo(
    interaction: discord.Interaction
):

    guild = interaction.guild


    if guild is None:

        await interaction.response.send_message(

            "❌ Use this command inside a server.",

            ephemeral=True
        )

        return


    embed = discord.Embed(

        title=f"Server Info — {guild.name}",

        color=discord.Color.blurple()
    )


    embed.add_field(

        name="Server ID",

        value=str(guild.id),

        inline=False

    )


    embed.add_field(

        name="Owner",

        value=f"<@{guild.owner_id}>",

        inline=True

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


    if guild.icon:

        embed.set_thumbnail(

            url=guild.icon.url

        )


    await interaction.response.send_message(

        embed=embed

    )


# ============================================================
# USER INFO
# ============================================================

@bot.tree.command(
    name="userinfo",
    description="Show user information"
)
@app_commands.describe(
    user="User to inspect"
)
async def userinfo(
    interaction: discord.Interaction,
    user: discord.Member
):

    embed = discord.Embed(

        title=f"User Info — {user}",

        color=discord.Color.blurple()
    )


    embed.add_field(

        name="User ID",

        value=str(user.id),

        inline=False

    )


    embed.add_field(

        name="Created",

        value=discord.utils.format_dt(

            user.created_at,

            "F"

        ),

        inline=False

    )


    embed.add_field(

        name="Joined",

        value=(

            discord.utils.format_dt(

                user.joined_at,

                "F"

            )

            if user.joined_at

            else "Unknown"

        ),

        inline=False

    )


    embed.add_field(

        name="Roles",

        value=(

            ", ".join(

                role.mention

                for role
                in user.roles[1:]

            )

            or "None"

        ),

        inline=False

    )


    embed.set_thumbnail(

        url=user.display_avatar.url

    )


    await interaction.response.send_message(

        embed=embed

    )


# ============================================================
# MODERATION HELPER
# ============================================================

def can_moderate(
    interaction: discord.Interaction
):

    return (

        isinstance(

            interaction.user,

            discord.Member

        )

        and

        interaction.user.guild_permissions.moderate_members

    )


# ============================================================
# KICK
# ============================================================

@bot.tree.command(
    name="kick",
    description="Kick any member from server!"
)
@app_commands.describe(
    member="Member to kick",
    reason="Reason"
)
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if not can_moderate(
        interaction
    ):

        await interaction.response.send_message(

            "❌ You need Moderate Members permission.",

            ephemeral=True
        )

        return


    try:

        await member.kick(

            reason=reason

        )


        await interaction.response.send_message(

            f"✅ Kicked **{member}**.\n"
            f"Reason: {reason}"

        )


    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I cannot kick that member.",

            ephemeral=True
        )


# ============================================================
# BAN
# ============================================================

@bot.tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.describe(
    member="Member to ban",
    reason="Reason"
)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if not can_moderate(
        interaction
    ):

        await interaction.response.send_message(

            "❌ You need Moderate Members permission.",

            ephemeral=True
        )

        return


    try:

        await member.ban(

            reason=reason

        )


        await interaction.response.send_message(

            f"✅ Banned **{member}**.\n"
            f"Reason: {reason}"

        )


    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I cannot ban that member.",

            ephemeral=True
        )


# ============================================================
# TIMEOUT
# ============================================================

@bot.tree.command(
    name="timeout",
    description="Timeout a member"
)
@app_commands.describe(
    member="Member to timeout",
    minutes="Duration in minutes",
    reason="Reason"
)
async def timeout_member(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: app_commands.Range[
        int,
        1,
        40320
    ],
    reason: str = "No reason provided"
):

    if not can_moderate(
        interaction
    ):

        await interaction.response.send_message(

            "❌ You need Moderate Members permission.",

            ephemeral=True
        )

        return


    try:

        await member.timeout(

            timedelta(
                minutes=minutes
            ),

            reason=reason

        )


        await interaction.response.send_message(

            f"✅ Timed out **{member}** "
            f"for **{minutes} minutes**."

        )


    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I cannot timeout that member.",

            ephemeral=True
        )


# ============================================================
# BLACKLIST
# ============================================================

@bot.tree.command(
    name="blacklist",
    description="Blacklist a member from clan registration"
)
@app_commands.describe(
    user="User to blacklist"
)
async def blacklist(
    interaction: discord.Interaction,
    user: discord.User
):

    if not owner_role_and_admin(
        interaction.user
    ):

        await interaction.response.send_message(

            "❌ You need the **Owner** role "
            "and **Administrator** permission.",

            ephemeral=True
        )

        return


    blacklisted_users.add(
        user.id
    )


    await interaction.response.send_message(

        f"✅ {user.mention} has been "
        "blacklisted from clan registration."

    )


# ============================================================
# UNBLACKLIST
# ============================================================

@bot.tree.command(
    name="unblacklist",
    description="Remove a user from the clan registration blacklist"
)
@app_commands.describe(
    user="User to unblacklist"
)
async def unblacklist(
    interaction: discord.Interaction,
    user: discord.User
):

    if not owner_role_and_admin(
        interaction.user
    ):

        await interaction.response.send_message(

            "❌ You need the **Owner** role "
            "and **Administrator** permission.",

            ephemeral=True
        )

        return


    blacklisted_users.discard(
        user.id
    )


    await interaction.response.send_message(

        f"✅ {user.mention} has been "
        "removed from clan registration blacklist."

    )


# ============================================================
# REGISTRATION LOG CHANNEL
# ============================================================

@bot.tree.command(
    name="set-registration-logs",
    description="Set the channel for clan registration logs"
)
@app_commands.describe(
    channel="Registration log channel"
)
async def set_registration_logs(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):

    if not owner_role_and_admin(
        interaction.user
    ):

        await interaction.response.send_message(

            "❌ You need the **Owner** role "
            "and **Administrator** permission.",

            ephemeral=True
        )

        return


    registration_log_channels[
        interaction.guild.id
    ] = channel.id


    await interaction.response.send_message(

        f"✅ Registration logs will be sent "
        f"to {channel.mention}.",

        ephemeral=True
    )


# ============================================================
# BOT READY
# ============================================================

@bot.event
async def on_ready():

    print(
        f"Logged in as "
        f"{bot.user} ({bot.user.id})"
    )


    print(
        f"Connected to "
        f"{len(bot.guilds)} server(s)."
    )


    if not getattr(

        bot,

        "_registration_view_added",

        False

    ):

        bot.add_view(

            ClanRegistrationView()

        )

        bot._registration_view_added = True


    try:

        synced = await bot.tree.sync()


        print(

            f"Synced "
            f"{len(synced)} slash command(s)."

        )


    except Exception as e:

        print(

            f"Slash command sync failed: {e}"

        )


# ============================================================
# SLASH COMMAND ERROR HANDLER
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    print(
        f"App command error: {repr(error)}"
    )


    message = (
        "❌ An unexpected error occurred."
    )


    if isinstance(

        error,

        app_commands.MissingPermissions

    ):

        message = (

            "❌ You don't have permission "
            "to use this command."

        )


    try:

        if interaction.response.is_done():

            await interaction.followup.send(

                message,

                ephemeral=True

            )

        else:

            await interaction.response.send_message(

                message,

                ephemeral=True

            )


    except Exception as e:

        print(

            f"Could not send error response: {e}"

        )


# ============================================================
# START BOT
# ============================================================

if not TOKEN:

    raise RuntimeError(

        "DISCORD_TOKEN environment variable "
        "is missing. Never put your bot token "
        "directly in this file."

    )


bot.run(TOKEN)
