import frappe


def sync_primary_address_contact(doc, method=None):
	"""Customer.on_update - the stock Customer form's own primary-address/
	contact fields (customer_primary_address, customer_primary_contact) only
	become usable via a separate "Create a New Address/Contact" popup AFTER
	the Customer is first saved, and still need several clicks per record.
	The shop_* fields (see fixtures/custom_field.json) sit on the same tab
	as customer_name/customer_group/territory so a Field Officer can enter
	the whole shop - including its address and the shopkeeper's own contact
	number - in one continuous form and one save. This keeps the real
	Address and Contact records (and Customer's own customer_primary_address/
	customer_primary_contact links, which everything else in the app and in
	ERPNext already expects) in sync behind the scenes."""
	_sync_primary_address(doc)
	_sync_primary_contact(doc)


def _sync_primary_address(doc):
	if not doc.get("shop_address_line1") or not doc.get("shop_city"):
		return

	existing_name = doc.customer_primary_address
	if existing_name and frappe.db.exists("Address", existing_name):
		addr = frappe.get_doc("Address", existing_name)
		is_new_address = False
	else:
		addr = frappe.new_doc("Address")
		addr.address_title = doc.customer_name
		addr.address_type = "Shop"
		addr.is_primary_address = 1
		addr.is_shipping_address = 1
		addr.append("links", {"link_doctype": "Customer", "link_name": doc.name})
		is_new_address = True

	changed = is_new_address
	for fieldname, value in (
		("address_line1", doc.get("shop_address_line1")),
		("city", doc.get("shop_city")),
		("phone", doc.get("shop_phone")),
	):
		if value and addr.get(fieldname) != value:
			addr.set(fieldname, value)
			changed = True
	if not addr.country:
		addr.country = frappe.db.get_default("country") or "Pakistan"
		changed = True

	if not changed:
		return

	if is_new_address:
		addr.insert(ignore_permissions=True)
		frappe.db.set_value("Customer", doc.name, "customer_primary_address", addr.name, update_modified=False)
		doc.customer_primary_address = addr.name
	else:
		addr.save(ignore_permissions=True)


def _sync_primary_contact(doc):
	if not doc.get("shop_contact_name") and not doc.get("shop_contact_mobile"):
		return

	existing_name = doc.customer_primary_contact
	if existing_name and frappe.db.exists("Contact", existing_name):
		contact = frappe.get_doc("Contact", existing_name)
		is_new_contact = False
	else:
		contact = frappe.new_doc("Contact")
		contact.is_primary_contact = 1
		contact.append("links", {"link_doctype": "Customer", "link_name": doc.name})
		is_new_contact = True

	changed = is_new_contact
	name_value = doc.get("shop_contact_name")
	if name_value and contact.first_name != name_value:
		contact.first_name = name_value
		changed = True
	if contact.is_new() and not contact.first_name:
		# Contact requires a name - fall back to the shop's own name rather
		# than blocking the save when only a mobile number was given.
		contact.first_name = doc.customer_name
		changed = True

	mobile = doc.get("shop_contact_mobile")
	if mobile:
		# Contact.validate()'s set_primary("mobile_no") derives the
		# top-level mobile_no field FROM this child table (it's the actual
		# source of truth) - setting mobile_no directly gets silently
		# discarded if phone_nos has no matching row.
		primary_rows = [row for row in contact.get("phone_nos", []) if row.is_primary_mobile_no]
		if primary_rows:
			if primary_rows[0].phone != mobile:
				primary_rows[0].phone = mobile
				changed = True
		elif not any(row.phone == mobile for row in contact.get("phone_nos", [])):
			contact.append("phone_nos", {"phone": mobile, "is_primary_mobile_no": 1})
			changed = True

	if not changed:
		return

	if is_new_contact:
		contact.insert(ignore_permissions=True)
		frappe.db.set_value("Customer", doc.name, "customer_primary_contact", contact.name, update_modified=False)
		doc.customer_primary_contact = contact.name
	else:
		contact.save(ignore_permissions=True)
