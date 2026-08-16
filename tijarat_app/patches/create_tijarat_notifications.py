import frappe

NOTIFICATIONS = [
	{
		"name": "Tijarat: Order Confirmed",
		"document_type": "Sales Order",
		"event": "Submit",
		"channel": "Email",
		"subject": "Order {{ doc.name }} confirmed",
		"message": "<p>Hi {{ doc.customer_name }},</p><p>Your order <b>{{ doc.name }}</b> for "
		"Rs. {{ doc.grand_total }} has been confirmed and is being processed.</p>",
		"recipients": [{"receiver_by_document_field": "contact_email"}],
	},
	{
		"name": "Tijarat: Invoice Generated",
		"document_type": "Sales Invoice",
		"event": "Submit",
		"channel": "Email",
		"subject": "Invoice {{ doc.name }} for your order",
		"message": "<p>Hi {{ doc.customer_name }},</p><p>Invoice <b>{{ doc.name }}</b> for "
		"Rs. {{ doc.grand_total }} has been generated. Outstanding: Rs. {{ doc.outstanding_amount }}.</p>",
		"recipients": [{"receiver_by_document_field": "contact_email"}],
	},
	{
		"name": "Tijarat: Order Dispatched",
		"document_type": "Delivery Note",
		"event": "Submit",
		"channel": "Email",
		"subject": "Your order {{ doc.name }} is on its way",
		"message": "<p>Hi {{ doc.customer_name }},</p><p>Your shipment <b>{{ doc.name }}</b> has "
		"been dispatched and is on its way to you.</p>",
		"recipients": [{"receiver_by_document_field": "contact_email"}],
	},
	{
		"name": "Tijarat: Payment Received",
		"document_type": "Payment Entry",
		"event": "Submit",
		"channel": "System Notification",
		"subject": "Payment {{ doc.name }} received - Rs. {{ doc.paid_amount }}",
		"message": "<p>Payment <b>{{ doc.name }}</b> of Rs. {{ doc.paid_amount }} from "
		"{{ doc.party_name }} was received and reconciled.</p>",
		"condition": 'doc.payment_type == "Receive"',
		"recipients": [{"receiver_by_role": "Sales Coordinator"}],
	},
	{
		"name": "Tijarat: Support Ticket Escalated",
		"document_type": "Support Ticket",
		"event": "Value Change",
		"value_changed": "workflow_state",
		"channel": "System Notification",
		"subject": "Support Ticket {{ doc.name }} escalated",
		"message": "<p>Support Ticket <b>{{ doc.name }}</b> has been escalated and needs attention.</p>",
		"condition": 'doc.workflow_state == "Escalated"',
		"recipients": [{"receiver_by_role": "Distributor Admin"}],
	},
]


def execute():
	for config in NOTIFICATIONS:
		_ensure_notification(config)
	frappe.db.commit()


def _ensure_notification(config):
	if frappe.db.exists("Notification", config["name"]):
		return
	try:
		doc = frappe.new_doc("Notification")
		doc.name = config["name"]
		doc.subject = config["subject"]
		doc.document_type = config["document_type"]
		doc.event = config["event"]
		doc.channel = config["channel"]
		doc.message = config["message"]
		doc.enabled = 1
		doc.send_system_notification = 1 if config["channel"] == "System Notification" else 0
		if config.get("value_changed"):
			doc.value_changed = config["value_changed"]
		if config.get("condition"):
			doc.condition = config["condition"]
		for recipient in config["recipients"]:
			doc.append("recipients", recipient)
		doc.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title="Tijarat: could not create notification",
			message=f"Notification '{config['name']}' could not be created: {frappe.get_traceback()}",
		)
