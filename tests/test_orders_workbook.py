"""The manual order sheet must never ship with an account value in it."""
from openpyxl import load_workbook

from src.portfolio.orders_workbook import build


def test_workbook_carries_no_account_value(tmp_path):
    out = build(out_path=tmp_path / "orders.xlsx", default_tier="AGG", include_mtm=False)
    ws = load_workbook(out)["Orders"]
    assert ws["C6"].value is None                      # the user types it in
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                assert c.value == 0, f"{c.coordinate} holds a number: {c.value}"   # only the example-holdings zeros


def test_dollar_formulas_stay_blank_until_a_value_is_entered(tmp_path):
    out = build(out_path=tmp_path / "orders.xlsx", default_tier="AGG", include_mtm=False)
    ws = load_workbook(out)["Orders"]
    for col in ("F", "H", "I"):
        assert '$C$6=""' in ws[f"{col}12"].value       # guarded: no #DIV/0! on an empty cell
    assert ws["E12"].value.startswith("=IF($D12")       # weights do not depend on the account value
    assert '$C$6=""' in ws["C24"].value
