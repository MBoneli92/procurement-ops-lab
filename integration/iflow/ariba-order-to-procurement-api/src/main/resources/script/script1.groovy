/*
 * Script step 1 of iFlow ariba-order-to-procurement-api.
 *
 * In:  cXML OrderRequest (as sent by SAP Ariba Network, here by integration/ariba_sim.py)
 * Out: JSON body for POST /purchase-orders of procurement-api
 *
 *   OrderRequestHeader/Extrinsic[@name='SupplierID']  -> supplier_id
 *   OrderRequestHeader/Total/Money/@currency          -> currency
 *   ItemOut/ItemID/SupplierPartID                     -> items[].material
 *   ItemOut/@quantity                                 -> items[].quantity
 *   ItemOut/ItemDetail/UnitPrice/Money                -> items[].unit_price
 *
 * Only JDK XML classes and groovy.json are used, so the script runs on both Groovy 2.4 and 4.
 */
import com.sap.gateway.ip.core.customdev.util.Message
import groovy.json.JsonOutput
import javax.xml.parsers.DocumentBuilderFactory
import javax.xml.xpath.XPathConstants
import javax.xml.xpath.XPathFactory
import org.w3c.dom.NodeList

def Message processData(Message message) {
    String body = message.getBody(String)

    // cXML starts with a DOCTYPE that only points to the public cXML DTD. Remove exactly that
    // line, then parse with DOCTYPE declarations forbidden: a payload from outside can never
    // declare its own entities (XXE). A DOCTYPE with anything else in it is rejected.
    body = body.replaceFirst(/<!DOCTYPE\s+cXML\s+SYSTEM\s+"[^"]*"\s*>/, "")
    def factory = DocumentBuilderFactory.newInstance()
    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
    factory.setXIncludeAware(false)
    factory.setExpandEntityReferences(false)
    def doc = factory.newDocumentBuilder().parse(new ByteArrayInputStream(body.getBytes("UTF-8")))
    def xpath = XPathFactory.newInstance().newXPath()

    String header = "/cXML/Request/OrderRequest/OrderRequestHeader"
    String orderId = xpath.evaluate(header + "/@orderID", doc)
    String supplierId = xpath.evaluate(header + "/Extrinsic[@name='SupplierID']", doc).trim()
    String currency = xpath.evaluate(header + "/Total/Money/@currency", doc)
    String payloadId = xpath.evaluate("/cXML/@payloadID", doc)

    if (!orderId || !supplierId.isInteger()) {
        throw new IllegalArgumentException(
            "cXML OrderRequest needs OrderRequestHeader/@orderID and a numeric Extrinsic SupplierID")
    }

    def items = []
    NodeList lines = (NodeList) xpath.evaluate(
        "/cXML/Request/OrderRequest/ItemOut", doc, XPathConstants.NODESET)
    for (int i = 0; i < lines.getLength(); i++) {
        def line = lines.item(i)
        items << [
            material  : xpath.evaluate("ItemID/SupplierPartID", line),
            quantity  : new BigDecimal(xpath.evaluate("@quantity", line)),
            unit_price: new BigDecimal(xpath.evaluate("ItemDetail/UnitPrice/Money", line).trim())
        ]
    }
    if (items.isEmpty()) {
        throw new IllegalArgumentException("cXML OrderRequest " + orderId + " has no ItemOut")
    }

    // Kept for the reply step and for searching in Monitor Message Processing.
    message.setProperty("AribaOrderID", orderId)
    message.setProperty("AribaPayloadID", payloadId)
    // The iFlow simulation has no message log, so the variable does not exist there.
    try {
        messageLogFactory.getMessageLog(message)?.addCustomHeaderProperty("AribaOrderID", orderId)
    } catch (MissingPropertyException ignored) {
    }
    message.setHeader("Content-Type", "application/json")
    message.setBody(JsonOutput.toJson([
        supplier_id: supplierId as Integer,
        currency   : currency ?: "USD",
        items      : items
    ]))
    return message
}
