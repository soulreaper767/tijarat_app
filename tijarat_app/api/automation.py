import frappe
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

# --- Daily jobs -----------------------------------------------------------


def generate_journey_plan_visits():
	"""Populates today's Journey Plan Visit records from every active Route's
	`repeat_on` schedule + its Route Stop rows - the field has existed since
	the Route doctype was built but nothing generated visits from it yet."""
	today = getdate(nowdate())
	weekday = today.strftime("%A")

	routes = frappe.get_all(
		"Route",
		filters={"is_active": 1},
		fields=["name", "sales_person", "repeat_on"],
	)
	for route in routes:
		if route.repeat_on not in ("Daily", weekday):
			continue
		stops = frappe.get_all(
			"Route Stop",
			filters={"parent": route.name, "parenttype": "Route"},
			fields=["customer", "planned_time"],
			order_by="sequence asc",
		)
		for stop in stops:
			if not stop.customer:
				continue
			if frappe.db.exists(
				"Journey Plan Visit",
				{"route": route.name, "customer": stop.customer, "visit_date": today},
			):
				continue
			frappe.get_doc(
				{
					"doctype": "Journey Plan Visit",
					"route": route.name,
					"sales_person": route.sales_person,
					"customer": stop.customer,
					"visit_date": today,
					"planned_time": stop.planned_time,
				}
			).insert(ignore_permissions=True)
	frappe.db.commit()


def check_pjp_compliance():
	"""End of day: any visit still 'Planned' for today never got a check-in -
	flip it to Missed so the PJP Compliance report (report/pjp_compliance)
	reflects reality without a human combing through the day's visits."""
	frappe.db.set_value(
		"Journey Plan Visit",
		{"visit_date": getdate(nowdate()), "status": "Planned"},
		"status",
		"Missed",
	)
	frappe.db.commit()


def create_low_stock_purchase_orders():
	"""Items below their configured reorder level (native Item > Reorder
	Levels) get a draft Purchase Order against their default Supplier -
	replenishment doesn't wait on a human noticing the Bin is low."""
	reorder_rows = frappe.get_all(
		"Item Reorder",
		filters={"warehouse_reorder_level": [">", 0]},
		fields=[
			"parent as item_code",
			"warehouse",
			"warehouse_reorder_level",
			"warehouse_reorder_qty",
		],
	)
	for row in reorder_rows:
		item = frappe.get_cached_value(
			"Item", row.item_code, ["disabled", "is_purchase_item"], as_dict=True
		)
		if not item or item.disabled or not item.is_purchase_item:
			continue

		actual_qty = (
			frappe.db.get_value(
				"Bin", {"item_code": row.item_code, "warehouse": row.warehouse}, "actual_qty"
			)
			or 0
		)
		if flt(actual_qty) >= flt(row.warehouse_reorder_level):
			continue

		default_supplier = frappe.db.get_value(
			"Item Default", {"parent": row.item_code, "parenttype": "Item"}, "default_supplier"
		)
		if not default_supplier:
			continue

		dedup_tag = f"tijarat-auto-reorder:{row.item_code}:{row.warehouse}:{nowdate()}"
		if frappe.db.exists("Purchase Order", {"remarks": dedup_tag}):
			continue

		schedule_date = add_days(nowdate(), 3)
		frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": default_supplier,
				"schedule_date": schedule_date,
				"remarks": dedup_tag,
				"items": [
					{
						"item_code": row.item_code,
						"qty": row.warehouse_reorder_qty or 1,
						"warehouse": row.warehouse,
						"schedule_date": schedule_date,
					}
				],
			}
		).insert(ignore_permissions=True)
	frappe.db.commit()


