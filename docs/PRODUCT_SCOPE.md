# Product scope: what we’re building

This doc clarifies **what this project is** from a product perspective (single restaurant vs aggregator) and when **restaurant_id** matters.

---

## What we’re building: **single restaurant (hotel) ordering app**

- **One venue:** One hotel restaurant, one kitchen, one menu.
- **One set of products and prices:** The website shows one menu. No “choose a restaurant” or “different prices per restaurant.”
- **User flow:** Open site → see menu → add items → place order → food to your table (or pickup). No sign-in for now.
- **Not:** A Zomato/Swiggy-style **aggregator** (many restaurants, many menus, compare prices, reviews, etc.).

So from a **product view**: we’re building a **restaurant app** (or **hotel ordering app**), not a **food delivery aggregator**.

---

## Is `restaurant_id` necessary?

- **For a single restaurant / hotel app (what we have):**  
  From the **user’s perspective**, no — there’s only one place to order from. We still keep **`restaurant_id`** in the **data model** (e.g. `R1`) for:
  - Pipeline and analytics (same schema as the reference design).
  - Gold layer (e.g. daily_sales, restaurant_metrics by `restaurant_id`).
  - Future multi-outlet (e.g. same hotel, multiple restaurants: R1 dining, R2 pool bar) without changing the schema.

- **For a Zomato/Swiggy-like app:**  
  **Yes, essential.** You have **many restaurants**. Each order must say **which restaurant** it belongs to. You’d need:
  - **Multiple restaurants** in the system.
  - **Per-restaurant menus** and **per-restaurant prices** (same dish can have different prices at different places).
  - **Reviews/ratings** per restaurant (and optionally per dish).
  - **UI:** List/browse restaurants → select one → show **that** restaurant’s menu and prices → place order for that restaurant.

So: **restaurant_id is necessary for an aggregator; for a single restaurant it’s for data/analytics and future flexibility, not for the user.**

---

## Single restaurant vs aggregator (summary)

| Aspect | What we have (single restaurant / hotel) | Zomato/Swiggy-like (aggregator) |
|--------|------------------------------------------|----------------------------------|
| **Number of venues** | One (e.g. hotel restaurant) | Many restaurants |
| **Menu** | One menu, one set of items | One menu **per restaurant** |
| **Prices** | One price per item | **Different prices per restaurant** (and possibly reviews) |
| **User flow** | Open app → menu → order | Browse restaurants → pick restaurant → that restaurant’s menu → order |
| **restaurant_id in data** | One value (e.g. R1); mainly for pipeline/analytics | **Required** — every order tied to a restaurant |
| **Reviews/ratings** | Optional (one venue) | Typically **per restaurant** (and sometimes per dish) |

---

## If we later built a Zomato/Swiggy-like app

We’d add (conceptually):

1. **Restaurant list:** API/data for many restaurants (id, name, address, rating, etc.).
2. **Per-restaurant menu:** For each restaurant, a list of products with **that** restaurant’s name and price (and optionally ratings).
3. **UI:** Home → list of restaurants → tap one → load and show **that** restaurant’s menu and prices → cart and checkout for that restaurant (order payload includes that `restaurant_id`).
4. **Reviews/ratings:** Stored and displayed per restaurant (and optionally per dish).

The **current pipeline** (Bronze/Silver/Gold) already has `restaurant_id` in the order payload and in Gold (e.g. daily_sales, restaurant_metrics), so it can support multiple restaurants. The **current product** (website + one menu) is explicitly **single restaurant**.

---

**Bottom line:** We’re building a **restaurant app** (single hotel/restaurant), not a **food delivery aggregator**. `restaurant_id` is in the data for consistency and analytics; for this product it’s not something the user chooses. For an aggregator, we’d need multiple restaurants, per-restaurant menus/prices, and reviews — and then `restaurant_id` would be central to the product.
