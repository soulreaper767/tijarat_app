// Copyright (c) 2026, Tijarat and contributors
// License: MIT

frappe.query_reports["Courier Performance"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "courier_partner",
			label: __("Courier Partner"),
			fieldtype: "Link",
			options: "Courier Partner",
		},
	],
};
