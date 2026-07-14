from dataclasses import dataclass


@dataclass
class RecoverStaleResult:
    processed: int      # stale payments this sweep picked up (= settled + unresolved)
    settled: int        # reached terminal (charged/recorded)
    unresolved: int     # still stuck (UNKNOWN or a failed terminal write) — next sweep
