// Apply the saved/system theme before first paint, without inline scripts or styles.
(() => {
  let saved;
  try { saved = localStorage.getItem("mcp-stack-theme"); } catch { /* Storage is optional. */ }
  const theme = saved === "dark" || saved === "light" ? saved : matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = theme;
})();
