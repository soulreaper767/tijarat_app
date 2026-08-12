# Tijarat App

The core Tijarat platform, built as a Frappe/ERPNext v16 app. Covers the
full custom layer designed across this project: dual customer/supplier
registration, multi-supplier marketplace listings, territory and route
management, order booking (self, assisted, or online), commissions and
referrals, fulfillment/courier integration, and warehousing-as-a-service.

Installs everything automatically via `bench install-app` — no manual
DocType creation, no manual field setup, no manual role creation.

---

## What Gets Installed Automatically

- **10 custom DocTypes**: Item Listing, Route, Route Stop, Journey Plan
  Visit, Territory Exception Request, Courier Partner, Courier Booking,
  Service Package, Service Package Item, Referral Code
- **1 Workflow**: Territory Exception approval (Pending → Approved/Rejected)
- **41 custom fields** across Contact, Customer, Supplier, Territory, Item,
  Sales Order, Sales Order Item, Sales Invoice, and Warehouse
- **6 custom Roles**: Territory Manager, Field Officer, Distributor Admin,
  Warehouse Manager, Rider, Support Agent
- **Tijarat workspace** — sidebar entry point with shortcuts to every
  custom DocType above
- **4 Customer Groups** seeded (Retailer, Distributor, Wholesaler,
  Manufacturer / Importer)
- **Common Party Accounting enabled** — the native mechanism that lets one
  business be both a Customer and a Supplier with automatically netted
  ledgers

## Install

```bash
cd ~/backend/frappe-bench
bench get-app https://github.com/YOUR_ORG/tijarat_app.git
bench --site tijarat.local install-app tijarat_app
bench --site tijarat.local list-apps
sudo supervisorctl restart all
```

`tijarat_app` depends on `erpnext` (declared via `required_apps` in
hooks.py) — install order doesn't matter, bench resolves it, but ERPNext
must already be installed on the site for the Customer/Supplier/Territory
customizations to have something to attach to.

---

## Architecture Decisions Worth Understanding

### Why a custom "Item Listing" doctype for multi-supplier pricing

This was researched, not assumed: ERPNext's native `Item Price` doctype
supports an optional Supplier field, but it's built for procurement cost
comparison (which supplier is cheapest to *buy from*), not a customer-facing
"pick which supplier to buy from" marketplace view with per-territory
availability. There's an open GitHub feature request (Sept 2025) asking
ERPNext core to add proper multi-vendor marketplace support — as of this
build, it doesn't exist natively. `Item Listing` fills that specific,
confirmed gap: one record per (Item, Supplier, Territory, Rate)
combination. `api/marketplace.py`'s `get_item_listings()` is what the
frontend calls to show the price-comparison view.

### Why the party model still uses Party Link, not a new "party" doctype

Same reasoning as the earlier ERPNext Simplified Native design: Party Link
+ Common Party Accounting are native, and `register_trade_party()` in
`api/registration.py` wires them together with a shared Contact and one
portal User carrying both Customer and Supplier roles — one account, no
upfront role decision, exactly as scoped throughout this project.

### Why territory lock and MRP checks are Python hooks, not Workflow states

Both are `validate` hooks (synchronous, blocking) rather than anything
async or Workflow-driven — consistent with the project's standing rule:
anything that must block a transaction before it can complete stays native
server-side logic, never routed through automation that could fail or lag.

### Why commissions use native Sales Partner/Sales Person, not a new doctype

ERPNext already has commission-rate fields built into Sales Partner and
Sales Person specifically for this purpose. `Referral Code` is a thin
wrapper on top — a shareable code that resolves to one of those two native
records — rather than reinventing commission tracking from scratch.

---

## Known Risk Areas — Please Verify These Specifically

Same honesty as the `custom_design` app: some of what's below was written
against Frappe/ERPNext v16's documented schema without a live instance to
test every code path against, so a few things need your confirmation once
installed.

1. **The Tijarat workspace** (sidebar entry point) — generated
   programmatically and self-validated for internal JSON consistency, but
   v16's actual sidebar rendering is new. If it looks wrong, every DocType
   is still fully reachable via the awesomebar search regardless.

2. **`insert_after` values in `custom_field.json`** reference native field
   names (e.g. `customer_primary_contact` on Customer, `is_purchase_item`
   on Item) based on standard ERPNext field naming. If any of these don't
   exist on your exact v16 build, Frappe's Custom Field creation falls back
   to appending the field at the end of the form rather than erroring out —
   so worst case is a field showing up in a slightly different position,
   not a failed install. Check the Design Settings-style sections in
   Customer, Supplier, Item, and Warehouse forms after install to confirm
   they landed somewhere sensible.

3. **`api/commission.py`'s Journal Entry posting** assumes your Company has
   both a default income account and default receivable account
   configured. If not, the commission accrual is skipped with a logged
   error (`frappe.log_error`) rather than blocking the Sales Invoice
   submission — check the Error Log after your first real invoice if you
   don't see a Journal Entry appear.

4. **`api/pricing.py`'s service package charges** append rows to the Sales
   Order's `taxes` child table using what I believe are the standard
   Sales Taxes and Charges fieldnames (`charge_type`, `account_head`,
   `description`, `tax_amount`) — this is long-stable ERPNext accounting
   structure, low risk, but it's the one place to check first if a Service
   Package doesn't visibly add its charges.

5. **`PLATFORM_COMMISSION_RATE = 0.02` in `api/commission.py`** is an
   illustrative placeholder (2%), not a number pulled from your actual fee
   agreements — the Complete Business Model document's fee tables are the
   real source; update this constant to match before relying on the
   accrual figures for anything financial.

Test each of these with one real record before building further on top of
them, same discipline as everywhere else in this project.

---

## Using the Marketplace API

```python
# Get all active listings for an item, in a customer's territory, cheapest first
GET/POST tijarat_app.api.marketplace.get_item_listings
  item_code=<Item>, customer=<Customer>  (or territory=<Territory> directly)

# Book an order - identical call whether it's self-service or Field-Officer-assisted
POST tijarat_app.api.marketplace.book_order
  customer=<Customer>
  lines=[{"item_listing": "LST-...", "qty": 5}, ...]
  booking_channel="Self" | "Assisted" | "Online"
```

## Requesting a Territory Exception

```python
POST tijarat_app.api.territory.request_exception
  customer=<Customer>
  requested_supplier=<Supplier>
  supplier_territory=<Territory>
  reason="..."
```
Creates a `Territory Exception Request` in `Pending` state; a Territory
Manager approves or rejects it via the Workflow (visible as action buttons
on the document itself in the Desk).

## Uninstall

```bash
bench --site tijarat.local uninstall-app tijarat_app
```
