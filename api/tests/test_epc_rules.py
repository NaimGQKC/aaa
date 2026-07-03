"""EPC/EPBD rule tables (spec §3.3)."""

from datetime import date

from dd_schemas.epc_rules import assess_epc

TODAY = date(2026, 7, 3)


def test_fr_residential_g_ban_in_force():
    findings = assess_epc(country="FR", epc_class="G", residential=True, today=TODAY)
    assert any(f.category == "epc_ban" and f.severity == "high" for f in findings)


def test_fr_residential_f_ban_trajectory():
    findings = assess_epc(country="FR", epc_class="F", residential=True, today=TODAY)
    traj = [f for f in findings if f.category == "epc_ban_trajectory"]
    assert traj and traj[0].severity == "high"  # 2028 ban is <3 years away


def test_fr_commercial_is_trajectory_not_ban():
    """Commercial FR assets must NOT get a hard letting-ban finding (the ban
    calendar stems from residential decency law — spec risk #3)."""
    findings = assess_epc(country="FR", epc_class="F", residential=False, today=TODAY)
    assert not any(f.category == "epc_ban" for f in findings)
    assert any(f.category == "epc_trajectory" for f in findings)
    assert any(f.category == "epbd_meps" for f in findings)


def test_es_worst_band_gets_meps_flag_not_ban():
    findings = assess_epc(country="ES", epc_class="F", residential=False, today=TODAY)
    assert any(f.category == "epbd_meps" for f in findings)
    assert not any(f.category.startswith("epc_ban") for f in findings)


def test_missing_epc_flagged():
    findings = assess_epc(country="ES", epc_class=None, today=TODAY)
    assert any(f.category == "epc_missing" for f in findings)


def test_es_class_g_short_validity():
    findings = assess_epc(
        country="ES", epc_class="G", residential=False,
        epc_issue_date=date(2020, 1, 1), today=TODAY,  # 6.5y > 5y G-validity
    )
    assert any(f.category == "epc_expired" for f in findings)


def test_good_class_no_findings():
    findings = assess_epc(country="ES", epc_class="B", residential=False, today=TODAY)
    assert findings == []
