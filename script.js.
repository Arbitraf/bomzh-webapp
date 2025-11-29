// Публичный адрес твоего API (через ngrok)
const API_BASE = "https://jennifer-inviolate-unmentally.ngrok-free.dev";

const tg = window.Telegram?.WebApp;
if (tg) tg.expand();

const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
const digBtn = document.getElementById("digBtn");

// Берём реальный user_id из Telegram WebApp
let userId = 0;
if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
  userId = tg.initDataUnsafe.user.id;
} else {
  // если просто открыли страницу в браузере
  userId = 12345;
}

async function callAction(action) {
  try {
    digBtn.disabled = true;

    const res = await fetch(`${API_BASE}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, action })
    });

    const data = await res.json();

    if (data.error) {
      logEl.textContent = "Ошибка: " + data.error;
      return;
    }

    const u = data.user;
    statusEl.textContent =
      `Уровень: ${u.level} (опыт: ${u.exp})\n` +
      `Деньги: ${u.money} руб\n` +
      `Энергия: ${u.energy}/${u.max_energy}`;

    logEl.textContent = "Действие: " + action;
  } catch (e) {
    logEl.textContent = "Сервер недоступен";
  } finally {
    digBtn.disabled = false;
  }
}

digBtn.addEventListener("click", () => {
  callAction("dig_trash");
});

// при первом открытии сразу обновим статус
callAction("collect_bottles");
