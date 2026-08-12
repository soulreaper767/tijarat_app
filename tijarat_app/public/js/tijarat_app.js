// tijarat_app: Desk-side helpers.
// Adds a "Compare Suppliers" button on the Item form for any item flagged
// as a marketplace item, showing every active Item Listing for it
// side-by-side - useful for staff checking pricing without leaving the
// Item form to go dig through the Item Listing list view manually.

frappe.ui.form.on("Item", {
	refresh(frm) {
		if (!frm.doc.is_marketplace_item || frm.is_new()) return;

		frm.add_custom_button(__("Compare Suppliers"), () => {
			frappe.call({
				method: "tijarat_app.api.marketplace.get_item_listings",
				args: { item_code: frm.doc.name },
				callback: (r) => {
					if (!r.message || !r.message.length) {
						frappe.msgprint(__("No active listings found for this item yet."));
						return;
					}
					showComparisonDialog(frm.doc.item_name || frm.doc.name, r.message);
				},
			});
		});
	},
});

function showComparisonDialog(itemLabel, listings) {
	const rows = listings
		.map(
			(l) => `
			<tr>
				<td>${frappe.utils.escape_html(l.supplier_name || l.supplier)}</td>
				<td>${frappe.utils.escape_html(l.territory || "-")}</td>
				<td>${format_currency(l.rate, l.currency)}</td>
				<td>${frappe.utils.escape_html(l.stock_status || "-")}</td>
			</tr>`
		)
		.join("");

	const html = `
		<table class="table table-bordered">
			<thead>
				<tr>
					<th>${__("Supplier")}</th>
					<th>${__("Territory")}</th>
					<th>${__("Rate")}</th>
					<th>${__("Stock Status")}</th>
				</tr>
			</thead>
			<tbody>${rows}</tbody>
		</table>`;

	const dialog = new frappe.ui.Dialog({
		title: __("Suppliers for {0}", [itemLabel]),
		fields: [{ fieldtype: "HTML", fieldname: "comparison_html", options: html }],
	});
	dialog.show();
}
