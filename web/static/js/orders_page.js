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
  function prepNote(status) {
    var s = (status || "").toLowerCase();
    if (s === "done" || s === "completed") return "Ready";
    if (s === "cancelled" || s === "canceled") return "—";
    return "Est. 15–20 min";
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
  function loadYourOrders() {
    var loading = document.getElementById("your-orders-loading");
    var table = document.getElementById("your-orders-table");
    var tbody = document.getElementById("your-orders-tbody");
    var empty = document.getElementById("your-orders-empty");
    if (!loading || !table || !tbody || !empty) return;
    loading.style.display = "block";
    table.style.display = "none";
    empty.style.display = "none";
    fetch("/api/orders", { credentials: "same-origin" })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        loading.style.display = "none";
        if (!Array.isArray(data) || data.length === 0) {
          empty.style.display = "block";
          return;
        }
        table.style.display = "table";
        tbody.innerHTML = data.map(function (o) {
          var qty = o.total_quantity != null ? o.total_quantity : (o.items_list && o.items_list.length ? o.items_list.reduce(function (s, i) { return s + (i.quantity || 0); }, 0) : "—");
          var itemsHtml = renderItemsList(o.items_list, o.items_summary);
          return "<tr><td>" + (o.order_id || "—") + "</td><td>" + itemsHtml + "</td><td class=\"td-num\">" + qty + "</td><td class=\"td-num\">$" + (o.total_amount != null ? Number(o.total_amount).toFixed(2) : "0.00") + "</td><td>" + statusBadge(o.status) + "</td><td>" + formatOrderTime(o.created_at) + "</td><td>" + prepNote(o.status) + "</td></tr>";
        }).join("");
      })
      .catch(function () {
        loading.style.display = "none";
        empty.style.display = "block";
        if (empty) empty.innerHTML = "Could not load orders. <a href=\"/\">Home</a>";
      });
  }
  var btnRefresh = document.getElementById("btn-refresh-orders");
  if (btnRefresh) btnRefresh.addEventListener("click", loadYourOrders);
  var btnLogin = document.getElementById("btn-open-login");
  if (btnLogin) btnLogin.addEventListener("click", function () { window.location.href = "/?login=1"; });
  loadYourOrders();
})();
