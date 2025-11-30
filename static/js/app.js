(function() {
  'use strict';

  // Initialize Telegram WebApp
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.expand();
    tg.setHeaderColor('#1b1b1b');
    tg.setBackgroundColor('#111');
  }

  // Get user_id from query string
  function getUserId() {
    const params = new URLSearchParams(window.location.search);
    const queryUserId = params.get('user_id');
    if (queryUserId) {
      return queryUserId;
    }
    // Fallback: try to get from Telegram WebApp
    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
      return String(tg.initDataUnsafe.user.id);
    }
    return null;
  }

  const userId = getUserId();

  // DOM elements
  const levelEl = document.getElementById('level');
  const expEl = document.getElementById('exp');
  const rublesEl = document.getElementById('rubles');
  const dollarsEl = document.getElementById('dollars');
  const energyEl = document.getElementById('energy');
  const strengthEl = document.getElementById('strength');
  const toastEl = document.getElementById('toast');
  const actionButtons = document.querySelectorAll('.action-btn');

  // Show toast notification
  function showToast(message, type) {
    toastEl.textContent = message;
    toastEl.className = 'toast ' + (type || '');
    
    setTimeout(function() {
      toastEl.classList.add('hidden');
    }, 2500);
  }

  // Update stats display
  function updateStats(user) {
    if (!user) return;
    
    levelEl.textContent = user.level || 1;
    expEl.textContent = user.exp || 0;
    rublesEl.textContent = (user.money_rub || 0) + ' ₽';
    dollarsEl.textContent = '$' + (user.money_usd || 0);
    energyEl.textContent = (user.energy || 0) + '/' + (user.max_energy || 100);
    strengthEl.textContent = user.strength || 0;
  }

  // Set loading state
  function setLoading(isLoading) {
    actionButtons.forEach(function(btn) {
      btn.disabled = isLoading;
    });
    document.body.classList.toggle('loading', isLoading);
  }

  // Fetch user data
  function fetchUser() {
    if (!userId) {
      showToast('Ошибка: user_id не найден', 'error');
      return Promise.reject(new Error('No user_id'));
    }

    return fetch('/user?user_id=' + encodeURIComponent(userId))
      .then(function(res) {
        return res.json();
      })
      .then(function(data) {
        if (data.error) {
          showToast('Ошибка: ' + data.error, 'error');
          return null;
        }
        updateStats(data.user);
        return data.user;
      })
      .catch(function(err) {
        console.error('Fetch user error:', err);
        showToast('Ошибка загрузки данных', 'error');
        return null;
      });
  }

  // Perform action
  function performAction(actionName) {
    if (!userId) {
      showToast('Ошибка: user_id не найден', 'error');
      return;
    }

    setLoading(true);

    fetch('/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, action: actionName })
    })
      .then(function(res) {
        return res.json();
      })
      .then(function(data) {
        if (data.error) {
          showToast('❌ ' + data.error, 'error');
          return;
        }
        updateStats(data.user);
        
        var messages = {
          'dig_trash': '✅ Накопал мусора! +50₽',
          'collect_bottles': '✅ Собрал бутылки! +$0.5',
          'train_strength': '✅ Потренировался! +1 сила'
        };
        showToast(messages[actionName] || '✅ Действие выполнено', 'success');
      })
      .catch(function(err) {
        console.error('Action error:', err);
        showToast('❌ Ошибка подключения', 'error');
      })
      .finally(function() {
        setLoading(false);
      });
  }

  // Attach event listeners to action buttons
  actionButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      var action = this.getAttribute('data-action');
      if (action) {
        performAction(action);
      }
    });
  });

  // Initial load
  if (userId) {
    setLoading(true);
    fetchUser().finally(function() {
      setLoading(false);
    });
  } else {
    showToast('Откройте игру через Telegram', 'error');
  }
})();
