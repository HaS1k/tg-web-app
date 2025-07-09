// js/app.js

// Утилита для корректной декодировки URL-safe Base64 с UTF-8
function b64DecodeUnicode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  const pad = str.length % 4;
  if (pad) str += '='.repeat(4 - pad);
  return decodeURIComponent(
    atob(str)
      .split('')
      .map(c => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
      .join('')
  );
}

document.addEventListener('DOMContentLoaded', async () => {
  // 1) Всегда грузим шаблон модалки и расширяем WebApp
  await loadModalTemplate();
  const tg = window.Telegram.WebApp;
  tg.expand();

  // 2) Привязываем кнопку корзины и переключатель «Сдача с»
  bindCartButton();
  bindPaymentToggle();

  // 3) Читаем параметры URL — может быть menu_data или order_data
  const params = new URLSearchParams(window.location.search);
  let isEditing = false;
  if (params.has('order_data')) {
    isEditing = true;
    // декодируем безопасный Base64 в JSON
    const raw = params.get('order_data');
    const data = JSON.parse(b64DecodeUnicode(raw));

    // заполняем корзину
    cart = data.items.map(it => ({
      key: `${it.externalId}|${(it.modifiers||[]).map(m => m.id).join(',')}`,
      externalId: it.externalId,
      name: it.name,
      price: it.price,
      quantity: it.quantity,
      modifiers: it.modifiers || []
    }));
    saveCart();
    updateCartCount();

    // заполняем форму доставки
    const d = data.delivery_info;
    document.getElementById('input-name').value       = d.name;
    document.getElementById('input-phone').value      = d.phone;
    document.getElementById('input-street').value     = d.street;
    document.getElementById('input-house').value      = d.house;
    document.getElementById('input-entrance').value   = d.entrance;
    document.getElementById('input-floor').value      = d.floor;
    document.getElementById('input-apartment').value  = d.apartment;
    document.getElementById('input-intercom').value   = d.intercom;
    document.getElementById('input-persons').value    = d.numPersons;
    if (d.paymentType === 'cash') {
      document.getElementById('pay-cash').checked = true;
    } else {
      document.getElementById('pay-card').checked = true;
    }
    toggleChange();
    document.getElementById('input-change').value    = d.changeFrom  || '';
    document.getElementById('textarea-comment').value = d.comment     || '';
  }

  // 4) Загружаем меню и рендерим категории/товары
  loadCart();
  await fetchMenu();

  // 5) Если это редактирование — показываем корзину и форму
  if (isEditing) {
    showCart();
    showOrderForm();
  }
});




async function loadModalTemplate() {
  const html = await fetch('components/product-modal.html').then(r => r.text());
  document.getElementById('product-modal-container').innerHTML = html;
  document.getElementById('modal-add-btn')
    .addEventListener('click', onModalAdd);
}

const API_BASE = "http://127.0.0.1:8000";
let cart = [], categories = {}, currentItem = null;

// Кнопка корзины
function bindCartButton() {
  document.getElementById('cart-button')
    .addEventListener('click', showCart);
}

// Переключатель «Сдача с»
function bindPaymentToggle() {
  document.getElementById('pay-cash').addEventListener('change', toggleChange);
  document.getElementById('pay-card').addEventListener('change', toggleChange);
}
function toggleChange() {
  document.getElementById('change-container').style.display =
    document.getElementById('pay-cash').checked ? 'block' : 'none';
}

// Загрузка меню
async function fetchMenu() {
  try {
    const resp = await fetch(`${API_BASE}/menu`, { mode: 'cors' });
    if (!resp.ok) throw new Error(resp.status);
    categories = await resp.json();
    renderCategories();
    const first = Object.keys(categories)[0];
    if (first) showItems(first);
  } catch (e) {
    console.error(e);
    alert('Не удалось загрузить меню');
  }
}

// Рендер категорий
function renderCategories() {
  const ctr = document.getElementById('categories');
  ctr.innerHTML = '';
  for (let cid in categories) {
    const btn = document.createElement('button');
    btn.className = 'btn coffee-btn me-2 mb-2';
    btn.textContent = categories[cid].name;
    btn.addEventListener('click', () => showItems(cid));
    ctr.append(btn);
  }
}

