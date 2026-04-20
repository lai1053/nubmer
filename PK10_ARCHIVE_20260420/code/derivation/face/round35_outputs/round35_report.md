# Round35 Daily Deployment Refinement

- This round starts from the frozen retained components and searches a more robust daily deployment policy.
- Differences vs round33: component-specific gates and optional 1-2 day cooldown after a negative active day.

## Baseline
- round33 best daily path: final `73455.60`, CI low `1.9531`, recent13/26/52 CI low `-2.8381 / -1.5072 / 1.6531`, max DD `-5118.65`.

## Best Refined Policy
- core40_spread_only__exp0_off__oe40_spread_only__cd2 -> final `18050.88`, CI low `0.2043`, recent13/26/52 CI low `0.7094 / 0.1815 / 1.0731`, avg daily bets `29.74`, active share `30.95%`, max DD `-3118.28`.

## Answer
- The refined daily deployment policy improves both short-window stability and drawdown versus round33.
