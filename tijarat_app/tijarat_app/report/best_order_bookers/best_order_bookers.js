// Copyright (c) 2026, Tijarat and contributors
// License: MIT

frappe.query_reports["Best Order Bookers"] = {
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
			fieldname: "booking_channel",
			label: __("Booking Channel"),
			fieldtype: "Select",
			options: "\nSelf\nAssisted\nOnline",
		},
	],
};
