(() => {
  const timer = setInterval(() => {
    if (location.hostname !== "auth.afip.gob.ar") return;

    const cuit = document.querySelector(
      'input[aria-label="CUIT/CUIL"], input[type="number"]',
    );
    const next = [...document.querySelectorAll('button, input[type="submit"]')].find(
      (node) => (node.innerText || node.value || "").trim() === "Siguiente",
    );

    if (cuit && cuit.value.replace(/\D/g, "").length === 11 && next) {
      clearInterval(timer);
      next.click();
    }
  }, 50);
})();
