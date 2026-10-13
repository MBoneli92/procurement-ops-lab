import argparse
import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from integration import ariba_sim

ITEMS = [("MAT-001", Decimal("10"), Decimal("15.00")), ("MAT-002", Decimal("2"), Decimal("99.90"))]


def _parse(document: str) -> ET.Element:
    # ElementTree ignores the DOCTYPE and never fetches the DTD.
    return ET.fromstring(document.encode())


def test_order_request_has_the_fields_the_iflow_reads():
    root = _parse(ariba_sim.build_order_request("PO-1", "7", ITEMS, "BRL"))
    header = root.find("Request/OrderRequest/OrderRequestHeader")
    assert header.get("orderID") == "PO-1"
    assert header.find("Extrinsic[@name='SupplierID']").text == "7"
    assert header.find("Total/Money").get("currency") == "BRL"
    assert header.find("Total/Money").text == "349.80"
    lines = root.findall("Request/OrderRequest/ItemOut")
    assert [(i.find("ItemID/SupplierPartID").text, i.get("quantity")) for i in lines] == [
        ("MAT-001", "10"),
        ("MAT-002", "2"),
    ]
    assert lines[1].find("ItemDetail/UnitPrice/Money").text == "99.90"


def test_payload_id_is_unique_per_message():
    first = _parse(ariba_sim.build_order_request("PO-1", "1", ITEMS)).get("payloadID")
    second = _parse(ariba_sim.build_order_request("PO-1", "1", ITEMS)).get("payloadID")
    assert first != second


def test_special_characters_are_escaped():
    root = _parse(
        ariba_sim.build_order_request('PO-"1"', "1", [("A&B<C>", Decimal(1), Decimal(1))])
    )
    assert root.find(".//SupplierPartID").text == "A&B<C>"


def test_parse_item():
    assert ariba_sim.parse_item("MAT-001:10:15.00") == ("MAT-001", Decimal("10"), Decimal("15.00"))


@pytest.mark.parametrize("raw", ["MAT-001", "MAT-001:10", "MAT-001:ten:1"])
def test_parse_item_rejects_bad_input(raw):
    with pytest.raises(argparse.ArgumentTypeError):
        ariba_sim.parse_item(raw)


def test_dry_run_prints_without_credentials(monkeypatch, capsys):
    for name in ariba_sim.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    assert ariba_sim.main(["--supplier-id", "1", "--item", "MAT-001:1:1", "--dry-run"]) == 0
    assert "<OrderRequest>" in capsys.readouterr().out


def test_send_without_credentials_fails_fast(monkeypatch):
    for name in ariba_sim.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    assert ariba_sim.main(["--supplier-id", "1", "--item", "MAT-001:1:1"]) == 2


def test_malformed_is_not_valid_xml(capsys):
    ariba_sim.main(["--supplier-id", "1", "--item", "MAT-001:1:1", "--dry-run", "--malformed"])
    with pytest.raises(ET.ParseError):
        _parse(capsys.readouterr().out)
