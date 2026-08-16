app_name = "tijarat_app"
app_title = "Tijarat App"
app_publisher = "Sibyl Technologies"
app_description = "Core Tijarat platform: parties, marketplace listings, territory/route management, order booking, commissions, fulfillment, and warehousing-as-a-service."
app_email = "hello@tijaratapp.com"
app_license = "MIT"

required_apps = ["erpnext"]

app_include_js = "/assets/tijarat_app/js/tijarat_app.js"

# --- Fixtures ---------------------------------------------------------
# Without this list, the JSON files sitting in fixtures/ are inert - this
# is what actually tells `bench install-app` / `bench migrate` to read and
# apply them.
fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [
			[
				"dt",
				"in",
				[
					"Contact",
					"Customer",
					"Supplier",
					"Territory",
					"Item",
					"Item Group",
					"Sales Order",
					"Sales Order Item",
					"Sales Invoice",
					"Warehouse",
				],
			]
		],
	},
	{
		"doctype": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"Territory Manager",
					"Field Officer",
					"Distributor Admin",
					"Warehouse Manager",
					"Rider",
					"Support Agent",
					"Customer Service",
					"Sales Coordinator",
				],
			]
		],
	},
	{
		"doctype": "Role Profile",
		"filters": [
			[
				"name",
				"like",
				"Tijarat - %",
			]
		],
	},
	{
		"doctype": "Custom DocPerm",
		"filters": [
			[
				"role",
				"in",
				[
					"Rider",
					"Support Agent",
					"Territory Manager",
					"Distributor Admin",
					"Customer",
					"Supplier",
					"Customer Service",
					"Field Officer",
					"Sales Coordinator",
				],
			]
		],
	},
	{
		"doctype": "Workflow",
		"filters": [
			[
				"name",
				"in",
				["Territory Exception Approval", "Support Ticket Resolution", "Trade Scheme Approval"],
			]
		],
	},
	{
		"doctype": "Property Setter",
		"filters": [
			[
				"doc_type",
				"in",
				["Sales Order", "Delivery Note"],
			]
		],
	},
]

after_install = "tijarat_app.install.after_install"

# --- Document Events ----------------------------------------------------
doc_events = {
	"Sales Order": {
		"validate": [
			"tijarat_app.api.territory.validate_territory_lock",
			"tijarat_app.api.pricing.apply_service_package_charges",
		],
		"on_submit": [
			"tijarat_app.api.lifecycle.mark_productive_customer",
			"tijarat_app.api.invoicing.auto_invoice_and_assign",
		],
	},
	"Purchase Order": {
		"on_submit": "tijarat_app.api.lifecycle.mark_productive_supplier",
	},
	"Item": {
		"validate": "tijarat_app.api.catalog.apply_item_group_attributes",
	},
	"Sales Invoice": {
		"validate": "tijarat_app.api.pricing.validate_mrp_ceiling",
		"on_submit": "tijarat_app.api.commission.accrue_commission",
	},
	"Payment Entry": {
		"on_submit": "tijarat_app.api.commission.settle_referral_payable_on_payment",
	},
	"Delivery Note": {
		"on_submit": "tijarat_app.api.dispatch.auto_assign_courier",
	},
}

# --- Scheduled Jobs -------------------------------------------------------
scheduler_events = {
	"daily": [
		"tijarat_app.api.automation.generate_journey_plan_visits",
		"tijarat_app.api.automation.create_low_stock_purchase_orders",
		"tijarat_app.api.automation.flag_overdue_payments",
	],
	"cron": {
		# End of day, after the day's visits have had a chance to happen.
		"0 21 * * *": ["tijarat_app.api.automation.check_pjp_compliance"],
	},
	"hourly": [
		"tijarat_app.api.automation.escalate_overdue_support_tickets",
	],
	"monthly": [
		"tijarat_app.api.automation.recompute_tijarat_scores",
	],
}
