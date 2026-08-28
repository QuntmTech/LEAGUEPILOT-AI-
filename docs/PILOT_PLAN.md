# Four-week founder pilot

The next valuable iteration is evidence from real league behavior, not a broader feature list. Run
LEAGUEPILOT AI privately in at least three ESPN football leagues with different scoring and roster
formats before offering a paid plan.

## Weekly operating loop

1. Synchronize each league and record whether projections, injuries, free agents and matchups map
   correctly.
2. Run lineup Thursday and Sunday, waivers Monday, trades Tuesday and a weekly recap after the final
   matchup.
3. Mark every recommendation approved or dismissed; record the actual action separately because
   v0.2.1 never writes to ESPN.
4. Ask managers whether the group-chat recap was useful, entertaining or noisy.
5. Log failures without pasting ESPN cookies, webhook URLs or private league data.

## Pass criteria before charging

| Signal | Four-week target |
|---|---:|
| Successful league synchronizations | at least 98% |
| Recommendations with visible evidence | 100% |
| False or fabricated factual claims | 0 |
| Scheduled runs completed without intervention | at least 95% |
| Managers who want the recap next week | at least 60% |
| Median optional-AI cost per active league | below the intended gross-margin budget |

Any credential leak, cross-workspace exposure or silent roster action is a stop-ship event. A failed
ESPN sync or model call must remain visible and recoverable.

## Product decisions after the pilot

- Charge first for reliable waiver/trade workflow and commissioner recaps, not unsupported claims of
  guaranteed wins.
- Add a second provider only if pilots identify ESPN exclusivity as the leading conversion blocker.
- Add public authentication, PostgreSQL, deletion/export controls and billing only after the core
  weekly loop earns repeated usage.
- Preserve rules-only mode as the free and failure-safe tier; meter optional model narration by
  league and report.
