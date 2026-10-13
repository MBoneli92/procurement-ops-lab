"""Play the role of SAP Ariba Network: build a cXML OrderRequest and send it to the iFlow.

    python -m integration.ariba_sim --supplier-id 1 --item MAT-001:10:15.00 --dry-run
    python -m integration.ariba_sim --supplier-id 1 --item MAT-001:10:15.00 --item MAT-002:2:99.90

Without --dry-run it needs these environment variables, taken from the service key of the
Process Integration Runtime instance (plan integration-flow):
    CPI_TOKEN_URL      oauth.tokenurl
    CPI_CLIENT_ID      oauth.clientid
    CPI_CLIENT_SECRET  oauth.clientsecret
    CPI_ENDPOINT       oauth.url + /http/ariba/orders
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import escape, quoteattr

REQUIRED_ENV = ("CPI_TOKEN_URL", "CPI_CLIENT_ID", "CPI_CLIENT_SECRET", "CPI_ENDPOINT")
CXML_VERSION = "1.2.060"


def parse_item(raw: str) -> tuple[str, Decimal, Decimal]:
    """'MAT-001:10:15.00' -> ('MAT-001', Decimal('10'), Decimal('15.00'))."""
    try:
        material, quantity, price = raw.split(":")
        return material, Decimal(quantity), Decimal(price)
    except (ValueError, InvalidOperation) as error:
        raise argparse.ArgumentTypeError(f"item {raw!r} must be MATERIAL:QUANTITY:PRICE") from error


def build_order_request(
    order_id: str,
    supplier_id: str,
    items: list[tuple[str, Decimal, Decimal]],
    currency: str = "USD",
) -> str:
    """Return a cXML OrderRequest document as text."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    payload_id = f"{uuid.uuid4()}@ariba-sim.procurement-ops-lab"
    total = sum((qty * price for _, qty, price in items), Decimal("0"))
    item_xml = "".join(
        f"""
      <ItemOut quantity="{qty}" lineNumber="{line}">
        <ItemID><SupplierPartID>{escape(material)}</SupplierPartID></ItemID>
        <ItemDetail>
          <UnitPrice><Money currency={quoteattr(currency)}>{price}</Money></UnitPrice>
          <Description xml:lang="en">{escape(material)}</Description>
          <UnitOfMeasure>EA</UnitOfMeasure>
        </ItemDetail>
      </ItemOut>"""
        for line, (material, qty, price) in enumerate(items, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/{CXML_VERSION}/cXML.dtd">
<cXML payloadID={quoteattr(payload_id)} timestamp="{now}" xml:lang="en-US">
  <Header>
    <From><Credential domain="NetworkID"><Identity>AN-BUYER-LAB</Identity></Credential></From>
    <To>
      <Credential domain="NetworkID">
        <Identity>AN-SUPPLIER-{escape(supplier_id)}</Identity>
      </Credential>
    </To>
    <Sender>
      <Credential domain="NetworkID"><Identity>AN-BUYER-LAB</Identity></Credential>
      <UserAgent>procurement-ops-lab ariba_sim</UserAgent>
    </Sender>
  </Header>
  <Request deploymentMode="test">
    <OrderRequest>
      <OrderRequestHeader orderID={quoteattr(order_id)} orderDate="{now}" type="new">
        <Total><Money currency={quoteattr(currency)}>{total}</Money></Total>
        <Extrinsic name="SupplierID">{escape(supplier_id)}</Extrinsic>
      </OrderRequestHeader>{item_xml}
    </OrderRequest>
  </Request>
</cXML>
"""


def get_token() -> str:
    """OAuth client credentials against the token URL of the Process Integration Runtime key."""
    user_pass = f"{os.environ['CPI_CLIENT_ID']}:{os.environ['CPI_CLIENT_SECRET']}"
    request = urllib.request.Request(
        os.environ["CPI_TOKEN_URL"],
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": "Basic " + base64.b64encode(user_pass.encode()).decode()},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)["access_token"]


def send(document: str) -> tuple[int, str]:
    request = urllib.request.Request(
        os.environ["CPI_ENDPOINT"],
        data=document.encode(),
        method="POST",
        headers={"Content-Type": "text/xml", "Authorization": f"Bearer {get_token()}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--supplier-id", required=True, help="id of the supplier in the API")
    parser.add_argument(
        "--item", action="append", type=parse_item, required=True, help="MATERIAL:QTY:PRICE"
    )
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--order-id", default=f"PO-{datetime.now(UTC):%Y%m%d%H%M%S}")
    parser.add_argument("--dry-run", action="store_true", help="print the cXML, send nothing")
    parser.add_argument(
        "--malformed", action="store_true", help="cut the XML in half to test the error path"
    )
    args = parser.parse_args(argv)

    document = build_order_request(args.order_id, args.supplier_id, args.item, args.currency)
    if args.malformed:
        document = document[: len(document) // 2]
    if args.dry_run:
        print(document)
        return 0

    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print(f"missing environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2
    status, body = send(document)
    print(f"HTTP {status}\n{body}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
