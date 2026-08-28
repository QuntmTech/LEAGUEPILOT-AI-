from __future__ import annotations

from datetime import UTC, datetime

from app.schemas import LeagueSnapshot, Matchup, Player, Team


def demo_snapshot(season: int) -> LeagueSnapshot:
    """Return a clearly fictional snapshot for product tours and local evaluation."""

    def player(
        player_id: str,
        name: str,
        position: str,
        projection: float,
        *,
        slot: str,
        injury: str = "ACTIVE",
        average: float | None = None,
    ) -> Player:
        eligible = [position]
        if position in {"RB", "WR", "TE"}:
            eligible.append("FLEX")
        return Player(
            id=player_id,
            name=name,
            position=position,
            pro_team="DME",
            projected_points=projection,
            season_points=round((average or projection) * 5, 1),
            average_points=average or projection,
            injury_status=injury,
            current_slot=slot,
            eligible_slots=eligible,
            opponent="@ SAMPLE",
            percent_owned=75.0,
        )

    founder_roster = [
        player("p01", "Marcus Vale", "QB", 21.8, slot="QB"),
        player("p02", "Devin Rivers", "RB", 16.4, slot="RB"),
        player("p03", "Cal Brooks", "RB", 10.1, slot="RB", injury="QUESTIONABLE"),
        player("p04", "Eli North", "WR", 17.6, slot="WR"),
        player("p05", "Jay Holloway", "WR", 14.3, slot="WR"),
        player("p06", "Theo Banks", "TE", 10.8, slot="TE"),
        player("p07", "Nico Stone", "WR", 8.2, slot="FLEX"),
        player("p08", "Avery King", "RB", 13.7, slot="BE"),
        player("p09", "Port City", "D/ST", 7.1, slot="D/ST"),
        player("p10", "Owen Price", "K", 8.0, slot="K"),
    ]
    north_roster = [
        player("p11", "Sam Mercer", "QB", 20.2, slot="QB"),
        player("p12", "Andre Lake", "RB", 14.9, slot="RB"),
        player("p13", "Malik Snow", "RB", 13.0, slot="RB"),
        player("p14", "Jon Bell", "WR", 16.2, slot="WR"),
        player("p15", "Trey Lane", "WR", 12.6, slot="WR"),
        player("p16", "Cole Hart", "TE", 9.7, slot="TE"),
        player("p17", "Rico West", "WR", 11.4, slot="FLEX"),
    ]
    south_roster = [
        player("p21", "Leo Grant", "QB", 18.9, slot="QB"),
        player("p22", "Drew Moss", "RB", 17.2, slot="RB"),
        player("p23", "Kian Fox", "RB", 11.8, slot="RB"),
        player("p24", "Noah Reed", "WR", 15.4, slot="WR"),
        player("p25", "Miles Dean", "WR", 13.1, slot="WR"),
        player("p26", "Isaac Moon", "TE", 11.2, slot="TE"),
        player("p27", "Jace Young", "WR", 10.6, slot="FLEX"),
    ]
    coast_roster = [
        player("p31", "Ben Locke", "QB", 22.3, slot="QB"),
        player("p32", "Kai Fields", "RB", 15.1, slot="RB"),
        player("p33", "Roman Gray", "RB", 12.4, slot="RB"),
        player("p34", "Cam Woods", "WR", 17.1, slot="WR"),
        player("p35", "Zane Perry", "WR", 14.0, slot="WR"),
        player("p36", "Luke Cross", "TE", 8.9, slot="TE"),
        player("p37", "Max Irving", "RB", 9.8, slot="FLEX"),
    ]
    teams = [
        Team(
            id=1,
            name="Fourth & Founders",
            owner="Demo Owner",
            wins=4,
            losses=1,
            points_for=612.4,
            projected_total=123.1,
            roster=founder_roster,
        ),
        Team(
            id=2,
            name="Northside Noise",
            owner="Demo Rival A",
            wins=3,
            losses=2,
            points_for=588.7,
            projected_total=117.9,
            roster=north_roster,
        ),
        Team(
            id=3,
            name="Sunday Syndicate",
            owner="Demo Rival B",
            wins=2,
            losses=3,
            points_for=560.2,
            projected_total=115.4,
            roster=south_roster,
        ),
        Team(
            id=4,
            name="Coastline Chaos",
            owner="Demo Rival C",
            wins=4,
            losses=1,
            points_for=625.8,
            projected_total=121.6,
            roster=coast_roster,
        ),
    ]
    free_agents = [
        player("fa1", "Darius Prime", "RB", 14.8, slot="FA", average=13.9),
        player("fa2", "Will Sparks", "WR", 12.9, slot="FA", average=11.7),
        player("fa3", "Mason Pike", "TE", 11.6, slot="FA", average=10.8),
        player("fa4", "Chris Arden", "QB", 17.5, slot="FA", average=16.2),
    ]
    return LeagueSnapshot(
        league_id=999_000_001,
        league_name="LeaguePilot Showcase — Fictional Demo",
        season=season,
        week=6,
        scoring_format="Demo PPR",
        my_team_id=1,
        roster_slots=["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "D/ST", "K"],
        teams=teams,
        free_agents=free_agents,
        matchups=[
            Matchup(
                week=6,
                home_team_id=1,
                away_team_id=2,
                home_projected=123.1,
                away_projected=117.9,
            ),
            Matchup(
                week=6,
                home_team_id=3,
                away_team_id=4,
                home_projected=115.4,
                away_projected=121.6,
            ),
        ],
        fetched_at=datetime.now(UTC),
    )
