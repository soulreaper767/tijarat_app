import frappe
from frappe import _


BUSINESS_TYPE_TO_CUSTOMER_GROUP = {
	"retailer": "Retailer",
	"wholesaler": "Wholesaler",
	"distributor": "Distributor",
	"manufacturer": "Manufacturer / Importer",
	"ecommerce": "E-commerce",
}


def _login_email_for(mobile_no):
	# Frappe's User.name/email must be email-shaped; every party registered
	# through this app logs in by phone number, not this synthetic address -
	# see login_with_mobile.
	return f"{mobile_no}@tijaratapp.users"


@frappe.whitelist(allow_guest=True)
def login_with_mobile(mobile_no, password):
	"""Native `/api/method/login` only accepts an email-shaped `usr`, but
	every party registered through register_trade_party thinks of their
	mobile number as their identity, not the synthetic
	`{mobile}@tijaratapp.users` address behind it. This resolves the real
	User and drives the same LoginManager the native endpoint uses, so the
	session cookie it sets is indistinguishable from a normal login."""
	user = frappe.db.get_value("User", {"mobile_no": mobile_no, "enabled": 1}, "name")
	if not user:
		frappe.throw(_("No account found for this mobile number."), frappe.AuthenticationError)

	frappe.local.login_manager.authenticate(user=user, pwd=password)
	frappe.local.login_manager.post_login()
	return {
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name"),
	}


@frappe.whitelist(allow_guest=True)
def register_trade_party(
	party_name,
	contact_person,
	mobile_no,
	city,
	business_type=None,
	trade_category=None,
	email=None,
	address=None,
	password=None,
	latitude=None,
	longitude=None,
	registration_channel="Self",
	referral_code=None,
):
	"""Single entry point for both self-registration and Field-Officer-assisted
	registration. Creates Customer + Supplier + Party Link + Contact (+ Address
	if given) + a portal User with both roles, in one call - either the whole
	trio exists together or none of it does.

	`business_type` is the shape the frontend's registration form actually
	collects (retailer/wholesaler/distributor/manufacturer/ecommerce) and
	drives the Customer Group. `trade_category` is a separate, optional
	Item Group classification (e.g. "Beverages") for catalog-side filtering.
	"""
	if frappe.db.exists("Contact", {"mobile_no": mobile_no}):
		frappe.throw(_("This mobile number is already registered."))

	customer_group = _customer_group_for(business_type)
	territory = _resolve_territory(city)

	# served_territories seeds the multi-territory model with this party's
	# home/registration territory as the primary one - Item Listing later
	# auto-fills from this when a Supplier books a listing without picking a
	# territory explicitly, and add_served_territory (api/territory.py) is
	# how they register additional territories as their business expands.
	# Two separate list literals - not one shared reference - since insert()
	# stamps parent/name onto each child row dict in place.
	customer = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": party_name,
			"customer_group": customer_group,
			"territory": territory,
			"lifecycle_status": "Registered",
			"served_territories": [{"territory": territory, "is_primary": 1}],
		}
	).insert(ignore_permissions=True)

	supplier = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": party_name,
			"supplier_group": _default_supplier_group(),
			"lifecycle_status": "Registered",
			"is_brand_owner": 1 if business_type == "manufacturer" else 0,
			"served_territories": [{"territory": territory, "is_primary": 1}],
		}
	).insert(ignore_permissions=True)

	frappe.get_doc(
		{
			"doctype": "Party Link",
			"primary_role": "Customer",
			"primary_party": customer.name,
			"secondary_role": "Supplier",
			"secondary_party": supplier.name,
		}
	).insert(ignore_permissions=True)

	contact_doc = {
		"doctype": "Contact",
		"first_name": contact_person,
		"mobile_no": mobile_no,
		"latitude": latitude,
		"longitude": longitude,
		"trade_category": trade_category,
		"registration_channel": registration_channel,
		"registered_by": frappe.session.user,
		"referral_code_used": referral_code,
		"links": [
			{"link_doctype": "Customer", "link_name": customer.name},
			{"link_doctype": "Supplier", "link_name": supplier.name},
		],
	}
	# Always claim the synthetic login email as one of this Contact's
	# addresses, even when a real email is also given (marked primary
	# instead, if so) - Frappe's native User.create_contact background job
	# looks up an existing Contact by the User's email and only auto-creates
	# a new one if that lookup comes back empty. Without this, that lookup
	# never finds the Contact we just made, and the native job tries to
	# create a second, colliding one on every registration.
	login_email = _login_email_for(mobile_no)
	contact_doc["email_ids"] = [{"email_id": login_email, "is_primary": 0 if email else 1}]
	if email:
		contact_doc["email_ids"].append({"email_id": email, "is_primary": 1})
	contact = frappe.get_doc(contact_doc).insert(ignore_permissions=True)

	address_doc = None
	if address:
		address_doc = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": party_name,
				"address_type": "Shop",
				"address_line1": address,
				"city": city,
				"links": [
					{"link_doctype": "Customer", "link_name": customer.name},
					{"link_doctype": "Supplier", "link_name": supplier.name},
				],
			}
		).insert(ignore_permissions=True)

	user = _grant_portal_access(
		mobile_no,
		party_name,
		customer.name,
		supplier.name,
		contact.name,
		address_doc.name if address_doc else None,
		business_type,
		password,
	)

	if referral_code and frappe.db.exists("Referral Code", referral_code):
		frappe.get_doc("Referral Code", referral_code).record_usage()

	frappe.db.commit()
	return {
		"customer": customer.name,
		"supplier": supplier.name,
		"contact": contact.name,
		"user": user.name,
	}


