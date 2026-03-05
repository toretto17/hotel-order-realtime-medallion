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
        thankyouOrderId.textContent = data.order_id || "";
        statusValue.textContent = "Preparation in progress";
        setThankyouGreeting(lines);
        thankyouMessage.textContent = data.message || "Your order has been received.";
        orderView.classList.add("hidden");
        thankyouView.classList.remove("hidden");
        var card = thankyouView.querySelector(".thankyou-card-animate");
        if (card) {
          card.classList.remove("thankyou-just-showed");
          void card.offsetWidth;
          card.classList.add("thankyou-just-showed");
        }
        thankyouView.scrollIntoView({ behavior: "smooth" });
        triggerOrderCelebration();
      })
      .catch(function (err) {
        alert("Order failed: " + err.message);
      })
      .finally(function () {
        btnSubmit.disabled = false;
        btnSubmit.textContent = "Place order";
      });
  });

  function setThankyouGreeting(lines) {
    var greetingEl = document.getElementById("thankyou-greeting");
    if (!greetingEl) return;
    greetingEl.innerHTML = "";
    greetingEl.classList.remove("gratitude-hands", "greeting-with-hands");
    var categories = [];
    if (lines && lines.length) {
      categories = lines.map(function (l) { return (l.category || "").toLowerCase(); }).filter(Boolean);
      categories = categories.filter(function (c, i, a) { return a.indexOf(c) === i; });
    }
    greetingEl.removeAttribute("aria-hidden");
    if (categories.length === 1) {
      var c = categories[0];
      var handsHtml = "<div class=\"hands-join-anim\" aria-hidden=\"true\"><span class=\"hand hand-left\">🙏</span><span class=\"hand hand-right\">🙏</span></div>";
      if (c === "south_indian") {
        greetingEl.classList.add("greeting-with-hands");
        greetingEl.innerHTML = handsHtml + "<span class=\"greeting-text\">Vanakkam! Big Namastey.</span>";
      } else if (c === "gujarati") {
        greetingEl.classList.add("greeting-with-hands");
        greetingEl.innerHTML = handsHtml + "<span class=\"greeting-text\">Jai Jinendra.</span>";
      } else if (c === "north_indian") {
        greetingEl.classList.add("gratitude-hands", "greeting-with-hands");
        greetingEl.innerHTML = handsHtml + "<span class=\"greeting-text\">Dhanyawaad</span>";
      } else if (c === "beverage") {
        greetingEl.innerHTML = "<span class=\"greeting-text\">Ab pine ma maza Le! &#128521;&#128521;</span>";
      } else {
        greetingEl.setAttribute("aria-hidden", "true");
      }
    } else {
      greetingEl.setAttribute("aria-hidden", "true");
    }
  }

  btnOrderAgain.addEventListener("click", function () {
    var card = thankyouView.querySelector(".thankyou-card-animate");
    if (card) card.classList.remove("thankyou-just-showed");
    var greetingEl = document.getElementById("thankyou-greeting");
    if (greetingEl) { greetingEl.innerHTML = ""; greetingEl.setAttribute("aria-hidden", "true"); greetingEl.classList.remove("gratitude-hands", "greeting-with-hands"); }
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

  // ——— Order success celebration (hearts / candy-style floating animation)
  function triggerOrderCelebration() {
    var container = document.getElementById("celebration-container");
    if (!container) return;
    container.innerHTML = "";
    container.classList.remove("celebration-done");
    var shapes = ["♥", "❤", "✦", "•", "◆"];
    var count = 35;
    for (var i = 0; i < count; i++) {
      var el = document.createElement("span");
      el.className = "celebration-particle celebration-particle-" + (i % 3);
      el.setAttribute("aria-hidden", "true");
      el.textContent = shapes[i % shapes.length];
      el.style.left = Math.random() * 100 + "%";
      el.style.animationDelay = Math.random() * 0.6 + "s";
      el.style.setProperty("--drift", (Math.random() - 0.5) * 40 + "px");
      container.appendChild(el);
    }
    container.classList.add("celebration-active");
    setTimeout(function () {
      container.classList.remove("celebration-active");
      container.classList.add("celebration-done");
      setTimeout(function () { container.innerHTML = ""; }, 600);
    }, 3200);
  }

  // Hero "Order now" → scroll to menu (no nav tabs; Your orders is at /orders, All orders at /admin/orders)
  var heroOrderNow = document.getElementById("hero-order-now");
  if (heroOrderNow) {
    heroOrderNow.addEventListener("click", function (e) {
      e.preventDefault();
      var menuEl = document.getElementById("menu");
      if (menuEl) menuEl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  // ——— Login modal (Guest vs Staff / Admin) ———
  var loginModal = document.getElementById("login-modal");
  function openLoginModal() {
    if (loginModal) {
      loginModal.classList.add("is-open");
      loginModal.setAttribute("aria-hidden", "false");
      var err = document.getElementById("login-modal-error");
      if (err) { err.style.display = "none"; err.textContent = ""; }
      var pwd = document.getElementById("login-modal-password");
      if (pwd) pwd.value = "";
    }
  }
  function closeLoginModal() {
    if (loginModal) {
      loginModal.classList.remove("is-open");
      loginModal.setAttribute("aria-hidden", "true");
    }
  }
  ["btn-open-login-top", "btn-open-login-footer"].forEach(function (id) {
    var btn = document.getElementById(id);
    if (btn) btn.addEventListener("click", openLoginModal);
  });
  var btnCloseLogin = document.getElementById("btn-close-login-modal");
  if (btnCloseLogin) btnCloseLogin.addEventListener("click", closeLoginModal);
  if (loginModal) loginModal.addEventListener("click", function (e) { if (e.target === loginModal) closeLoginModal(); });
  var btnContinueGuest = document.getElementById("btn-continue-guest");
  if (btnContinueGuest) btnContinueGuest.addEventListener("click", function () { closeLoginModal(); });

  var loginModalAdminForm = document.getElementById("login-modal-admin-form");
  var loginModalPassword = document.getElementById("login-modal-password");
  var loginModalError = document.getElementById("login-modal-error");
  if (loginModalAdminForm) {
    loginModalAdminForm.addEventListener("submit", function (e) {
      e.preventDefault();
      if (loginModalError) { loginModalError.style.display = "none"; loginModalError.textContent = ""; }
      fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ password: loginModalPassword ? loginModalPassword.value : "" }),
      })
        .then(function (res) { return res.json().then(function (d) { return { ok: res.ok, data: d }; }); })
        .then(function (r) {
          if (r.ok) {
            closeLoginModal();
            if (loginModalPassword) loginModalPassword.value = "";
            window.location.href = "/admin/orders";
          } else {
            if (loginModalError) {
              loginModalError.textContent = r.data.error || "Invalid password";
              loginModalError.style.display = "block";
            }
          }
        })
        .catch(function () {
          if (loginModalError) { loginModalError.textContent = "Request failed"; loginModalError.style.display = "block"; }
        });
    });
  }

  // Open login modal when arriving with ?login=1 or ?admin=login (e.g. from /orders or /admin/orders)
  if (location.search.indexOf("login=1") !== -1 || location.search.indexOf("admin=login") !== -1) {
    openLoginModal();
  }

  // ——— Testimonials: scrollable + auto-scroll one after another ———
  var testimonialTrack = document.getElementById("testimonial-track");
  var testimonialWrap = testimonialTrack ? testimonialTrack.closest(".testimonial-scroll-wrap") : null;
  var testimonialDots = document.getElementById("testimonial-dots");
  var cards = testimonialTrack ? testimonialTrack.querySelectorAll(".testimonial-card-item") : [];
  var autoScrollInterval = null;
  var currentIndex = 0;

  function updateDots() {
    if (!testimonialDots || !cards.length) return;
    testimonialDots.innerHTML = "";
    cards.forEach(function (_, i) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "testimonial-dot" + (i === currentIndex ? " active" : "");
      btn.setAttribute("aria-label", "Go to testimonial " + (i + 1));
      btn.addEventListener("click", function () {
        currentIndex = i;
        scrollToTestimonial(i);
        updateDotsActive();
      });
      testimonialDots.appendChild(btn);
    });
  }
  function updateDotsActive() {
    if (!testimonialDots) return;
    testimonialDots.querySelectorAll(".testimonial-dot").forEach(function (dot, i) {
      dot.classList.toggle("active", i === currentIndex);
    });
  }
  function scrollToTestimonial(index) {
    if (!testimonialWrap || !cards[index]) return;
    var card = cards[index];
    var left = card.offsetLeft - (testimonialWrap.offsetWidth / 2) + (card.offsetWidth / 2);
    testimonialWrap.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
  }
  function advanceTestimonial() {
    currentIndex = (currentIndex + 1) % cards.length;
    scrollToTestimonial(currentIndex);
    updateDotsActive();
  }
  function startAutoScroll() {
    if (autoScrollInterval) return;
    autoScrollInterval = setInterval(advanceTestimonial, 5000);
  }
  function stopAutoScroll() {
    if (autoScrollInterval) {
      clearInterval(autoScrollInterval);
      autoScrollInterval = null;
    }
  }
  if (testimonialWrap && cards.length) {
    updateDots();
    var testimonialsSection = document.getElementById("testimonials");
    if (testimonialsSection && typeof IntersectionObserver !== "undefined") {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) startAutoScroll();
          else stopAutoScroll();
        });
      }, { threshold: 0.2 });
      io.observe(testimonialsSection);
    } else {
      startAutoScroll();
    }
    testimonialWrap.addEventListener("scroll", function () {
      var wrap = testimonialWrap;
      var mid = wrap.scrollLeft + wrap.offsetWidth / 2;
      for (var i = 0; i < cards.length; i++) {
        var c = cards[i];
        if (c.offsetLeft + c.offsetWidth / 2 >= mid - 20) { currentIndex = i; updateDotsActive(); break; }
      }
    });
  }

})();
