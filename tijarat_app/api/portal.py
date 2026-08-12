import frappe
from frappe.utils import add_days, flt, getdate, nowdate

RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}


@frappe.whitelist()
def get_my_context():
	"""One call the frontend makes right after login (and on app load) to
	learn who's signed in without three separate round trips: roles decide
	what nav/pages to show, customer/supplier tell it which portal identity
	is attached to this user (set up by register_trade_party)."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw("Not logged in", frappe.AuthenticationError)

	customer = frappe.db.get_value("User Permission", {"user": user, "allow": "Customer"}, "for_value")
	supplier = frappe.db.get_value("User Permission", {"user": user, "allow": "Supplier"}, "for_value")

	return {
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name"),
		"roles": frappe.get_roles(user),
		"customer": customer,
		"supplier": supplier,
	}


@frappe.whitelist()
def get_dashboard_summary(range="30d"):
	"""KPI totals + trend + breakdowns for the web console Dashboard.
	Deliberately uses frappe.get_list (not get_all) throughout - get_list
	applies the caller's own permissions (including the User Permission rows
	register_trade_party sets up), so a Distributor Admin automatically sees
	only their own Company's data and a Retailer only their own orders,
	without this function hand-rolling that scoping itself."""
	days = RANGE_DAYS.get(range, 30)
	from_date = add_days(nowdate(), -days)

	orders = frappe.get_list(
		"Sales Order",
		filters={"transaction_date": [">=", from_date], "docstatus": 1},
		fields=["name", "grand_total", "company"],
	)
	invoices = frappe.get_list(
		"Sales Invoice",
		filters={"posting_date": [">=", from_date], "docstatus": 1},
		fields=["name", "grand_total", "outstanding_amount", "posting_date", "customer"],
	)
	payments = frappe.get_list(
		"Payment Entry",
		filters={"posting_date": [">=", from_date], "docstatus": 1, "payment_type": "Receive"},
		fields=["paid_amount"],
	)
	recent_orders = frappe.get_list(
		"Sales Invoice",
		filters={"docstatus": 1},
		fields=["name", "customer", "posting_date", "grand_total", "status"],
		order_by="posting_date desc",
		limit_page_length=20,
	)

	sales_total = sum(flt(i.grand_total) for i in invoices)
	collections_total = sum(flt(p.paid_amount) for p in payments)
	outstanding_total = sum(flt(i.outstanding_amount) for i in invoices)

	return {
		"kpis": {
			"sales": sales_total,
			"orders": len(orders),
			"collections": collections_total,
			"outstanding": outstanding_total,
		},
		"sales_trend": _bucket_by_day(invoices, from_date, days),
		"territories": _top_territories(invoices),
		"top_distributors": _top_distributors(orders),
		"recent_orders": recent_orders,
	}


def _bucket_by_day(invoices, from_date, days):
	buckets = {}
	for row in invoices:
		d = getdate(row.posting_date)
		buckets[d] = buckets.get(d, 0) + flt(row.grand_total)

	result = []
	for i in range(days):
		d = getdate(add_days(from_date, i + 1))
		result.append({"label": d.strftime("%d %b"), "value": buckets.get(d, 0)})
	return result


def _top_territories(invoices):
	territory_map = {}
	for inv in invoices:
		if not inv.customer:
			continue
		territory = frappe.db.get_value("Customer", inv.customer, "territory")
		if not territory:
			continue
		territory_map[territory] = territory_map.get(territory, 0) + flt(inv.grand_total)
	ranked = sorted(territory_map.items(), key=lambda x: -x[1])
	return [{"name": name, "value": value} for name, value in ranked[:5]]


def _top_distributors(orders):
	distributor_map = {}
	for order in orders:
		if not order.company:
			continue
		bucket = distributor_map.setdefault(order.company, {"value": 0, "orders": 0})
		bucket["value"] += flt(order.grand_total)
		bucket["orders"] += 1
	ranked = sorted(distributor_map.items(), key=lambda x: -x[1]["value"])
	return [
		{"name": name, "value": data["value"], "orders": data["orders"]} for name, data in ranked[:5]
	]
