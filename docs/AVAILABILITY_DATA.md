# Availability data strategy

## Decision

The founder beta uses nflverse for independent weekly practice participation and game-status
evidence. It is free, published in common file formats, carries ESPN and GSIS player IDs through the
nflverse players dataset, and is licensed under CC BY 4.0.

- Players: `https://github.com/nflverse/nflverse-data/releases/download/players/players.csv`
- Injuries: `https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv`
- Documentation: `https://nflreadr.nflverse.com/reference/load_injuries.html`
- License: `https://github.com/nflverse/nflverse-data/blob/main/LICENSE.md`

The adapter never exposes raw nflverse rows. It maps `espn_id` to `gsis_id`, selects the requested
season/week, and emits only normalized source, practice status, game status, injury and confidence
fields on `LeagueSnapshot`.

## Honesty boundary

nflverse weekly injury reports are not treated as the official 90-minute inactive list. The
normalized `confirmed_inactive` field remains unknown unless a provider explicitly supplies that
evidence. A weekly `OUT` report can create an alert; DNP/LP practice rows add risk context but do not
receive an invented point multiplier.

## Commercial launch gate

Before charging broadly, implement and contract-test one licensed source behind the same
`AvailabilityGateway` interface:

1. Sportradar NFL Weekly Injuries plus Game Roster for declared game-day status; or
2. SportsDataIO NFL Injuries with its game-day inactive update workflow.

The production provider must document update latency, redistribution rights, rate limits, incident
behavior and stable player-ID mapping. Changing providers must not alter analyzer inputs outside the
normalized availability model.
