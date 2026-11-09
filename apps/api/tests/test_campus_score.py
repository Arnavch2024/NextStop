from app.scoring.campus_score import (
    classify_company,
    compute_campus_internship_score,
    compute_campus_score,
)


def test_classify_company_tiers():
    # Tier 1 categories
    assert classify_company("investment_bank") == (1, False)
    assert classify_company("institutional_investor") == (1, False)
    assert classify_company("fortune500_global") == (1, False)

    # GCC is tier 2, even if fortune500 or combined
    assert classify_company("gcc") == (2, False)
    assert classify_company("global") == (2, False)
    assert classify_company("gcc_global") == (2, False)

    # Known Tier 3
    assert classify_company("startup") == (3, False)
    assert classify_company("enterprise") == (3, False)

    # Unknown or null -> tier 3 and flagged
    assert classify_company(None) == (3, True)
    assert classify_company("") == (3, True)
    assert classify_company("unknown") == (3, True)
    assert classify_company("xyz_unrecognized") == (3, True)


def test_campus_score_base():
    # Empty rows -> base score 50
    res = compute_campus_score([], {})
    assert res.score == 50
    assert len(res.breakdown) == 1
    assert res.breakdown[0].reason == "Base score"
    assert res.breakdown[0].points == 50


def test_campus_score_boundary_exactly_5_vs_6():
    cat_map = {"c1": "investment_bank"}

    # Exactly 5 offers in Tier 1 -> 0 bonus (A14: more than 5 means >= 6)
    rows_5 = [{"company_id": "c1", "cycle_year": 2027, "offers_made": 5}]
    res_5 = compute_campus_score(rows_5, cat_map)
    assert res_5.score == 50

    # 6 offers in Tier 1 -> +3 bonus
    rows_6 = [{"company_id": "c1", "cycle_year": 2027, "offers_made": 6}]
    res_6 = compute_campus_score(rows_6, cat_map)
    assert res_6.score == 53
    assert any(b.points == 3 and "Tier 1" in b.reason for b in res_6.breakdown)


def test_campus_score_tiers_stack_within_year():
    # In 2027: >5 in Tier 1 (+3), >5 in Tier 2 (+2), >5 in Tier 3 (+1) -> +6 total
    cat_map = {
        "c_t1": "investment_bank",
        "c_t2": "gcc",
        "c_t3": "startup",
    }
    rows = [
        {"company_id": "c_t1", "cycle_year": 2027, "offers_made": 6},
        {"company_id": "c_t2", "cycle_year": 2027, "offers_made": 7},
        {"company_id": "c_t3", "cycle_year": 2027, "offers_made": 8},
    ]
    res = compute_campus_score(rows, cat_map)
    assert res.score == 56  # 50 + 3 + 2 + 1


def test_campus_score_years_accumulate():
    cat_map = {
        "c1": "investment_bank",
        "c2": "gcc",
    }
    rows = [
        {"company_id": "c1", "cycle_year": 2027, "offers_made": 6},  # +3
        {"company_id": "c2", "cycle_year": 2028, "offers_made": 6},  # +2
    ]
    res = compute_campus_score(rows, cat_map)
    assert res.score == 55  # 50 + 3 + 2


def test_campus_score_clamp_100():
    cat_map = {"c1": "investment_bank"}
    # Create 20 years of tier 1 bonus (20 * 3 = 60; 50 + 60 = 110 -> clamped to 100)
    rows = [{"company_id": "c1", "cycle_year": 2000 + i, "offers_made": 10} for i in range(20)]
    res = compute_campus_score(rows, cat_map)
    assert res.score == 100


def test_campus_score_gcc_never_tier_1():
    # GCC company with 10 offers gets +2 (Tier 2), not +3 (Tier 1)
    cat_map = {"c_gcc": "gcc"}
    rows = [{"company_id": "c_gcc", "cycle_year": 2027, "offers_made": 10}]
    res = compute_campus_score(rows, cat_map)
    assert res.score == 52
    assert not any("Tier 1" in b.reason for b in res.breakdown)
    assert any("Tier 2" in b.reason for b in res.breakdown)


def test_campus_score_unknown_category_tier3_and_flagged():
    cat_map = {"c_unk": None}
    rows = [{"company_id": "c_unk", "cycle_year": 2027, "offers_made": 6}]
    res = compute_campus_score(rows, cat_map)
    # Tier 3 > 5 offers -> +1 bonus
    assert res.score == 51
    assert "c_unk" in res.flagged


def test_campus_internship_score():
    cat_map = {"c1": "investment_bank"}
    rows = [{"company_id": "c1", "cycle_year": 2027, "offers_made": 7}]
    res = compute_campus_internship_score(rows, cat_map)
    assert res.score == 53
    assert res.campus_internship_score == 53
    assert any("Internship" in b.reason for b in res.breakdown)