// Показ товаров и навешивание клика на «Подробнее»
function showItems(cid) {
  const ctr = document.getElementById('items');
  ctr.innerHTML = '';
  categories[cid].items.forEach(item => {
    const col = document.createElement('div');
    col.className = 'col-12 col-sm-6 col-md-4';
    col.innerHTML = `
      <div class="product-card">
        <img src="${item.image||'images/placeholder.png'}"
             class="product-image" alt="${item.name}"
             onerror="this.src='images/placeholder.png'" />
        <div class="p-2">
          <h6>${item.name}</h6>
          <p>${item.price} ₽</p>
          <button class="btn coffee-btn details-btn">Подробнее</button>
        </div>
      </div>`;
    col.querySelector('.details-btn')
       .addEventListener('click', () => openModal(cid, item));
    ctr.append(col);
  });
}

// Открытие модалки
function openModal(categoryId, item) {
  currentItem = item;
  document.getElementById('modal-title').textContent = item.name;
  document.getElementById('modal-image').src = item.image||'images/placeholder.png';
  document.getElementById('modal-desc').innerHTML = item.description||'Описание недоступно';
  renderModifiers(item.modifiers||[]);
  bootstrap.Modal.getOrCreateInstance(
    document.getElementById('productModal')
  ).show();
}

// Рендер модификаторов (пропускаем первый, как делали ранее)
function renderModifiers(mods) {
  const ctr = document.getElementById('modal-modifiers');
  ctr.innerHTML = '';
  if (!mods || mods.length <= 1) {
    ctr.style.display = 'none';
    return;
  }
  ctr.style.display = 'block';

  // Пропускаем первый элемент
  const toRender = mods.slice(1);
  const allGroups = toRender.every(g => Array.isArray(g.options));

  if (!allGroups) {
    // плоский список опций
    const wrapper = document.createElement('div');
    toRender.forEach(opt => {
      const id = `mod-${currentItem.id}-${opt.id}`;
      wrapper.innerHTML += `
        <div class="form-check">
          <input class="form-check-input"
                 type="radio"
                 name="mod-${currentItem.id}"
                 id="${id}"
                 value="${opt.id}">
          <label class="form-check-label" for="${id}">
            ${opt.name} (+${opt.cost}₽)
          </label>
        </div>`;
    });
    ctr.append(wrapper);
  } else {
    // набор групп
    toRender.forEach(group => {
      const wrapper = document.createElement('div');
      wrapper.innerHTML = `<p class="mb-1"><strong>${group.name}</strong></p>`;
      group.options.forEach(opt => {
        const id = `mod-${group.id}-${opt.id}`;
        wrapper.innerHTML += `
          <div class="form-check">
            <input class="form-check-input"
                   type="${group.type==='Single'?'radio':'checkbox'}"
                   name="mod-${group.id}"
                   id="${id}"
                   value="${opt.id}">
            <label class="form-check-label" for="${id}">
              ${opt.name} (+${opt.cost}₽)
            </label>
          </div>`;
      });
      ctr.append(wrapper);
    });
  }
}

// «Добавить в корзину» из модалки — сохраним полные данные модификаторов
function onModalAdd() {
  const selected = [];
  (currentItem.modifiers||[]).slice(1).forEach(group => {
    // если группа с options
    if (Array.isArray(group.options)) {
      group.options.forEach(opt => {
        const inp = document.getElementById(`mod-${group.id}-${opt.id}`);
        if (inp && inp.checked) {
          selected.push({ 
            group: group.name, 
            id: opt.id, 
            name: opt.name, 
            cost: opt.cost 
          });
        }
      });
    } else {
      // плоский список
      const inp = document.getElementById(`mod-${currentItem.id}-${group.id}`);
      if (inp && inp.checked) {
        selected.push({ 
          group: null, 
          id: group.id, 
          name: group.name, 
          cost: group.cost 
        });
      }
    }
  });

  addToCart(currentItem, selected);
  bootstrap.Modal.getInstance(
    document.getElementById('productModal')
  ).hide();
}

// Добавление в cart — разные позиции по разным модификаторам, пустые стекаются
function addToCart(item, mods=[]) {
  const modKey = mods.map(m => m.id).join(',');
  const key = `${item.externalId||item.id}|${modKey}`;
  let ci = cart.find(i => i.key === key);
  if (ci) {
    ci.quantity++;
  } else {
    cart.push({
      key,
      externalId: item.externalId||item.id,
      name: item.name,
      price: item.price,
      quantity: 1,
      modifiers: mods
    });
  }
  saveCart();
  updateCartCount();
}

// Работа с локальным хранилищем
function loadCart() {
  cart = JSON.parse(localStorage.getItem('cartData')||'[]');
  updateCartCount();
}
function saveCart() {
  localStorage.setItem('cartData', JSON.stringify(cart));
}
function updateCartCount() {
  document.getElementById('cart-count').textContent =
    cart.reduce((sum, i) => sum + i.quantity, 0);
}

