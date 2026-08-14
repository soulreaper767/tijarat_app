import frappe
from frappe.utils import add_months, flt, getdate, nowdate

# Sales Order's native `status` collapsed into four kanban columns instead of
# the raw seven ("Draft", "On Hold", "To Deliver and Bill", "To Bill",
# "To Deliver", "Completed", "Cancelled", "Closed") - a portal user cares
# about "not started yet / in progress / done / cancelled", not the exact
# native workflow label.
KANBAN_COLUMNS = [
	("Draft", ["Draft", "On Hold"]),
	("In Progress", ["To Deliver and Bill", "To Bill", "To Deliver"]),
	("Completed", ["Completed", "Closed"]),
	("Cancelled", ["Cancelled"]),
]


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.redirect("/login")

	user = frappe.session.user
	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.full_name = frappe.db.get_value("User", user, "full_name") or user
	context.roles = frappe.get_roles(user)
	context.customer = frappe.db.get_value("User Permission", {"user": user, "allow": "Customer"}, "for_value")
	context.supplier = frappe.db.get_value("User Permission", {"user": user, "allow": "Supplier"}, "for_value")

	currency = frappe.db.get_default("currency") or "PKR"
	context.currency = currency

	context.buyer = _buyer_summary(currency) if context.customer else None
	context.seller = _seller_summary(currency) if context.supplier else None
	return context


def _buyer_summary(currency):
	customer = frappe.db.get_value("User Permission", {"user": frappe.session.user, "allow": "Customer"}, "for_value")
	# frappe.get_all with an *explicit* customer filter, not frappe.get_list -
	# every Tijarat account holds both a Customer and a Supplier User
	# Permission (apply_to_all_doctypes=1, set at registration), and Sales
	# Order has link fields to both (customer, primary_supplier). Frappe's
	# get_list ANDs every link-field's user-permission restriction together,
	# so it would silently require customer=mine AND primary_supplier=mine
	# on the *same* order - true only for a self-sale, so it returns
	# effectively nothing for a normal buyer. Filtering explicitly here
	# sidesteps that rather than relying on the ambient (broken, for this
	# account shape) permission scoping.
	orders = frappe.get_all(
		"Sales Order",
		filters={"docstatus": 1, "customer": customer},
		fields=["name", "status", "grand_total", "transaction_date"],
		order_by="transaction_date desc",
		limit_page_length=200,
	)
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "customer": customer},
		fields=["name", "grand_total", "outstanding_amount", "posting_date"],
		limit_page_length=500,
	)

	total_spend = sum(flt(i.grand_total) for i in invoices)
	outstanding = sum(flt(i.outstanding_amount) for i in invoices)

	board = {label: [] for label, _ in KANBAN_COLUMNS}
	for order in orders:
		for label, statuses in KANBAN_COLUMNS:
			if order.status in statuses:
				board[label].append(order)
				break

	return {
		"order_count": len(orders),
		"total_spend": fmt_compact_currency(total_spend, currency),
		"outstanding": fmt_compact_currency(outstanding, currency),
		"outstanding_raw": outstanding,
		"monthly_trend": _monthly_trend(invoices),
		"board": [{"label": label, "orders": board[label][:6], "count": len(board[label])} for label, _ in KANBAN_COLUMNS],
		"recent_orders": orders[:5],
	}


def _seller_summary(currency):
	supplier = frappe.db.get_value("User Permission", {"user": frappe.session.user, "allow": "Supplier"}, "for_value")
	# get_all with an explicit primary_supplier filter - see the comment in
	# _buyer_summary on why get_list's ambient scoping doesn't work for an
	# account that (like every Tijarat account) holds both a Customer and a
	# Supplier permission at once.
	listings = frappe.get_all(
		"Item Listing", filters={"is_active": 1, "supplier": supplier}, fields=["name"], limit_page_length=0
	)
	sales = frappe.get_all(
		"Sales Order",
		filters={"docstatus": 1, "primary_supplier": supplier},
		fields=["name", "grand_total", "status", "transaction_date"],
		order_by="transaction_date desc",
		limit_page_length=200,
	)
	revenue = sum(flt(s.grand_total) for s in sales)

	return {
		"active_listings": len(listings),
		"orders_received": len(sales),
		"revenue": fmt_compact_currency(revenue, currency),
		"recent_sales": sales[:5],
	}


def _monthly_trend(invoices):
	buckets = {}
	for inv in invoices:
		key = getdate(inv.posting_date).strftime("%Y-%m")
		buckets[key] = buckets.get(key, 0) + flt(inv.grand_total)

	months = []
	for i in range(5, -1, -1):
		d = getdate(add_months(nowdate(), -i))
		key = d.strftime("%Y-%m")
		months.append({"label": d.strftime("%b"), "value": buckets.get(key, 0)})
	peak = max((m["value"] for m in months), default=0) or 1
	for m in months:
		m["pct"] = round((m["value"] / peak) * 100)
	return months


def fmt_compact_currency(value, currency="PKR"):
	"""35.9 Cr-style Indian abbreviation isn't the right convention here -
	this gives the standard million/thousand notation instead, e.g.
	'PKR 3.6M', 'PKR 850K', 'PKR 1,240'."""
	value = flt(value)
	sign = "-" if value < 0 else ""
	value = abs(value)
	if value >= 1_000_000:
		return f"{sign}{currency} {value / 1_000_000:.1f}M"
	if value >= 1_000:
		return f"{sign}{currency} {value / 1_000:.1f}K"
	return f"{sign}{currency} {value:,.0f}"