def flag_overdue_payments():
	"""Stamps Customer.payment_overdue_days from the age of each customer's
	oldest overdue Sales Invoice - feeds the Finance page/aging report on the
	frontend without it having to compute aging client-side."""
	today = getdate(nowdate())
	rows = frappe.db.sql(
		"""
		select customer, min(due_date) as oldest_due_date
		from `tabSales Invoice`
		where docstatus = 1 and outstanding_amount > 0 and due_date < %s
		group by customer
		""",
		(today,),
		as_dict=True,
	)
	overdue_customers = set()
	for row in rows:
		days = (today - getdate(row.oldest_due_date)).days
		frappe.db.set_value("Customer", row.customer, "payment_overdue_days", cint(days))
		overdue_customers.add(row.customer)

	# Clear the flag for anyone no longer overdue.
	stale = frappe.get_all(
		"Customer",
		filters={"payment_overdue_days": [">", 0]},
		pluck="name",
	)
	for name in stale:
		if name not in overdue_customers:
			frappe.db.set_value("Customer", name, "payment_overdue_days", 0)
	frappe.db.commit()


# --- Hourly jobs ------------------------------------------------------------


def escalate_overdue_support_tickets():
	"""Any ticket still Open/In Progress past its SLA due time gets bumped to
	Escalated - the human-facing consequence (a notification, a channel
	message) is n8n's job; this just makes the state itself trustworthy."""
	overdue = frappe.get_all(
		"Support Ticket",
		filters={
			"workflow_state": ["in", ["Open", "In Progress"]],
			"sla_due_on": ["<", now_datetime()],
		},
		pluck="name",
	)
	for name in overdue:
		frappe.db.set_value("Support Ticket", name, "workflow_state", "Escalated")
	frappe.db.commit()


# --- Monthly jobs -------------------------------------------------------


def recompute_tijarat_scores():
	"""First-pass Trust Intelligence score: order frequency, on-time payment
	rate, and dispute rate per Customer/Supplier, written to the
	tijarat_score/score_updated_on fields already reserved for it. Deliberately
	simple - refine the weighting once real transaction history exists."""
	for party_type in ("Customer", "Supplier"):
		party_field = "customer" if party_type == "Customer" else "supplier"
		invoice_doctype = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"

		parties = frappe.get_all(party_type, filters={"lifecycle_status": "Productive"}, pluck="name")
		for party in parties:
			total_invoices = frappe.db.count(
				invoice_doctype, {party_field: party, "docstatus": 1}
			)
			if not total_invoices:
				continue

			paid_on_time = frappe.db.sql(
				f"""
				select count(*) from `tab{invoice_doctype}`
				where {party_field} = %s and docstatus = 1
				  and outstanding_amount = 0 and due_date >= modified
				""",
				(party,),
			)[0][0]

			disputes = frappe.db.count("Support Ticket", {"customer": party}) if party_type == "Customer" else 0

			frequency_score = min(total_invoices, 50)
			repayment_score = (paid_on_time / total_invoices) * 40 if total_invoices else 0
			dispute_penalty = min(disputes * 5, 20)

			score = max(0, min(100, round(frequency_score * 0.4 + repayment_score - dispute_penalty)))
			frappe.db.set_value(
				party_type, party, {"tijarat_score": score, "score_updated_on": now_datetime()}
			)
	frappe.db.commit()


# --- Whitelisted helpers --------------------------------------------------


@frappe.whitelist()
def create_auto_repeat_from_order(sales_order, frequency="Weekly"):
	"""Offers "repeat this order" without the frontend having to hand-build
	the native Auto Repeat form - wraps frappe.get_doc for the one native
	doctype (Auto Repeat) this app leaves entirely as-is."""
	order = frappe.get_doc("Sales Order", sales_order)
	if order.docstatus != 1:
		frappe.throw("Only a submitted Sales Order can be turned into a repeat order.")

	auto_repeat = frappe.get_doc(
		{
			"doctype": "Auto Repeat",
			"reference_doctype": "Sales Order",
			"reference_document": order.name,
			"frequency": frequency,
			"start_date": nowdate(),
			"submit_on_creation": 1,
			"party_type": "Customer",
			"party": order.customer,
		}
	)
	auto_repeat.insert(ignore_permissions=(frappe.session.user != order.owner))
	frappe.db.commit()
	return auto_repeat.name
