from __future__ import annotations

import httpx

from app.services.espn import EspnGateway


def test_httpx_espn_adapter_normalizes_league_without_third_party_wrapper() -> None:
    requests: list[httpx.Request] = []

    def raw_player(player_id: int, name: str, position_id: int, projection: float) -> dict:
        return {
            "id": player_id,
            "fullName": name,
            "defaultPositionId": position_id,
            "proTeamId": 12,
            "eligibleSlots": [position_id - 1 if position_id < 5 else 17],
            "injuryStatus": "ACTIVE",
            "ownership": {"percentOwned": 88.5},
            "stats": [
                {
                    "statSourceId": 1,
                    "scoringPeriodId": 6,
                    "appliedTotal": projection,
                },
                {
                    "statSourceId": 0,
                    "statSplitTypeId": 0,
                    "appliedTotal": 70.0,
                },
            ],
        }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "kona_player_info" in request.url.params.get_list("view"):
            return httpx.Response(
                200,
                json={"players": [{"player": raw_player(99, "Waiver Star", 2, 14.2)}]},
            )
        return httpx.Response(
            200,
            json={
                "status": {"currentScoringPeriod": 6, "currentMatchupPeriod": 5},
                "settings": {
                    "name": "Adapter Test League",
                    "rosterSettings": {"lineupSlotCounts": {"0": 1, "2": 1, "20": 4}},
                    "scoringSettings": {"scoringType": "HEAD_TO_HEAD_POINTS"},
                },
                "members": [
                    {"id": "owner-1", "displayName": "Owner One"},
                    {"id": "owner-2", "displayName": "Owner Two"},
                ],
                "teams": [
                    {
                        "id": 1,
                        "location": "Test",
                        "nickname": "Founders",
                        "owners": ["owner-1"],
                        "record": {
                            "overall": {"wins": 4, "losses": 1, "ties": 0, "pointsFor": 600}
                        },
                        "roster": {
                            "entries": [
                                {
                                    "lineupSlotId": 0,
                                    "playerPoolEntry": {
                                        "player": raw_player(1, "Quarterback One", 1, 20.5)
                                    },
                                },
                                {
                                    "lineupSlotId": 2,
                                    "playerPoolEntry": {
                                        "player": raw_player(2, "Running Back One", 2, 15.0)
                                    },
                                },
                            ]
                        },
                    },
                    {
                        "id": 2,
                        "location": "Other",
                        "nickname": "Team",
                        "owners": ["owner-2"],
                        "record": {
                            "overall": {"wins": 3, "losses": 2, "ties": 0, "pointsFor": 550}
                        },
                        "roster": {"entries": []},
                    },
                ],
                "schedule": [
                    {
                        "matchupPeriodId": 6,
                        "home": {
                            "teamId": 1,
                            "totalPoints": 0,
                            "totalProjectedPointsLive": 115.5,
                        },
                        "away": {
                            "teamId": 2,
                            "totalPoints": 0,
                            "totalProjectedPointsLive": 109.2,
                        },
                    }
                ],
            },
        )

    gateway = EspnGateway(transport=httpx.MockTransport(handler))
    snapshot = gateway.fetch_snapshot(
        league_id=123,
        team_id=1,
        season=2026,
        espn_s2="private-cookie",
        swid="{private-swid}",
    )

    assert snapshot.league_name == "Adapter Test League"
    assert snapshot.week == 6
    assert snapshot.my_team.owner == "Owner One"
    assert snapshot.my_team.projected_total == 35.5
    assert snapshot.free_agents[0].name == "Waiver Star"
    assert snapshot.matchups[0].away_projected == 109.2
    assert len(requests) == 2
    assert all("private-cookie" in request.headers.get("cookie", "") for request in requests)
    assert requests[1].headers.get("x-fantasy-filter")
