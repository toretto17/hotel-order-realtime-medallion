(function () {
  const orderView = document.getElementById("order-view");
  const thankyouView = document.getElementById("thankyou-view");
  const orderForm = document.getElementById("order-form");
  const cartCount = document.getElementById("cart-count");
  const cartTotal = document.getElementById("cart-total");
  const btnSubmit = document.getElementById("btn-submit");
  const btnOrderAgain = document.getElementById("btn-order-again");
  const thankyouMessage = document.getElementById("thankyou-message");
  const thankyouOrderId = document.getElementById("thankyou-order-id");
  const statusValue = document.getElementById("status-value");

  // quantity by item_id (from data attributes on +/- buttons)
  const quantities = {};

  function getItemData(btn) {
    return {
      item_id: btn.dataset.itemId,
      name: btn.dataset.name,
      category: btn.dataset.category,
      unit_price: parseFloat(btn.dataset.unitPrice),
    };
  }

  function setQty(itemId, delta) {
    const prev = quantities[itemId] || 0;
    const next = Math.max(0, Math.min(20, prev + delta));
    quantities[itemId] = next;
    const span = document.getElementById("qty-" + itemId);
    if (span) span.textContent = next;
    updateCart();
  }

  function getOrderLines() {
    const lines = [];
    const menuData = {};
    document.querySelectorAll(".btn-qty-plus").forEach(function (btn) {
      const d = getItemData(btn);
      menuData[d.item_id] = d;
    });
    Object.keys(quantities).forEach(function (itemId) {
      const q = quantities[itemId] || 0;
      if (q > 0 && menuData[itemId]) {
        lines.push({
          item_id: menuData[itemId].item_id,
          name: menuData[itemId].name,
          category: menuData[itemId].category,
          quantity: q,
          unit_price: menuData[itemId].unit_price,
        });
      }
    });
    return lines;
  }

  function updateCart() {
    const lines = getOrderLines();
    const count = lines.reduce(function (acc, l) { return acc + l.quantity; }, 0);
    const total = lines.reduce(function (acc, l) {
      return acc + l.quantity * l.unit_price;
    }, 0);
    cartCount.textContent = count;
    cartTotal.textContent = total.toFixed(2);
    btnSubmit.disabled = count === 0;
  }

  document.querySelectorAll(".btn-qty-plus").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setQty(btn.dataset.itemId, 1);
    });
  });
  document.querySelectorAll(".btn-qty-minus").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setQty(btn.dataset.itemId, -1);
    });
  });

  orderForm.addEventListener("submit", function (e) {
    e.preventDefault();
    const lines = getOrderLines();
    if (lines.length === 0) return;
    btnSubmit.disabled = true;
    btnSubmit.textContent = "Sending…";

    fetch("/api/order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: lines }),
    })
      .then(function (res) {
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
          return res.text().then(function (text) {
            throw new Error("Server error. Check connection and try again.");
          });
        }
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || "Order failed");
          return data;
        });
      })
      .then(function (data) {
        thankyouMessage.textContent = data.message || "Thank you! Your order has been received.";
        thankyouOrderId.textContent = data.order_id || "";
        statusValue.textContent = "Preparation in progress";
        orderView.classList.add("hidden");
        thankyouView.classList.remove("hidden");
        thankyouView.scrollIntoView({ behavior: "smooth" });
      })
      .catch(function (err) {
        alert("Order failed: " + err.message);
      })
      .finally(function () {
        btnSubmit.disabled = false;
        btnSubmit.textContent = "Place order";
      });
  });

  btnOrderAgain.addEventListener("click", function () {
    Object.keys(quantities).forEach(function (id) {
      quantities[id] = 0;
      const span = document.getElementById("qty-" + id);
      if (span) span.textContent = "0";
    });
    updateCart();
    thankyouView.classList.add("hidden");
    orderView.classList.remove("hidden");
    document.getElementById("menu").scrollIntoView({ behavior: "smooth" });
  });

  updateCart();
})();
