import os
import re
import unicodedata
import asyncio
from datetime import timedelta

import discord
from discord.ext import commands
from discord import app_commands


# =========================================================
# CONFIGURATION
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

# Your FLAME Bot Application ID / Client ID
# Find it in:
# Discord Developer Portal
# -> Your Application
# -> General Information
# -> Application ID
#
# Example:
# FLAME_APPLICATION_ID = "123456789012345678"

FLAME_APPLICATION_ID = "1546783120676884490"


# Exact name of the Owner role allowed to post registration panel
OWNER_ROLE_NAME = "Owner"

# Minimum members required for EACH selected region
MIN_REGION_MEMBERS = 75

# Maximum number of regions that can be selected
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
# REGION ROLE DETECTION
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

    name = unicodedata.normalize(
        "NFKC",
        name
    )

    name = name.lower()

    name = name.replace("_", " ")
    name = name.replace("-", " ")

    name = re.sub(
        r"[^\w\s]",
        " ",
        name,
        flags=re.UNICODE
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    return name


def find_region_roles(guild, region):

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

            # Short abbreviations
            if normalized_keyword in {
                "na",
                "sa",
                "eu",
                "oc"
            }:

                if normalized_keyword in words:

                    matching_roles.append(role)

                    break

            # Multi-word regions
            elif len(keyword_words) > 1:

                if all(
                    word in words
                    for word in keyword_words
                ):

                    matching_roles.append(role)

                    break

            # Normal region name
            else:

                if normalized_keyword in words:

                    matching_roles.append(role)

                    break

    return matching_roles


def count_region_members(guild, region):

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

        if any(
            role.id in role_ids
            for role in member.roles
        ):

            count += 1

    return count, roles


# =========================================================
# LOG CHANNEL
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

        print(
            "I cannot send messages to the registration log channel."
        )


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

            "regions": [],

            "source_guild_id": interaction.guild.id
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

    def __init__(
        self,
        user_id
    ):

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

                "❌ This registration menu belongs to another user.",

                ephemeral=True
            )

            return

        data = pending_registrations.get(
            self.user_id
        )

        if data is None:

            await interaction.response.send_message(

                "❌ Your registration session expired. Start again.",

                ephemeral=True
            )

            return

        data["regions"] = list(
            self.values
        )

        selected_regions = "\n".join(
            f"• {region}"
            for region in self.values
        )

        await interaction.response.edit_message(

            content=(

                "**Your selected regions:**\n\n"

                f"{selected_regions}\n\n"

                "## Next Step\n"

                "You have to add **FLAME** to your clan "
                "so we can scan your clan!\n\n"

                "Click **Add FLAME to Clan** and add FLAME "
                "to your clan's Discord server.\n\n"

                "After adding FLAME, come back and click "
                "**I've Added FLAME**."
            ),

            view=AddBotView(
                self.user_id
            )
        )


class RegionSelectView(
    discord.ui.View
):

    def __init__(
        self,
        user_id
    ):

        super().__init__(
            timeout=300
        )

        self.add_item(
            RegionSelect(user_id)
        )


