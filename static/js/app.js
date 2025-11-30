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

  // DOM elements - Main View
  const mainView = document.getElementById('main-view');
  const levelEl = document.getElementById('level');
  const expEl = document.getElementById('exp');
  const rublesEl = document.getElementById('rubles');
  const dollarsEl = document.getElementById('dollars');
  const energyEl = document.getElementById('energy');
  const strengthEl = document.getElementById('strength');
  const toastEl = document.getElementById('toast');
  const actionButtons = document.querySelectorAll('.action-btn[data-action]');
  const openBattleBtn = document.getElementById('open-battle');

  // DOM elements - Battle View
  const battleView = document.getElementById('battle-view');
  const backToMainBtn = document.getElementById('back-to-main');
  const bossSelection = document.getElementById('boss-selection');
  const bossList = document.getElementById('boss-list');
  const activeBattle = document.getElementById('active-battle');
  const battleResult = document.getElementById('battle-result');
  const playerHpBar = document.getElementById('player-hp-bar');
  const playerHpText = document.getElementById('player-hp-text');
  const bossHpBar = document.getElementById('boss-hp-bar');
  const bossHpText = document.getElementById('boss-hp-text');
  const bossNameEl = document.getElementById('boss-name');
  const battleEnergyEl = document.getElementById('battle-energy');
  const turnCounterEl = document.getElementById('turn-counter');
  const moveButtonsEl = document.getElementById('move-buttons');
  const battleLogEl = document.getElementById('battle-log');
  const resultIcon = document.getElementById('result-icon');
  const resultTitle = document.getElementById('result-title');
  const rewardsList = document.getElementById('rewards-list');
  const claimRewardsBtn = document.getElementById('claim-rewards');

  // State
  let currentUser = null;
  let battleConfig = { moves: {}, bosses: {} };
  let selectedBossId = null;
  let currentBattle = null;

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
    currentUser = user;
    
    levelEl.textContent = user.level || 1;
    expEl.textContent = user.exp || 0;
    rublesEl.textContent = (user.money_rub || 0) + ' ₽';
    dollarsEl.textContent = '$' + (user.money_usd || 0);
    energyEl.textContent = (user.energy || 0) + '/' + (user.max_energy || 100);
    strengthEl.textContent = user.strength || 0;
    
    // Update battle energy display if in battle
    if (battleEnergyEl) {
      battleEnergyEl.textContent = user.energy || 0;
    }
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
        
        // Check if user has active battle
        if (data.user && data.user.battle && data.user.battle.active) {
          currentBattle = data.user.battle;
          showBattleView();
          showActiveBattle();
          renderBattleState(currentBattle);
        }
        
        return data.user;
      })
      .catch(function(err) {
        console.error('Fetch user error:', err);
        showToast('Ошибка загрузки данных', 'error');
        return null;
      });
  }

  // Fetch battle config
  function fetchBattleConfig() {
    return fetch('/battle/config')
      .then(function(res) {
        return res.json();
      })
      .then(function(data) {
        if (data.ok) {
          battleConfig = {
            moves: data.moves || {},
            bosses: data.bosses || {}
          };
          renderBossList();
          renderMoveButtons();
        }
        return battleConfig;
      })
      .catch(function(err) {
        console.error('Fetch battle config error:', err);
        return battleConfig;
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
        
        const messages = {
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

  // ==================== BATTLE FUNCTIONS ====================

  // Show battle view
  function showBattleView() {
    mainView.classList.add('hidden');
    battleView.classList.remove('hidden');
  }

  // Show main view
  function showMainView() {
    battleView.classList.add('hidden');
    mainView.classList.remove('hidden');
    // Reset battle UI
    showBossSelection();
    selectedBossId = null;
  }

  // Show boss selection
  function showBossSelection() {
    bossSelection.classList.remove('hidden');
    activeBattle.classList.add('hidden');
    battleResult.classList.add('hidden');
  }

  // Show active battle
  function showActiveBattle() {
    bossSelection.classList.add('hidden');
    activeBattle.classList.remove('hidden');
    battleResult.classList.add('hidden');
  }

  // Show battle result
  function showBattleResult(won, rewards) {
    bossSelection.classList.add('hidden');
    activeBattle.classList.add('hidden');
    battleResult.classList.remove('hidden');
    
    if (won) {
      resultIcon.textContent = '🎉';
      resultTitle.textContent = 'Победа!';
      battleResult.classList.remove('defeat');
      battleResult.classList.add('victory');
    } else {
      resultIcon.textContent = '💀';
      resultTitle.textContent = 'Поражение...';
      battleResult.classList.remove('victory');
      battleResult.classList.add('defeat');
    }
    
    // Render rewards
    rewardsList.innerHTML = '';
    if (won && rewards) {
      if (rewards.rub > 0) {
        const rubItem = document.createElement('div');
        rubItem.className = 'reward-item';
        rubItem.innerHTML = '<span>💰 Рубли</span><span>+' + rewards.rub + ' ₽</span>';
        rewardsList.appendChild(rubItem);
      }
      if (rewards.usd > 0) {
        const usdItem = document.createElement('div');
        usdItem.className = 'reward-item';
        usdItem.innerHTML = '<span>💵 Доллары</span><span>+$' + rewards.usd + '</span>';
        rewardsList.appendChild(usdItem);
      }
      if (rewards.exp > 0) {
        const expItem = document.createElement('div');
        expItem.className = 'reward-item';
        expItem.innerHTML = '<span>✨ Опыт</span><span>+' + rewards.exp + '</span>';
        rewardsList.appendChild(expItem);
      }
      if (rewards.items && rewards.items.length > 0) {
        rewards.items.forEach(function(itemId) {
          const itemEl = document.createElement('div');
          itemEl.className = 'reward-item';
          itemEl.innerHTML = '<span>🎁 Предмет</span><span>' + itemId + '</span>';
          rewardsList.appendChild(itemEl);
        });
      }
    } else if (!won) {
      const noRewardItem = document.createElement('div');
      noRewardItem.className = 'reward-item';
      noRewardItem.innerHTML = '<span>😔</span><span>Без награды</span>';
      rewardsList.appendChild(noRewardItem);
    }
  }

  // Render boss list
  function renderBossList() {
    bossList.innerHTML = '';
    
    const bossKeys = Object.keys(battleConfig.bosses);
    bossKeys.forEach(function(bossId) {
      const boss = battleConfig.bosses[bossId];
      const card = document.createElement('div');
      card.className = 'boss-card';
      card.dataset.bossId = bossId;
      
      card.innerHTML = 
        '<div class="boss-card-header">' +
          '<span class="boss-card-name">👹 ' + (boss.name_ru || boss.name) + '</span>' +
          '<span class="boss-card-level">Ур. ' + boss.level + '</span>' +
        '</div>' +
        '<div class="boss-card-stats">' +
          '<span>❤️ HP: ' + boss.hp + '</span>' +
          '<span>⚔️ Урон: ' + boss.damage_range[0] + '-' + boss.damage_range[1] + '</span>' +
        '</div>';
      
      card.addEventListener('click', function() {
        // Remove selected from all
        const allCards = bossList.querySelectorAll('.boss-card');
        allCards.forEach(function(c) { c.classList.remove('selected'); });
        // Select this one
        card.classList.add('selected');
        selectedBossId = bossId;
      });
      
      bossList.appendChild(card);
    });
    
    // Add start battle button
    const startBtn = document.createElement('button');
    startBtn.className = 'action-btn start-battle-btn';
    startBtn.textContent = '⚔️ Начать бой';
    startBtn.addEventListener('click', function() {
      if (!selectedBossId) {
        showToast('Выбери противника!', 'error');
        return;
      }
      startBattle(selectedBossId);
    });
    bossList.appendChild(startBtn);
  }

  // Render move buttons
  function renderMoveButtons() {
    moveButtonsEl.innerHTML = '';
    
    const moveKeys = Object.keys(battleConfig.moves);
    moveKeys.forEach(function(moveKey) {
      const move = battleConfig.moves[moveKey];
      const btn = document.createElement('button');
      btn.className = 'move-btn ' + moveKey;
      btn.dataset.move = moveKey;
      
      btn.innerHTML = 
        (move.name_ru || move.name) + 
        '<small>⚡' + move.energy_cost + ' | 💥' + move.base_damage + '</small>';
      
      btn.addEventListener('click', function() {
        performMove(moveKey);
      });
      
      moveButtonsEl.appendChild(btn);
    });
  }

  // Update move button states
  function updateMoveButtonStates() {
    const moveButtons = moveButtonsEl.querySelectorAll('.move-btn');
    moveButtons.forEach(function(btn) {
      const moveKey = btn.dataset.move;
      const move = battleConfig.moves[moveKey];
      if (move && currentUser) {
        btn.disabled = currentUser.energy < move.energy_cost || (currentBattle && currentBattle.finished);
      }
    });
  }

  // Render battle state
  function renderBattleState(battle) {
    if (!battle) return;
    
    currentBattle = battle;
    const boss = battleConfig.bosses[battle.boss_id] || {};
    
    // Update boss name
    bossNameEl.textContent = '👹 ' + (boss.name_ru || boss.name || 'Босс');
    
    // Update HP bars
    const playerHpPercent = Math.max(0, (battle.player_hp / battle.player_max_hp) * 100);
    const bossHpPercent = Math.max(0, (battle.boss_hp / battle.boss_max_hp) * 100);
    
    playerHpBar.style.width = playerHpPercent + '%';
    bossHpBar.style.width = bossHpPercent + '%';
    
    playerHpText.textContent = Math.max(0, battle.player_hp) + '/' + battle.player_max_hp;
    bossHpText.textContent = Math.max(0, battle.boss_hp) + '/' + battle.boss_max_hp;
    
    // Update turn counter
    turnCounterEl.textContent = battle.turn || 0;
    
    // Update battle log
    battleLogEl.innerHTML = '';
    const log = battle.log || [];
    log.forEach(function(entry) {
      const logEntry = document.createElement('div');
      logEntry.className = 'log-entry';
      logEntry.textContent = entry;
      battleLogEl.appendChild(logEntry);
    });
    // Scroll to bottom
    battleLogEl.scrollTop = battleLogEl.scrollHeight;
    
    // Update move button states
    updateMoveButtonStates();
  }

  // Start battle
  function startBattle(bossId) {
    if (!userId) {
      showToast('Ошибка: user_id не найден', 'error');
      return;
    }

    setLoading(true);

    fetch('/battle/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, boss_id: bossId })
    })
      .then(function(res) {
        return res.json();
      })
      .then(function(data) {
        if (!data.ok) {
          showToast('❌ ' + (data.error || 'Ошибка начала боя'), 'error');
          return;
        }
        
        updateStats(data.user);
        currentBattle = data.battle;
        showActiveBattle();
        renderBattleState(data.battle);
        showToast('⚔️ Бой начался!', 'success');
      })
      .catch(function(err) {
        console.error('Start battle error:', err);
        showToast('❌ Ошибка подключения', 'error');
      })
      .finally(function() {
        setLoading(false);
      });
  }

  // Perform move
  function performMove(moveKey) {
    if (!userId || !currentBattle) {
      showToast('Ошибка: нет активного боя', 'error');
      return;
    }

    setLoading(true);

    fetch('/battle/turn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, move: moveKey })
    })
      .then(function(res) {
        return res.json();
      })
      .then(function(data) {
        if (!data.ok) {
          showToast('❌ ' + (data.error || 'Ошибка хода'), 'error');
          return;
        }
        
        updateStats(data.user);
        renderBattleState(data.battle);
        
        if (data.finished) {
          // Show result after a short delay
          setTimeout(function() {
            showBattleResult(data.player_won, null);
          }, 1000);
        }
      })
      .catch(function(err) {
        console.error('Perform move error:', err);
        showToast('❌ Ошибка подключения', 'error');
      })
      .finally(function() {
        setLoading(false);
      });
  }

  // End battle and claim rewards
  function endBattle() {
    if (!userId) {
      showToast('Ошибка: user_id не найден', 'error');
      return;
    }

    setLoading(true);

    fetch('/battle/end', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId })
    })
      .then(function(res) {
        return res.json();
      })
      .then(function(data) {
        if (!data.ok) {
          showToast('❌ ' + (data.error || 'Ошибка завершения боя'), 'error');
          return;
        }
        
        updateStats(data.user);
        currentBattle = null;
        
        if (data.player_won) {
          showToast('🎉 Награды получены!', 'success');
        }
        
        // Go back to main view
        showMainView();
      })
      .catch(function(err) {
        console.error('End battle error:', err);
        showToast('❌ Ошибка подключения', 'error');
      })
      .finally(function() {
        setLoading(false);
      });
  }

  // ==================== EVENT LISTENERS ====================

  // Attach event listeners to action buttons
  actionButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      const action = this.getAttribute('data-action');
      if (action) {
        performAction(action);
      }
    });
  });

  // Open battle button
  if (openBattleBtn) {
    openBattleBtn.addEventListener('click', function() {
      showBattleView();
    });
  }

  // Back to main button
  if (backToMainBtn) {
    backToMainBtn.addEventListener('click', function() {
      if (currentBattle && currentBattle.active && !currentBattle.finished) {
        showToast('Нельзя выйти во время боя!', 'error');
        return;
      }
      showMainView();
    });
  }

  // Claim rewards button
  if (claimRewardsBtn) {
    claimRewardsBtn.addEventListener('click', function() {
      endBattle();
    });
  }

  // ==================== INITIALIZATION ====================

  // Initial load
  if (userId) {
    setLoading(true);
    Promise.all([fetchUser(), fetchBattleConfig()])
      .finally(function() {
        setLoading(false);
      });
  } else {
    showToast('Откройте игру через Telegram', 'error');
  }
})();
