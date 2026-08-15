// Copyright (c) 2026, Tijarat and contributors
// License: MIT

frappe.query_reports["Lifecycle Funnel"] = {
	filters: [
		{
			fieldname: "territory",
			label: __("Territory"),
			fieldtype: "Link",
			options: "Territory",
		},
	],
};
