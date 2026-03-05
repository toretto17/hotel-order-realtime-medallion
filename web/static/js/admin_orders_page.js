(function () {
  function formatOrderTime(iso) {
    if (!iso) return "—";
    try {
      var d = new Date(iso);
      return isNaN(d.getTime()) ? iso : d.toLocaleString();
    } catch (_) { return iso; }
  }
  function statusBadge(status) {
    var s = (status || "").toLowerCase();
    var label = s || "pending";
    return "<span class=\"status-badge " + label + "\">" + label + "</span>";
  }
  function renderItemsList(itemsList, fallbackSummary) {
    if (itemsList && itemsList.length > 0) {
      var lis = itemsList.map(function (i) {
        return "<li><span class=\"item-name\">" + (i.name || "—") + "</span><span class=\"item-qty\">× " + (i.quantity || 0) + "</span></li>";
      }).join("");
      return "<span class=\"item-count-badge\">" + itemsList.length + " item(s)</span><ul class=\"items-list\">" + lis + "</ul>";
    }
    return fallbackSummary || "—";
  }
  function loadAdminOrders() {
    var loading = document.getElementById("admin-orders-loading");
    var table = document.getElementById("admin-orders-table");
    var tbody = document.getElementById("admin-orders-tbody");
    var empty = document.getElementById("admin-orders-empty");
    if (!loading || !table || !tbody || !empty) return;
    loading.style.display = "block";
    table.style.display = "none";
    empty.style.display = "none";
    fetch("/api/admin/orders", { credentials: "same-origin" })
      .then(function (res) {
        if (!res.ok) { window.location.href = "/?admin=login"; return Promise.reject(); }
        return res.json();
      })
      .then(function (data) {
        loading.style.display = "none";
        if (!Array.isArray(data) || data.length === 0) {
          empty.style.display = "block";
          return;
        }
        table.style.display = "table";
        tbody.innerHTML = data.map(function (o) {
          var doneBtn = (o.status || "").toLowerCase() === "done" || (o.status || "").toLowerCase() === "completed"
            ? "<span class=\"status-done-label\">Done</span>"
            : "<button type=\"button\" class=\"btn btn-mark-done\" data-order-id=\"" + (o.order_id || "") + "\">Mark done</button>";
          var qty = o.total_quantity != null ? o.total_quantity : (o.items_list && o.items_list.length ? o.items_list.reduce(function (s, i) { return s + (i.quantity || 0); }, 0) : "—");
          var itemsHtml = renderItemsList(o.items_list, o.items_summary);
          return "<tr><td>" + (o.order_id || "—") + "</td><td>" + (o.customer_id || "—") + "</td><td>" + itemsHtml + "</td><td class=\"td-num\">" + qty + "</td><td class=\"td-num\">$" + (o.total_amount != null ? Number(o.total_amount).toFixed(2) : "0.00") + "</td><td>" + statusBadge(o.status) + "</td><td>" + formatOrderTime(o.created_at) + "</td><td>" + doneBtn + "</td></tr>";
        }).join("");
        tbody.querySelectorAll(".btn-mark-done").forEach(function (btn) {
          btn.addEventListener("click", function () {
            var id = btn.getAttribute("data-order-id");
            if (!id) return;
            btn.disabled = true;
            btn.textContent = "…";
            fetch("/api/admin/orders/" + encodeURIComponent(id) + "/status", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              credentials: "same-origin",
              body: JSON.stringify({ status: "done" }),
            })
              .then(function (res) { return res.json(); })
              .then(function (d) {
                if (d.success) loadAdminOrders();
                else { btn.disabled = false; btn.textContent = "Mark done"; }
              })
              .catch(function () { btn.disabled = false; btn.textContent = "Mark done"; });
          });
        });
      })
      .catch(function () {
        loading.style.display = "none";
        window.location.href = "/?admin=login";
      });
  }
  var btnRefresh = document.getElementById("btn-refresh-admin-orders");
  if (btnRefresh) btnRefresh.addEventListener("click", loadAdminOrders);
  var btnLogout = document.getElementById("btn-admin-logout");
  if (btnLogout) {
    btnLogout.addEventListener("click", function (e) {
      e.preventDefault();
      fetch("/api/admin/logout", { method: "POST", credentials: "same-origin" })
        .then(function () { window.location.href = "/"; });
    });
  }
  loadAdminOrders();
})();
