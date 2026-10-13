/*
 * Script step 2 of iFlow ariba-order-to-procurement-api.
 *
 * In:  JSON answer of POST /purchase-orders (201 Created)
 * Out: cXML Response with Status 200, the reply SAP Ariba Network expects for an OrderRequest
 */
import com.sap.gateway.ip.core.customdev.util.Message
import groovy.json.JsonSlurper
import java.time.OffsetDateTime
import java.time.ZoneOffset

def Message processData(Message message) {
    def order = new JsonSlurper().parseText(message.getBody(String))
    String aribaOrderId = message.getProperty("AribaOrderID") ?: ""
    String payloadId = message.getProperty("AribaPayloadID") ?: ""
    String now = OffsetDateTime.now(ZoneOffset.UTC).withNano(0).toString()

    def messageLog = messageLogFactory.getMessageLog(message)
    if (messageLog != null) {
        messageLog.addCustomHeaderProperty("ProcurementOrderID", String.valueOf(order.id))
    }

    String text = "Ariba order " + aribaOrderId + " created as purchase order " + order.id +
        " with status " + order.status
    message.setHeader("Content-Type", "text/xml")
    message.setBody(
        '<?xml version="1.0" encoding="UTF-8"?>\n' +
        '<cXML payloadID="' + escape(payloadId) + '.response" timestamp="' + now + '">' +
        '<Response><Status code="200" text="OK">' + escape(text) + '</Status></Response>' +
        '</cXML>\n')
    return message
}

String escape(String value) {
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("\"", "&quot;").replace("'", "&apos;")
}
