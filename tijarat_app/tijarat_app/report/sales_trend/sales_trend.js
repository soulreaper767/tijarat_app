// Copyright (c) 2026, Tijarat and contributors
// License: MIT

frappe.query_reports["Sales Trend"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -6),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "period",
			label: __("Group By"),
			fieldtype: "Select",
			options: "Daily\nWeekly\nMonthly",
			default: "Monthly",
		},
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory",
		},
	],
};
