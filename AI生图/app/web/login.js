const form = document.querySelector("#loginForm");
const password = document.querySelector("#password");
const button = document.querySelector("#loginButton");
const error = document.querySelector("#loginError");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";
  button.disabled = true;
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: password.value }),
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.error || "登录失败");
    }
    window.location.replace("/");
  } catch (loginError) {
    error.textContent = loginError.message;
    password.select();
  } finally {
    button.disabled = false;
  }
});
