from app.scoring.company_score import compute_company_score


def test_company_score_base():
    # Empty rows -> base score 50
    res = compute_company_score([])
    assert res.score == 50
    assert len(res.breakdown) == 1
    assert res.breakdown[0].reason == "Base score"
    assert res.breakdown[0].points == 50


def test_company_score_bands():
    # 0 offers -> -1
    res_0 = compute_company_score([{"college_id": "col1", "cycle_year": 2027, "offers_made": 0}])
    assert res_0.score == 49
    assert any(b.points == -1 for b in res_0.breakdown)

    # 1-4 offers -> 0 points (no change from 50)
    for offers in (1, 4):
        res = compute_company_score([{"college_id": "col1", "cycle_year": 2027, "offers_made": offers}])
        assert res.score == 50

    # 5-9 offers -> +1 point
    for offers in (5, 9):
        res = compute_company_score([{"college_id": "col1", "cycle_year": 2027, "offers_made": offers}])
        assert res.score == 51
        assert any(b.points == 1 for b in res.breakdown)

    # 10-20 offers -> +2 points
    for offers in (10, 20):
        res = compute_company_score([{"college_id": "col1", "cycle_year": 2027, "offers_made": offers}])
        assert res.score == 52
        assert any(b.points == 2 for b in res.breakdown)

    # >20 offers (e.g. 21) -> +3 points
    res_21 = compute_company_score([{"college_id": "col1", "cycle_year": 2027, "offers_made": 21}])
    assert res_21.score == 53
    assert any(b.points == 3 for b in res_21.breakdown)


def test_company_score_sums_across_types_for_campus_cycle():
    # Campus col1, cycle 2027 has internship: 3, full_time: 3 -> sum = 6 -> band 5-9 -> +1 once
    rows = [
        {"college_id": "col1", "cycle_year": 2027, "type": "internship", "offers_made": 3},
        {"college_id": "col1", "cycle_year": 2027, "type": "full_time", "offers_made": 3},
    ]
    res = compute_company_score(rows)
    # Banded once on summed offers (6) -> +1
    assert res.score == 51


def test_company_score_clamp_bounds():
    # Upper clamp at 100
    many_rows = [
        {"college_id": f"col_{i}", "cycle_year": 2027, "offers_made": 25}
        for i in range(25)  # 25 * 3 = 75; 50 + 75 = 125 -> clamped to 100
    ]
    res_high = compute_company_score(many_rows)
    assert res_high.score == 100

    # Lower clamp at 0
    zero_rows = [
        {"college_id": f"col_{i}", "cycle_year": 2027, "offers_made": 0}
        for i in range(60)  # 60 * -1 = -60; 50 - 60 = -10 -> clamped to 0
    ]
    res_low = compute_company_score(zero_rows)
    assert res_low.score == 0

