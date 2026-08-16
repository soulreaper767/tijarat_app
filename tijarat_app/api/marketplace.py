import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_item_listings(item_code, territory=None, customer=None):
	"""Returns every active, currently-valid listing for an Item, sorted by
	price - this is what powers the "same item, different supplier rates"
	comparison view on the frontend. If a territory or customer is given,
	listings scoped to a different territory are excluded (territory-lock
	applies to marketplace visibility, not just order placement)."""
	if not territory and customer:
		territory = frappe.db.get_value("Customer", customer, "territory")

	filters = {"item": item_code, "is_active": 1}
	listings = frappe.get_all(
		"Item Listing",
		filters=filters,
		fields=[
			"name",
			"supplier",
			"territory",
			"rate",
			"currency",
			"uom",
			"min_order_qty",
			"stock_status",
			"valid_from",
			"valid_upto",
		],
		order_by="rate asc",
	)

	result = []
	for listing in listings:
		if listing.territory and territory and listing.territory != territory:
			continue
		doc = frappe.get_cached_doc("Item Listing", listing.name)
		if not doc.is_currently_valid():
			continue
		listing["supplier_name"] = frappe.db.get_value("Supplier", listing.supplier, "supplier_name")
		result.append(listing)

	return result


@frappe.whitelist()
def book_order(customer, lines, booking_channel="Self", delivery_date=None, service_package=None, referral_code=None):
	"""Creates a Sales Order from a set of lines. Used identically whether the
	retailer books it themselves (booking_channel = Online/Self) or a Field
	Officer books it on their behalf (booking_channel = Assisted) - only the
	session and this one parameter differ.

	Each line is either `{"item_listing": "LST-...", "qty": 5}` (frontend has
	already picked a specific supplier/rate, e.g. from the price-comparison
	view) or `{"item_code": "ITM-...", "qty": 5}` (frontend just wants "this
	item" and leaves supplier resolution to the backend). item_code lines are
	auto-matched to the best territory listing for the customer - same
	preference order as get_item_listings (exact territory, then a supplier
	serving every territory, lowest rate first). If a line can't be matched
	to any listing at all, the order is still created (as a draft, tagged
	needs_supplier_assignment) rather than losing the sale, and gets routed
	to a Customer Service user to resolve by hand.
	"""
	if isinstance(lines, str):
		lines = frappe.parse_json(lines)

	if not lines:
		frappe.throw(_("At least one item is required to book an order."))

	customer_territory = frappe.db.get_value("Customer", customer, "territory")

	# All *resolved* lines must share one Supplier - a Sales Order has one
	# seller. If a buyer wants items from multiple suppliers, book_order is
	# called once per supplier from the frontend, not mixed in one call.
	items = []
	suppliers = set()
	unresolved_items = []
	for line in lines:
		listing = None
		if line.get("item_listing"):
			listing = frappe.get_cached_doc("Item Listing", line["item_listing"])
			if not listing.is_currently_valid():
				frappe.throw(_("Listing {0} is no longer available.").format(line["item_listing"]))
		elif line.get("item_code"):
			match = _resolve_listing_for_item(line["item_code"], customer_territory)
			if match:
				listing = frappe.get_cached_doc("Item Listing", match.name)
		else:
			frappe.throw(_("Each line needs either an item_listing or an item_code."))

		if listing:
			suppliers.add(listing.supplier)
			items.append(
				{
					"item_code": listing.item,
					"qty": line.get("qty", listing.min_order_qty or 1),
					"rate": listing.rate,
					"uom": listing.uom,
					"item_listing": listing.name,
				}
			)
		else:
			item_code = line["item_code"]
			items.append(
				{
					"item_code": item_code,
					"qty": line.get("qty", 1),
					"rate": frappe.db.get_value("Item", item_code, "standard_rate") or 0,
				}
			)
			unresolved_items.append(item_code)

	if len(suppliers) > 1:
		frappe.throw(_("All items in one order must come from the same supplier. Book separate orders per supplier."))

	order = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer,
			"territory": customer_territory,
			"delivery_date": delivery_date or frappe.utils.add_days(frappe.utils.nowdate(), 2),
			"booking_channel": booking_channel,
			"booked_by": frappe.session.user,
			"service_package": service_package,
			"referral_code": referral_code,
			"items": items,
		}
	)
	order.insert(ignore_permissions=(booking_channel == "Assisted"))

	# Auto-submission: territory lock and MRP ceiling already ran as blocking
	# `validate` hooks by the time insert() succeeds, so the remaining gates
	# are the customer's credit limit and every line having a resolved
	# supplier - stay a draft for a human to review/finish if either fails.
	auto_submitted = False
	if not unresolved_items and _within_credit_limit(order):
		order.submit()
		auto_submitted = True

	# primary_supplier/needs_supplier_assignment are written last, via a raw
	# DB update rather than on the doc dict above or via db_set before
	# submit(): a self-service Customer's own User Permission restricts every
	# Supplier Link field to *their own* Supplier record (set at
	# registration), so setting primary_supplier to the *seller's* Supplier
	# anywhere earlier in this flow would fail permission validation on
	# insert - and submit()'s internal save() would overwrite an earlier
	# db_set with the stale in-memory value anyway. Writing here, after every
	# save()/submit() call has already happened, avoids both problems.
	frappe.db.set_value(
		"Sales Order",
		order.name,
		{
			"primary_supplier": next(iter(suppliers)) if len(suppliers) == 1 else None,
			"needs_supplier_assignment": 1 if unresolved_items else 0,
		},
	)
	order.reload()

	if unresolved_items:
		_route_to_customer_service(order, unresolved_items)

	frappe.db.commit()
	result = order.as_dict()
	result["auto_submitted"] = auto_submitted
	return result