def _customer_group_for(business_type):
	group = BUSINESS_TYPE_TO_CUSTOMER_GROUP.get((business_type or "").lower())
	if group and frappe.db.exists("Customer Group", group):
		return group
	# Unrecognized/blank business_type - fall back to Retailer rather than
	# guessing, staff can reclassify via the normal Customer form.
	default_group = "Retailer"
	if frappe.db.exists("Customer Group", default_group):
		return default_group
	return frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups"


def _default_supplier_group():
	# frappe.get_all, not frappe.db.get_list - this is an internal system
	# lookup during a guest-callable registration flow, and get_list (unlike
	# get_all) enforces the *calling user's* permissions. A real Guest
	# session has no permission on Supplier Group at all, so get_list threw
	# PermissionError here - masked in every earlier test because those ran
	# as Administrator, who bypasses permission checks universally.
	existing = frappe.get_all("Supplier Group", limit=1, pluck="name")
	return existing[0] if existing else "All Supplier Groups"


def _resolve_territory(city):
	if not city:
		return frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
	if frappe.db.exists("Territory", city):
		return city
	# First-time city - create it as a leaf Territory under the root so
	# territory-lock validation (api/territory.py) has something real to
	# check against, rather than silently falling back to the root.
	# frappe.get_all, not frappe.db.get_all - same reasoning as
	# _default_supplier_group above: this must not depend on the calling
	# Guest session having any permission on Territory.
	root = frappe.get_all("Territory", filters={"is_group": 1, "parent_territory": ""}, limit=1, pluck="name")
	parent = root[0] if root else "All Territories"
	try:
		return frappe.get_doc(
			{"doctype": "Territory", "territory_name": city, "parent_territory": parent, "is_group": 0}
		).insert(ignore_permissions=True).name
	except Exception:
		return parent


def _grant_portal_access(
	mobile_no,
	full_name,
	customer_name,
	supplier_name,
	contact_name=None,
	address_name=None,
	business_type=None,
	password=None,
):
	email = _login_email_for(mobile_no)
	# A real login needs a real password - Frappe's User doctype requires an
	# email-shaped identifier for `name`, which is why the login id is this
	# synthetic address rather than the mobile number itself; login_with_mobile
	# below is what lets the *retailer* actually type their phone number.
	password = password or frappe.generate_hash(length=12)

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		user.new_password = password
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": full_name,
				"mobile_no": mobile_no,
				"user_type": "Website User",
				"send_welcome_email": 0,
				"new_password": password,
			}
		).insert(ignore_permissions=True)

	# Customer + Supplier are the universal portal roles (every party is both,
	# via Common Party Accounting). "distributor" additionally gets the
	# Distributor Admin *role* (not the Distributor Admin Role Profile, which
	# bundles cross-company native roles like Sales Manager/Accounts Manager -
	# too broad to hand an unverified self-registration automatically) so
	# they can immediately list their own items on the marketplace and manage
	# their own fulfillment doctypes, scoped entirely by the User Permission
	# set below.
	roles = ["Customer", "Supplier"]
	if business_type == "distributor" and frappe.db.exists("Role", "Distributor Admin"):
		roles.append("Distributor Admin")
	user.append_roles(*roles)

	if not user.role_profile_name and frappe.db.exists("Role Profile", "Tijarat - Retailer / Supplier Portal"):
		user.role_profile_name = "Tijarat - Retailer / Supplier Portal"

	user.save(ignore_permissions=True)

	# User Permission only *restricts which value* of a doctype this user can
	# touch - it grants nothing by itself. The base read/write grant for
	# Customer/Supplier/Contact/Address (roles Customer/Supplier) lives in
	# fixtures/custom_docperm.json; without both halves, native ERPNext flows
	# that read the party's own record (e.g. Sales Order pulling customer/
	# contact/address details on save) fail with a PermissionError even
	# though this looks, at a glance, like it should already work.
	scoped_records = [("Customer", customer_name), ("Supplier", supplier_name)]
	if contact_name:
		scoped_records.append(("Contact", contact_name))
	if address_name:
		scoped_records.append(("Address", address_name))

	for dt, name in scoped_records:
		doc = frappe.get_doc(dt, name)
		if hasattr(doc, "portal_users") and not any(pu.user == user.name for pu in doc.get("portal_users", [])):
			doc.append("portal_users", {"user": user.name})
			doc.save(ignore_permissions=True)

		if not frappe.db.exists(
			"User Permission", {"user": user.name, "allow": dt, "for_value": name}
		):
			frappe.get_doc(
				{
					"doctype": "User Permission",
					"user": user.name,
					"allow": dt,
					"for_value": name,
					"apply_to_all_doctypes": 1,
				}
			).insert(ignore_permissions=True)

	return user
