"""Business semantics: the metric glossary DDL can't express.

Text-to-SQL fails most often on meaning, not syntax: "revenue" implies
completed orders only, "signed up" means newest signup date, etc. This
glossary is appended to the schema context so generation and correction
both see the business definitions.
"""

GLOSSARY = """\
BUSINESS GLOSSARY (apply these definitions):
- "revenue" / "sales" / "spent" / "sold": only orders with status='completed'
  count. Cancelled and returned orders are NEVER revenue unless the user
  explicitly asks about them (e.g. "lost to cancellations").
- "order value" / "order total": SUM(order_items.quantity * unit_price) per
  order, again restricted to status='completed' when aggregating revenue.
- "units sold": SUM(order_items.quantity) joined to orders with
  status='completed'.
- "revenue share": each category's completed-order revenue divided by total
  completed-order revenue.
- "newest" / "recent" customers: ORDER BY signed_up DESC.
- "who bought X" / "customers who": list DISTINCT customer names, not counts,
  unless the user asks for a count. Buyer-listing questions do NOT take the
  status='completed' filter — that restriction applies to revenue/units/
  order-value metrics only.
- Intent rule: a question that NAMES an entity type ("customers", "products",
  "orders") without an aggregation word ("how many", "total", "revenue",
  "average") asks you to LIST the entities — return entity rows, not counts
  or sums.
- Top-N entity questions ("top products", "top customer"): return the
  human-readable entity column plus the metric (e.g. name + revenue). Never
  include surrogate keys (product_id, customer_id) in the output.
- "share" / "share of" questions: return the category/entity, the absolute
  metric value, AND the share as a fraction or percentage column.
- "most recent" / "newest": include the date column being sorted on.
- Month labels for trends: use strftime('%Y-%m', order_date) so months are
  sortable strings like '2025-03'.
- Return only the columns the question asks for.
"""