class AddBotView(discord.ui.View):

    def __init__(self, user_id):

        super().__init__(
            timeout=600
        )

        self.user_id = user_id

        # =================================================
        # ADD FLAME BUTTON
        # =================================================

        if FLAME_APPLICATION_ID != "PUT_YOUR_APPLICATION_ID_HERE":

            invite_url = (
                "https://discord.com/oauth2/authorize"
                f"?client_id={FLAME_APPLICATION_ID}"
                "&permissions=8"
                "&scope=bot%20applications.commands"
            )

            self.add_item(
                discord.ui.Button(
                    label="Add FLAME to Clan",
                    style=discord.ButtonStyle.link,
                    url=invite_url
                )
            )

        else:

            self.add_item(
                discord.ui.Button(
                    label="Application ID Missing",
                    style=discord.ButtonStyle.link,
                    url="https://discord.com/developers/applications"
                )
            )


    # =====================================================
    # I'VE ADDED FLAME
    # =====================================================

    @discord.ui.button(
        label="I've Added FLAME",
        style=discord.ButtonStyle.success
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # -------------------------------------------------
        # USER CHECK
        # -------------------------------------------------

        if interaction.user.id != self.user_id:

            await interaction.response.send_message(
                "❌ This registration belongs to another user.",
                ephemeral=True
            )

            return


        # -------------------------------------------------
        # GET REGISTRATION
        # -------------------------------------------------

        data = pending_registrations.get(
            self.user_id
        )

        if data is None:

            await interaction.response.send_message(
                "❌ Your registration session expired. Start again.",
                ephemeral=True
            )

            return


        await interaction.response.defer(
            ephemeral=True
        )


        # =================================================
        # FIND USER'S OWNED SERVERS
        # =================================================

        owned_servers = []

        for guild in bot.guilds:

            if guild.owner_id == interaction.user.id:

                owned_servers.append(
                    guild
                )


        # =================================================
        # NO OWNED SERVER
        # =================================================

        if not owned_servers:

            embed = discord.Embed(

                title="Clan Server Not Found",

                description=(

                    "❌ I couldn't find a server where you are "
                    "the **actual Discord server owner**.\n\n"

                    "Please make sure:\n"

                    "• You added **FLAME** to your clan server.\n"

                    "• You have the **👑 yellow owner crown**.\n"

                    "• FLAME is still inside the server."
                ),

                color=discord.Color.red()
            )

            await interaction.followup.send(

                embed=embed,

                ephemeral=True
            )

            return


        # =================================================
        # FIND BEST SERVER
        # =================================================

        if len(owned_servers) == 1:

            clan_server = owned_servers[0]

        else:

            best_server = None
            best_score = -1

            for guild in owned_servers:

                score = 0

                for region in data["regions"]:

                    if find_region_roles(
                        guild,
                        region
                    ):

                        score += 1

                if score > best_score:

                    best_score = score

                    best_server = guild

            clan_server = best_server

    # =================================================
    # MEMBER LOADING
    # =================================================
    
    await interaction.followup.send(
        "🔎 **FLAME is scanning your clan server...**\n\n"
        "Please wait up to 12 seconds.",
        ephemeral=True
    )

    try:
        await asyncio.wait_for(
            clan_server.chunk(cache=True),
            timeout=12
        )

    except asyncio.TimeoutError:
        print(
            f"Member scan timed out for {clan_server.id}"
        )

        await interaction.followup.send(
            "❌ **Scan timed out.**\n\n"
            "Discord did not finish loading the clan members "
            "within 12 seconds.\n\n"
            "Please try again.",
            ephemeral=True
        )
        return

    except Exception as e:
        print(
            f"Member chunk error for {clan_server.id}: {e}"
        )

        await interaction.followup.send(
            "❌ **Scan failed.**\n\n"
            "FLAME couldn't load the clan members.",
            ephemeral=True
        )
        return

    # =================================================
    # VERIFY MEMBER CACHE
    # =================================================

    if clan_server.member_count is None:
        await interaction.followup.send(
            "❌ **Member count unavailable.**\n\n"
            "Discord did not provide the server member count. "
            "Please try again.",
            ephemeral=True
        )
        return

    cached_members = len(clan_server.members)
    expected_members = clan_server.member_count

    if cached_members < expected_members:
        await interaction.followup.send(
            "❌ **Member scan incomplete.**\n\n"
            f"FLAME loaded **{cached_members:,}** members, "
            f"but Discord reports **{expected_members:,}**.\n\n"
            "Please try again.",
            ephemeral=True
        )
        return


        # -------------------------------------------------
        # DO NOT SCAN INCOMPLETE DATA
        # -------------------------------------------------

        if cached_members < expected_members:

            error_embed = discord.Embed(

                title="Verification Incomplete",

                description=(

                    "❌ I couldn't load all members of your "
                    "clan server.\n\n"

                    f"Discord reports **{expected_members}** "
                    "members, but FLAME only loaded "
                    f"**{cached_members}**.\n\n"

                    "Because the member list is incomplete, "
                    "I will **not approve or deny** your clan."
                ),

                color=discord.Color.orange()
            )

            await interaction.followup.send(

                embed=error_embed,

                ephemeral=True
            )

            print(
                "Verification stopped: incomplete member cache."
            )

            return


        # =================================================
        # REGION VERIFICATION
        # =================================================

        results = []

        failed = False


        for region in data["regions"]:

            count, roles = count_region_members(

                clan_server,

                region
            )


            if not roles:

                failed = True

                results.append({

                    "region": region,

                    "count": count,

                    "roles": [],

                    "passed": False,

                    "reason":
                    "No matching region role found."
                })


            elif count < MIN_REGION_MEMBERS:

                failed = True

                results.append({

                    "region": region,

                    "count": count,

                    "roles": roles,

                    "passed": False,

                    "reason": (

                        f"Only {count} members. "

                        f"{MIN_REGION_MEMBERS} required."
                    )
                })


            else:

                results.append({

                    "region": region,

                    "count": count,

                    "roles": roles,

                    "passed": True,

                    "reason":
                    "Requirement passed."
                })


        # =================================================
        # RESULT TEXT
        # =================================================

        result_text = ""

        for result in results:

            if result["passed"]:

                result_text += (

                    f"**{result['region']}** — "

                    f"`{result['count']}/{MIN_REGION_MEMBERS}` "
                    "✅\n"
                )

            else:

                result_text += (

                    f"**{result['region']}** — "

                    f"`{result['count']}/{MIN_REGION_MEMBERS}` "
                    "❌\n"

                    f"> {result['reason']}\n"
                )


        # =================================================
        # FAILED
        # =================================================

        if failed:

            embed = discord.Embed(

                title="Clan Registration Denied",

                description=(

                    f"**Clan:** {data['clan_name']}\n\n"

                    f"{result_text}"
                ),

                color=discord.Color.red()
            )

            embed.add_field(

                name="Clan Server",

                value=clan_server.name,

                inline=False
            )

            embed.add_field(

                name="Server Owner",

                value=(

                    f"{interaction.user.mention}\n"

                    "👑 Actual Discord server owner"
                ),

                inline=False
            )


            await interaction.followup.send(

                embed=embed,

                ephemeral=True
            )


            # ------------------------------------------------
            # LOG
            # ------------------------------------------------

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

                name="Clan Server",

                value=(

                    f"{clan_server.name}\n"

                    f"`{clan_server.id}`"
                ),

                inline=False
            )

            log_embed.add_field(

                name="Server Ownership",

                value="👑 Actual Discord Server Owner",

                inline=False
            )

            log_embed.add_field(

                name="Member Scan",

                value=(

                    f"Loaded `{cached_members}` / "
                    f"`{expected_members}` members"
                ),

                inline=False
            )

            log_embed.add_field(

                name="Region Scan",

                value=result_text,

                inline=False
            )

            log_embed.set_footer(

                text="FLAME Clan Registration System"
            )


            await send_registration_log(

                interaction.guild,

                log_embed
            )


            # ------------------------------------------------
            # LEAVE SERVER
            # ------------------------------------------------

            try:

                await clan_server.leave()

            except Exception as e:

                print(
                    f"Failed to leave server: {e}"
                )


            pending_registrations.pop(

                self.user_id,

                None
            )

            return


        # =================================================
        # APPROVED
        # =================================================

        embed = discord.Embed(

            title="Clan Registration Approved",

            description=(

                f"## {data['clan_name']}\n\n"

                f"{result_text}\n"

                "All selected region requirements have been "
                "**successfully verified**.\n\n"

                "✅ Your clan has been registered successfully."
            ),

            color=discord.Color.green()
        )

        embed.add_field(

            name="Clan Server",

            value=clan_server.name,

            inline=True
        )

        embed.add_field(

            name="Server Owner",

            value=(

                f"{interaction.user.mention}\n"

                "👑 Actual Discord Server Owner"
            ),

            inline=True
        )


        await interaction.followup.send(

            embed=embed,

            ephemeral=True
        )


        # =================================================
        # APPROVAL LOG
        # =================================================

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

            name="Clan Server",

            value=(

                f"{clan_server.name}\n"

                f"`{clan_server.id}`"
            ),

            inline=False
        )

        log_embed.add_field(

            name="Server Ownership",

            value=(

                f"👑 {interaction.user.mention}\n"

                "Verified as actual Discord server owner"
            ),

            inline=False
        )

        log_embed.add_field(

            name="Member Scan",

            value=(

                f"Loaded `{cached_members}` / "
                f"`{expected_members}` members"
            ),

            inline=False
        )


        detailed_regions = ""

        for result in results:

            role_names = ", ".join(

                f"`{role.name}`"

                for role in result["roles"]
            )

            detailed_regions += (

                f"**{result['region']}** — "

                f"`{result['count']}/{MIN_REGION_MEMBERS}` "
                "✅\n"

                f"Detected role(s): {role_names}\n\n"
            )


        log_embed.add_field(

            name="Region Verification",

            value=detailed_regions,

            inline=False
        )

        log_embed.set_footer(

            text="FLAME Clan Registration System"
        )


        await send_registration_log(

            interaction.guild,

            log_embed
        )


        # =================================================
        # LEAVE CLAN SERVER
        # =================================================

        try:

            await clan_server.leave()

        except Exception as e:

            print(
                f"Failed to leave server: {e}"
            )


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
                f"{channel.mention}."
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
# /POST GROUP
# =========================================================