// Переходы между экранами
function showCart() {
  document.getElementById('main-content').classList.add('d-none');
  document.getElementById('order-form').classList.add('d-none');
  document.getElementById('cart-content').classList.remove('d-none');
  renderCartItems();
}
function backToMain() {
  document.getElementById('cart-content').classList.add('d-none');
  document.getElementById('order-form').classList.add('d-none');
  document.getElementById('main-content').classList.remove('d-none');
}
function showOrderForm() {
  document.getElementById('cart-content').classList.add('d-none');
  document.getElementById('main-content').classList.add('d-none');
  document.getElementById('order-form').classList.remove('d-none');
}
function backToCart() {
  document.getElementById('order-form').classList.add('d-none');
  document.getElementById('cart-content').classList.remove('d-none');
}

// Рендер корзины с отображением модификаторов
function renderCartItems() {
  const ctr = document.getElementById('cart-items');
  ctr.innerHTML = '';
  if (!cart.length) {
    ctr.innerHTML = '<p>Корзина пуста</p>';
    return;
  }
  let total = 0;
  cart.forEach((item, idx) => {
    total += item.price * item.quantity;
    const modsHtml = item.modifiers.length
      ? `<div class="cart-mods"><small>${item.modifiers.map(m => m.name).join(', ')}</small></div>`
      : '';
    const div = document.createElement('div');
    div.className = 'cart-item mb-3';
    div.innerHTML = `
      <div class="d-flex justify-content-between align-items-start">
        <div>
          <strong>${item.name}</strong>
          ${modsHtml}
        </div>
        <div class="d-flex align-items-center">
          <button class="btn btn-sm btn-outline-secondary me-2" onclick="changeQty(${idx}, -1)">−</button>
          <span>${item.quantity}</span>
          <button class="btn btn-sm btn-outline-secondary ms-2" onclick="changeQty(${idx}, 1)">+</button>
        </div>
        <div>
          <span>${item.price * item.quantity}₽</span>
          <button class="btn btn-sm btn-danger ms-3" onclick="removeFromCart(${idx})">×</button>
        </div>
      </div>`;
    ctr.append(div);
  });
  ctr.insertAdjacentHTML('beforeend',
    `<div class="cart-total mt-3"><strong>Итого: ${total}₽</strong></div>`
  );
}

function changeQty(i, delta) {
  cart[i].quantity += delta;
  if (cart[i].quantity < 1) cart.splice(i, 1);
  saveCart(); renderCartItems(); updateCartCount();
}
function removeFromCart(i) {
  cart.splice(i, 1);
  saveCart(); renderCartItems(); updateCartCount();
}
// Отправка заказа в бота (модификаторы идут вместе с item.modifiers)
function submitOrder() {
  // 0) Проверяем, что функция вообще вызывается
  console.log("🔥 submitOrder fired");

  // 1) Собираем информацию о доставке
  const info = {
    name:       document.getElementById('input-name').value.trim(),
    phone:      document.getElementById('input-phone').value.trim(),
    street:     document.getElementById('input-street').value.trim(),
    house:      document.getElementById('input-house').value.trim(),
    entrance:   document.getElementById('input-entrance').value.trim(),
    floor:      document.getElementById('input-floor').value.trim(),
    apartment:  document.getElementById('input-apartment').value.trim(),
    intercom:   document.getElementById('input-intercom').value.trim(),
    numPersons: document.getElementById('input-persons').value,
    paymentType: document.querySelector('input[name="payment"]:checked').value,
    changeFrom: document.getElementById('input-change').value.trim() || null,
    comment:    document.getElementById('textarea-comment').value.trim()
  };
  console.log("   delivery_info:", info);

  // 2) Валидация
  if (!info.name || !info.phone || !info.street || !info.house) {
    alert('Пожалуйста, заполните все обязательные поля.');
    return;
  }
  if (!cart.length) {
    alert('Ваша корзина пуста.');
    return;
  }

  // 3) Формируем итоговый объект
  const order = {
    items: cart.map(i => ({
      externalId: i.externalId,
      name:       i.name,
      price:      i.price,
      quantity:   i.quantity,
      modifiers:  i.modifiers    // массив {group, id, name, cost}
    })),
    delivery_info: info
  };
  console.log("   order payload:", order);

  // 4) Отправка в Telegram Bot
  console.log("   calling sendData...");
  window.Telegram.WebApp.sendData(JSON.stringify(order));
  console.log("   sendData called");

  // 5) Очистка и закрытие
  localStorage.removeItem('cartData');
  window.Telegram.WebApp.close();
  console.log("   WebApp.closed");
}
