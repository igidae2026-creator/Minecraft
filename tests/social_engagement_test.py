from helpers import ROOT, load_yaml


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core"
SERVICE = CORE / "RpgNetworkService.java"
PROFILE = CORE / "RpgProfile.java"
GUILD = CORE / "RpgGuild.java"
MAIN = CORE / "Main.java"
GUILD_PLUGIN = ROOT / "plugins" / "guild_system" / "src" / "main" / "java" / "com" / "rpg" / "guild" / "Main.java"
METRICS = ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java"


def test_social_configs_exist_and_define_progression_loops():
    guilds = load_yaml("guilds.yml")
    prestige = load_yaml("prestige.yml")
    streaks = load_yaml("streaks.yml")

    assert guilds["guilds"]["progression"]["level_thresholds"]
    assert guilds["guilds"]["rivalry"]["created_threshold"] >= 2
    assert prestige["prestige"]["sources"]["boss_kill"] > 0
    assert prestige["prestige"]["badges"]
    assert streaks["streaks"]["return_reward"]["inactivity_hours"] >= 24
    assert streaks["streaks"]["daily_play"]["milestone_every"] >= 1


def test_profile_and_guild_schema_persist_social_state():
    profile_source = PROFILE.read_text(encoding="utf-8")
    guild_source = GUILD.read_text(encoding="utf-8")

    for marker in (
        "prestigePoints",
        "prestigeBadge",
        "streakCounts",
        "streakDates",
        'yaml.set("social.prestige_points"',
        'yaml.set("social.streaks.counts"',
    ):
        assert marker in profile_source

    for marker in (
        "memberRanks",
        "guildLevel",
        "guildPoints",
        "rewardClaims",
        'yaml.set("members.ranks"',
        'yaml.set("progression.level"',
    ):
        assert marker in guild_source


def test_social_runtime_is_wired_into_commands_rewards_and_broadcasts():
    source = SERVICE.read_text(encoding="utf-8")
    main_source = MAIN.read_text(encoding="utf-8")
    guild_main = GUILD_PLUGIN.read_text(encoding="utf-8")

    for marker in (
        "createGuild",
        "inviteGuild",
        "joinGuild",
        "sendGuildChat",
        "setGuildRank",
        "prestigeSummary",
        "streakSummary",
        "addPrestige",
        "applyGuildProgression",
        "grantReturnRewardIfEligible",
        "advanceStreak",
        "recordRivalryEncounter",
        "broadcastSocialEvent",
        "pollSocialBroadcasts",
        'yaml.set("guild_created"',
        'yaml.set("prestige_gain"',
        'yaml.set("rivalry_reward"',
    ):
        assert marker in source

    for marker in ('case "prestige"', 'case "streak"', "AsyncPlayerChatEvent", 'message.startsWith("@g ")'):
        assert marker in main_source
    for marker in ('case "chat"', 'case "rank"', "/guild chat <message>", "/guild rank <player> <officer|member>"):
        assert marker in guild_main


def test_social_metrics_are_exported():
    source = METRICS.read_text(encoding="utf-8")

    for marker in (
        "rpg_runtime_guild_created_total",
        "rpg_runtime_guild_joined_total",
        "rpg_runtime_prestige_gain_total",
        "rpg_runtime_return_player_reward_total",
        "rpg_runtime_streak_progress_total",
        "rpg_runtime_rivalry_created_total",
        "rpg_runtime_rivalry_match_total",
        "rpg_runtime_rivalry_reward_total",
        "guild_created ",
        "guild_joined ",
        "prestige_gain ",
        "return_player_reward ",
        "streak_progress ",
    ):
        assert marker in source
