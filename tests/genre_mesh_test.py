from helpers import ROOT, load_yaml


CORE = ROOT / "plugins" / "rpg_core" / "src" / "main" / "java" / "com" / "rpg" / "core"


def _read(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def test_genre_registry_and_mesh_profile_spine_exist():
    genres = load_yaml("genres.yml")
    network = load_yaml("network.yml")
    profile = _read("RpgProfile.java")
    service = _read("RpgNetworkService.java")

    assert network["data_flow"]["genre_registry"] == "configs/genres.yml"
    for key in ("lobby", "rpg", "minigame", "event", "dungeon"):
        assert key in genres["genre_registry"]
    for marker in ("currentGenre", "lastWorldVisited", "shardRoutingHint", "genreCurrencies", "progressionCurrencies", "genreSessionDurations"):
        assert marker in profile
    for marker in ("routeToGenre(", "returnToLobby(", "genreMeshSummary(", "recordGenreEntry(", "recordGenreExit("):
        assert marker in service


def test_party_safe_transfers_and_return_command_are_wired():
    main = _read("Main.java")
    service = _read("RpgNetworkService.java")
    party = _read("PartyService.java")

    for marker in ('case "return"', 'case "genres"', 'case "party"'):
        assert marker in main
    for marker in ("partyInvite(", "partyAccept(", "partyLeave(", "partyWarp(", "routeToGenre(player, genreId, true)"):
        assert marker in service
    for marker in ("invite(", "accept(", "markTransfer()", "partyFor("):
        assert marker in party


def test_genre_transfer_metrics_and_wallet_layers_are_exported():
    metrics = (ROOT / "plugins" / "metrics_monitor" / "src" / "main" / "java" / "com" / "rpg" / "metrics" / "Main.java").read_text(encoding="utf-8")
    service = _read("RpgNetworkService.java")

    for marker in ("rpg_runtime_genre_entered_total", "rpg_runtime_genre_exit_total", "rpg_runtime_genre_transfer_success_total", "rpg_runtime_genre_transfer_failure_total"):
        assert marker in metrics
    for marker in ("genre_entered", "genre_exit", "genre_transfer_success", "genre_transfer_failure", 'yaml.set("genre_registry"', 'yaml.set("party_service"'):
        assert marker in service


def test_profile_persists_across_genres_and_returns_without_currency_loss_markers():
    profile = _read("RpgProfile.java")
    service = _read("RpgNetworkService.java")

    for marker in ('yaml.set("currencies.global"', 'yaml.set("currencies.genre"', 'yaml.set("currencies.progression"', 'yaml.set("genres.last_world_visited"'):
        assert marker in profile
    for marker in ("profile.setShardRoutingHint(definition.targetServer())", "profile.addGenreCurrency(genreId, 0)", "travel(player, definition.targetServer())"):
        assert marker in service
