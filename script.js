// API адрес твоего приложения на Railway
const API_BASE = "https://bomzh-webapp-production.up.railway. app";

const tg = window. Telegram?. WebApp;
if (tg) {
  tg.expand();
  tg.setHeaderColor("#1b1b1b");
}

const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
const digBtn = document.getElementById("digBtn");

// Получаем user_id из Telegram
let userId = 0;
if (tg && tg.initDataUnsafe && tg.initDataUnsafe. user) {
  userId = tg. initDataUnsafe.user. id;
} else {
  userId = 12345; // для локального тестирования
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
      logEl.textContent = "❌ Ошибка: " + data.error;
      return;
    }

    const u = data.user;
    statusEl.textContent =
      `📊 Уровень: ${u.level} (опыт: ${u.exp})\n` +
      `💵 Рубли: ${u.money_rub} | 💵 Доллары: ${u.money_usd}\n` +
      `⚡ Энергия: ${u.energy}/${u.max_energy}\n` +
      `💪 Сила: ${u.strength} | 😔 Жалкость: ${u.pity} | 😎 Крутость: ${u.coolness}`;

    logEl.textContent = "✅ Действие выполнено: " + action;
  } catch (e) {
    logEl.textContent = "❌ Ошибка подключения: " + e.message;
    console.error(e);
  } finally {
    digBtn. disabled = false;
  }
}

digBtn.addEventListener("click", () => {
  callAction("dig_trash");
});

// При загрузке обновляем статус
callAction("collect_bottles");