post_group = app_commands.Group(

    name="post",

    description="Post FLAME system panels."
)


# =========================================================
# /POST CLAN GROUP
# =========================================================

clan_group = app_commands.Group(

    name="clan",

    description="Clan systems.",

    parent=post_group
)


# =========================================================
# /POST CLAN REGISTRATION
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

    # =====================================================
    # ADMINISTRATOR CHECK
    # =====================================================

    if not interaction.user.guild_permissions.administrator:

        await interaction.response.send_message(

            "❌ You need **Administrator** permission.",

            ephemeral=True
        )

        return


    # =====================================================
    # OWNER ROLE CHECK
    # =====================================================

    owner_role = discord.utils.get(

        interaction.guild.roles,

        name=OWNER_ROLE_NAME
    )

    if owner_role is None:

        await interaction.response.send_message(

            (

                f"❌ The Owner role `{OWNER_ROLE_NAME}` "
                "does not exist.\n\n"

                "Change `OWNER_ROLE_NAME` at the top "
                "of the code to your actual Owner role name."
            ),

            ephemeral=True
        )

        return


    if owner_role not in interaction.user.roles:

        await interaction.response.send_message(

            "❌ You need the configured **Owner** role.",

            ephemeral=True
        )

        return


    # =====================================================
    # REGISTRATION EMBED
    # =====================================================

    embed = discord.Embed(

        title="Registery Clan",

        description=(

            "**Requirements for your BLED clan:**\n\n"

            "• The clan must have **75 members** for "
            "each selected region.\n"

            "• Available regions: **Asia / NA / SA / EU / OC**.\n"

            "• You must be the **actual owner** of your "
            "clan's Discord server.\n\n"

            "Click the button below to register your clan."
        ),

        color=discord.Color.blurple()
    )

    embed.set_footer(

        text="BLED Clan Registration"
    )


    # =====================================================
    # SEND PANEL
    # =====================================================

    try:

        await channel.send(

            embed=embed,

            view=ClanRegistrationView()
        )

    except discord.Forbidden:

        await interaction.response.send_message(

            (

                f"❌ I cannot send messages in "
                f"{channel.mention}."
            ),

            ephemeral=True
        )

        return


    # =====================================================
    # SELECT LOG CHANNEL
    # =====================================================

    await interaction.response.send_message(

        (

            f"✅ Clan registration panel posted in "
            f"{channel.mention}.\n\n"

            "Select the channel where registration logs "
            "should be sent."
        ),

        view=RegistrationLogView(),

        ephemeral=True
    )


# =========================================================
# REGISTER COMMAND GROUP
# =========================================================

bot.tree.add_command(
    post_group
)


# =========================================================
# !PING
# =========================================================

@bot.command()
async def ping(ctx):

    await ctx.send(

        f"🏓 Pong! `{round(bot.latency * 1000)}ms`"
    )


# =========================================================
# /PING
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
# /SERVERINFO
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

            "❌ This command can only be used inside a server.",

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
# /USERINFO
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
# /KICK
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

            (

                f"✅ {user.mention} has been kicked.\n"

                f"Reason: `{reason}`"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I cannot kick that member.",

            ephemeral=True
        )


# =========================================================
# /BAN
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

            (

                f"🔨 {user.mention} has been banned.\n"

                f"Reason: `{reason}`"
            )
        )

    except discord.Forbidden:

        await interaction.response.send_message(

            "❌ I cannot ban that member.",

            ephemeral=True
        )


# =========================================================
# /TIMEOUT
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
# /BLACKLIST
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
# /UNBLACKLIST
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
# SLASH COMMAND ERROR HANDLER
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
