from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from supabase import Client

from app.scoring.engine import BreakdownItem


def classify_company(category: Optional[str]) -> Tuple[int, bool]:
    """
    Classifies a company into Tier 1, 2, or 3 based on docs/scoring.md A11:
    - Tier 1: investment_bank, institutional_investor, fortune500_global
    - Tier 2: gcc, global (and any other global company category). GCC is excluded from Tier 1 even if Fortune 500.
    - Tier 3: everything else.
    Unknown / null / empty category -> tier 3 and flagged_bool = True.
    """
    if category is None:
        return (3, True)
    cat = str(category).strip().lower()
    if not cat or cat in ("unknown", "null", "none"):
        return (3, True)

    # GCC / offshore centres are strictly Tier 2 (never Tier 1)
    if cat == "gcc" or "gcc" in cat:
        return (2, False)

    if cat in ("investment_bank", "institutional_investor", "fortune500_global"):
        return (1, False)

    if cat == "global" or "global" in cat:
        return (2, False)

    # Recognized Tier 3 categories
    if cat in (
        "enterprise",
        "startup",
        "domestic",
        "sme",
        "services",
        "product",
        "other",
        "tier3",
        "tier_3",
    ):
        return (3, False)

    # Unrecognized / unknown category -> tier 3 + flagged
    return (3, True)


@dataclass
class CampusScoreResult:
    score: int
    breakdown: List[BreakdownItem]
    flagged: List[str]
    next_best_actions: List[str]
    campus_score: Optional[int] = None
    campus_internship_score: Optional[int] = None

    def __post_init__(self):
        if self.campus_score is None:
            self.campus_score = self.score

    def to_dict(self):
        return {
            "score": self.score,
            "campus_score": self.campus_score,
            "campus_internship_score": self.campus_internship_score,
            "breakdown": [b.to_dict() for b in self.breakdown],
            "flagged": self.flagged,
            "next_best_actions": self.next_best_actions,
        }


def _compute_score_for_rows(
    rows: List[Any],
    category_map: Dict[str, Optional[str]],
    variant: str = "full_time",
) -> CampusScoreResult:
    """
    Pure computation for campus score or campus internship score.
    Starts at 50, clamps at 100.
    """
    breakdown: List[BreakdownItem] = [
        BreakdownItem(reason="Base score", points=50, source="system")
    ]
    flagged_ids: Set[str] = set()

    # Group by cycle_year
    year_map: Dict[int, List[Any]] = defaultdict(list)
    for r in rows:
        cy = r.get("cycle_year") if isinstance(r, dict) else getattr(r, "cycle_year", None)
        if cy is not None:
            try:
                year_map[int(cy)].append(r)
            except (ValueError, TypeError):
                continue

    for cy in sorted(year_map.keys()):
        tier_offers = {1: 0, 2: 0, 3: 0}
        for r in year_map[cy]:
            cid = str(r.get("company_id") if isinstance(r, dict) else getattr(r, "company_id", "") or "")
            cat = category_map.get(cid) if cid else None
            if cat is None and isinstance(r, dict) and "category" in r:
                cat = r.get("category")

            tier, is_flagged = classify_company(cat)
            offers = int(r.get("offers_made", 0) if isinstance(r, dict) else getattr(r, "offers_made", 0) or 0)
            if is_flagged and cid:
                flagged_ids.add(cid)
            tier_offers[tier] += offers

        # Per cycle_year: tier 1 total > 5 -> +3; tier 2 total > 5 -> +2; tier 3 total > 5 -> +1
        prefix = "Full-time" if variant == "full_time" else "Internship"
        if tier_offers[1] > 5:
            breakdown.append(
                BreakdownItem(
                    reason=f"{prefix} cycle {cy} Tier 1 recruitment (>5 offers)",
                    points=3,
                    source="system",
                )
            )
        if tier_offers[2] > 5:
            breakdown.append(
                BreakdownItem(
                    reason=f"{prefix} cycle {cy} Tier 2 recruitment (>5 offers)",
                    points=2,
                    source="system",
                )
            )
        if tier_offers[3] > 5:
            breakdown.append(
                BreakdownItem(
                    reason=f"{prefix} cycle {cy} Tier 3 recruitment (>5 offers)",
                    points=1,
                    source="system",
                )
            )

    total_points = sum(item.points for item in breakdown)
    capped_score = min(100, max(0, total_points))

    actions: List[str] = []
    if capped_score < 100:
        actions.append("Host campus drives with Tier 1 investment banks & global firms (>5 offers)")
        actions.append("Target GCCs and global enterprise recruiters for Tier 2 bonus")
        actions.append("Engage more industry partners to reach >5 offers in active cycles")

    return CampusScoreResult(
        score=capped_score,
        breakdown=breakdown,
        flagged=sorted(list(flagged_ids)),
        next_best_actions=actions[:3],
    )


def compute_campus_score(
    full_time_rows: List[Any],
    category_map: Dict[str, Optional[str]],
) -> CampusScoreResult:
    """
    Pure compute function for campus score (full-time recruitment).
    Start 50, max 100.
    """
    res = _compute_score_for_rows(full_time_rows, category_map, variant="full_time")
    res.campus_score = res.score
    return res


def compute_campus_internship_score(
    internship_rows: List[Any],
    category_map: Dict[str, Optional[str]],
) -> CampusScoreResult:
    """
    Pure compute function for campus internship score.
    Start 50, max 100.
    """
    res = _compute_score_for_rows(internship_rows, category_map, variant="internship")
    res.campus_internship_score = res.score
    return res


def load_campus_data(
    supabase: Client,
    college_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Optional[str]]]:
    """
    Loads campus hiring data for college_id and builds category map for all involved companies.
    """
    resp = supabase.table("campus_hiring").select("*").eq("college_id", college_id).execute()
    rows = resp.data or []

    full_time_rows = [r for r in rows if r.get("type") == "full_time"]
    internship_rows = [r for r in rows if r.get("type") == "internship"]

    company_ids = list({r.get("company_id") for r in rows if r.get("company_id")})
    category_map: Dict[str, Optional[str]] = {}

    if company_ids:
        c_resp = supabase.table("companies").select("id, category").in_("id", company_ids).execute()
        for c in c_resp.data or []:
            category_map[str(c["id"])] = c.get("category")

    return full_time_rows, internship_rows, category_map


def recompute_campus_score(
    supabase: Client,
    college_id: str,
) -> Dict[str, Any]:
    """
    Loads campus data and computes both full-time and internship scores.
    Returns combined CampusScoreResponse dictionary.
    """
    ft_rows, intern_rows, cat_map = load_campus_data(supabase, college_id)
    ft_result = compute_campus_score(ft_rows, cat_map)
    intern_result = compute_campus_internship_score(intern_rows, cat_map)

    # Combine breakdown (keep base score once, then FT bonuses and Intern bonuses)
    combined_breakdown = list(ft_result.breakdown)
    for b in intern_result.breakdown:
        if b.reason != "Base score":
            combined_breakdown.append(b)

    all_flagged = sorted(list(set(ft_result.flagged + intern_result.flagged)))
    actions = ft_result.next_best_actions

    return {
        "campus_score": ft_result.score,
        "campus_internship_score": intern_result.score,
        "breakdown": [b.to_dict() for b in combined_breakdown],
        "flagged": all_flagged,
        "next_best_actions": actions,
    }