def _resolve_listing_for_item(item_code, territory):
	"""Best territory-matched Item Listing for a plain item_code line: an
	exact match on the customer's territory wins; failing that, a supplier
	whose listing has no territory (serves everywhere) is used; lowest rate
	breaks ties either way. Returns None if nothing is tagged for this item
	at all, which is exactly the "nothing missing" case book_order routes to
	Customer Service instead of failing outright."""
	candidates = frappe.get_all(
		"Item Listing",
		filters={"item": item_code, "is_active": 1},
		fields=["name", "supplier", "territory", "rate"],
		order_by="rate asc",
	)

	exact_matches, blanket_matches = [], []
	for candidate in candidates:
		doc = frappe.get_cached_doc("Item Listing", candidate.name)
		if not doc.is_currently_valid():
			continue
		if territory and candidate.territory == territory:
			exact_matches.append(candidate)
		elif not candidate.territory:
			blanket_matches.append(candidate)

	pool = exact_matches or blanket_matches
	return pool[0] if pool else None


def _route_to_customer_service(order, unresolved_items):
	"""No Item Listing is tagged for one or more lines in the customer's
	territory - rather than blocking the sale, the order is kept as an
	unsubmitted draft and assigned (via a native ToDo) to one Customer
	Service user, who resolves/attaches a supplier and submits it by hand."""
	assignee = _pick_customer_service_user()
	if not assignee:
		frappe.log_error(
			title="Tijarat: no Customer Service user available",
			message=(
				f"Sales Order {order.name} needs manual supplier assignment for "
				f"{', '.join(unresolved_items)}, but no enabled user holds the "
				f"Customer Service role."
			),
		)
		return

	frappe.get_doc(
		{
			"doctype": "ToDo",
			"allocated_to": assignee,
			"reference_type": "Sales Order",
			"reference_name": order.name,
			"priority": "High",
			"description": (
				f"Order {order.name} for {order.customer} has no territory-matched supplier "
				f"for: {', '.join(unresolved_items)}. Attach a supplier/Item Listing and submit "
				f"it manually."
			),
		}
	).insert(ignore_permissions=True)


def _pick_customer_service_user():
	"""First enabled user holding the Customer Service role - the app tags
	the order to exactly one internal owner rather than a queue, so there's
	always a single accountable person per gap."""
	assignees = frappe.get_all(
		"Has Role",
		filters={"role": "Customer Service", "parenttype": "User"},
		fields=["parent"],
	)
	for row in assignees:
		if frappe.db.get_value("User", row.parent, "enabled"):
			return row.parent
	return None


def _within_credit_limit(order):
	credit_limit = frappe.db.get_value(
		"Customer Credit Limit", {"parent": order.customer, "parenttype": "Customer"}, "credit_limit"
	)
	if not credit_limit:
		return True
	outstanding = (
		frappe.db.sql(
			"""select sum(outstanding_amount) from `tabSales Invoice`
			   where customer=%s and docstatus=1""",
			(order.customer,),
		)[0][0]
		or 0
	)
	return (flt(outstanding) + flt(order.grand_total)) <= flt(credit_limit)
