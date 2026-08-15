// Copyright (c) 2026, Tijarat and contributors
// License: MIT

frappe.query_reports["Top Customers"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory",
		},
		{
			fieldname: "sort_by",
			label: __("Rank By"),
			fieldtype: "Select",
			options: "Revenue\nQuantity\nOrder Count",
			default: "Revenue",
		},
	],
};
