# Third-party notices

LEAGUEPILOT AI depends on open-source packages installed through `pyproject.toml`. Each
package remains governed by its own license. Important direct dependencies include:

- FastAPI — MIT License.
- SQLAlchemy — MIT License.
- Pydantic and pydantic-settings — MIT License.
- HTTPX — BSD-3-Clause License.
- Cryptography — Apache-2.0 or BSD-3-Clause dual license.
- Uvicorn — BSD-3-Clause License.

The optional founder-beta availability enrichment downloads player ID mappings and weekly injury
reports from [nflverse-data](https://github.com/nflverse/nflverse-data), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). LEAGUEPILOT AI normalizes and combines
selected fields with an ESPN league snapshot and identifies nflverse as the availability source.
The source repository and license link must remain visible anywhere this derived availability data
is redistributed.

No code was copied from the GPL-3.0 `fantasy-football-metrics-weekly-report` project. Similar
league metrics were independently implemented from general statistical concepts so this product
can remain proprietary.

ESPN and ESPN Fantasy are trademarks of their respective owners. This product is not affiliated
with, endorsed by, or sponsored by ESPN or The Walt Disney Company.
