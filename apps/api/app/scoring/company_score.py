from collections import defaultdict
from typing import Any, Dict, List

from supabase import Client

from app.scoring.engine import BreakdownItem, ScoreResult


def compute_company_score(rows: List[Any]) -> ScoreResult:
    """
    Pure computation for company score adhering to docs/scoring.md A17-A18.
    - Start 50; clamp to 0..100.
    - Group by (college_id, cycle_year): sum offers_made across all types (internship + full_time)
      and band once per campus-cycle:
      0 offers -> -1
      1-4 -> 0
      5-9 -> +1
      10-20 -> +2
      >20 -> +3
    """
    breakdown: List[BreakdownItem] = [BreakdownItem(reason="Base score", points=50, source="system")]

    # Group offers by (college_id, cycle_year)
    campus_cycle_offers: Dict[tuple, int] = defaultdict(int)

    for r in rows:
        col_id = r.get("college_id") if isinstance(r, dict) else getattr(r, "college_id", None)
        cy = r.get("cycle_year") if isinstance(r, dict) else getattr(r, "cycle_year", None)
        offers = int(r.get("offers_made", 0) if isinstance(r, dict) else getattr(r, "offers_made", 0) or 0)

        # Fallback to college name or id
        if not col_id:
            col_id = r.get("college") if isinstance(r, dict) else getattr(r, "college", "unknown")

        key = (str(col_id), int(cy) if cy is not None else 0)
        campus_cycle_offers[key] += offers

    # Sort keys for deterministic output
    for col_id, cy in sorted(campus_cycle_offers.keys()):
        total_offers = campus_cycle_offers[(col_id, cy)]
        if total_offers == 0:
            breakdown.append(
                BreakdownItem(
                    reason=f"Campus {col_id} cycle {cy}: 0 offers (-1 pt)",
                    points=-1,
                    source="system",
                )
            )
        elif 1 <= total_offers <= 4:
            # 0 points, no breakdown change
            pass
        elif 5 <= total_offers <= 9:
            breakdown.append(
                BreakdownItem(
                    reason=f"Campus {col_id} cycle {cy}: {total_offers} offers (+1 pt)",
                    points=1,
                    source="system",
                )
            )
        elif 10 <= total_offers <= 20:
            breakdown.append(
                BreakdownItem(
                    reason=f"Campus {col_id} cycle {cy}: {total_offers} offers (+2 pts)",
                    points=2,
                    source="system",
                )
            )
        else:  # > 20
            breakdown.append(
                BreakdownItem(
                    reason=f"Campus {col_id} cycle {cy}: {total_offers} offers (+3 pts)",
                    points=3,
                    source="system",
                )
            )

    total_points = sum(item.points for item in breakdown)
    clamped_score = min(100, max(0, total_points))

    actions: List[str] = []
    if clamped_score < 100:
        actions.append("Target 5+ offers at partner campuses to earn positive score bands")
        actions.append("Increase recruitment volume to 10+ or >20 offers at key campuses")
        actions.append("Avoid zero-offer campus drives to prevent score deductions (-1 pt)")

    return ScoreResult(
        score=clamped_score,
        breakdown=breakdown,
        next_best_actions=actions[:3],
    )


def load_company_data(supabase: Client, company_id: str) -> List[Dict[str, Any]]:
    """
    Loads all campus hiring rows for company_id.
    """
    resp = supabase.table("campus_hiring").select("*").eq("company_id", company_id).execute()
    return resp.data or []


def recompute_company_score(supabase: Client, company_id: str) -> ScoreResult:
    """
    Loads company data and computes the company score.
    """
    rows = load_company_data(supabase, company_id)
    return compute_company_score(rows)
