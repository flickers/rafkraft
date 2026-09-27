(function () {
  var button = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");

  function setOpen(open) {
    document.body.classList.toggle("nav-open", open);
    if (!button) return;
    button.setAttribute("aria-expanded", open ? "true" : "false");
    var label = button.querySelector(".nav-toggle-label");
    if (label) label.textContent = open ? "Loka" : "Valmynd";
  }

  if (button && nav) {
    button.addEventListener("click", function () {
      setOpen(!document.body.classList.contains("nav-open"));
    });
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) setOpen(false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth >= 960) setOpen(false);
    });
  }

  var form = document.getElementById("fyrirspurn");
  if (!form) return;

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var data = new FormData(form);
    var to = String(data.get("to") || "").trim();
    var name = String(data.get("name") || "").trim();
    var phone = String(data.get("phone") || "").trim();
    var email = String(data.get("email") || "").trim();
    var message = String(data.get("message") || "").trim();
    var status = document.getElementById("form-status");

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to)) {
      if (status) status.textContent = "Veldu viðtakanda.";
      return;
    }
    if (!message) {
      if (status) status.textContent = "Skrifaðu skilaboð.";
      return;
    }

    var subject = "Fyrirspurn" + (name ? " frá " + name : "");
    var lines = [];
    if (name) lines.push("Nafn: " + name);
    if (phone) lines.push("Sími: " + phone);
    if (email) lines.push("Netfang: " + email);
    lines.push("");
    lines.push(message);

    if (status) status.textContent = "Tölvupóstforritið opnast með skilaboðunum.";
    window.location.href =
      "mailto:" +
      to +
      "?subject=" +
      encodeURIComponent(subject) +
      "&body=" +
      encodeURIComponent(lines.join("\n"));
  });
})();
