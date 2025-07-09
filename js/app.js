// js/app.js


document.addEventListener('DOMContentLoaded', async () => {
  // 1) Обработка редактирования заказа из order_data
  const params = new URLSearchParams(window.location.search);
  if (params.has('order_data')) {
    const data = JSON.parse(atob(params.get('order_data')));
    console.log('Редактируем заказ:', data);

    // Заполняем корзину из data.items
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

    // Заполняем форму доставки
    const del = data.delivery_info;
    document.getElementById('input-name').value       = del.name;
    document.getElementById('input-phone').value      = del.phone;
    document.getElementById('input-street').value     = del.street;
    document.getElementById('input-house').value      = del.house;
    document.getElementById('input-entrance').value   = del.entrance;
    document.getElementById('input-floor').value      = del.floor;
    document.getElementById('input-apartment').value  = del.apartment;
    document.getElementById('input-intercom').value   = del.intercom;
    document.getElementById('input-persons').value    = del.numPersons;
    if (del.paymentType === 'cash') {
      document.getElementById('pay-cash').checked = true;
    } else {
      document.getElementById('pay-card').checked = true;
    }
    toggleChange();
    document.getElementById('input-change').value    = del.changeFrom  || '';
    document.getElementById('textarea-comment').value = del.comment     || '';

    // Загружаем меню и показываем форму редактирования
    await fetchMenu();
    showCart();
    showOrderForm();
    return;
  }

  // 2) Обычная инициализация
  await loadModalTemplate();
  const tg = window.Telegram.WebApp;
  tg.expand();
  loadCart();
  bindCartButton();
  bindPaymentToggle();
  await fetchMenu();
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
  const info = {
    name: document.getElementById('input-name').value.trim(),
    phone: document.getElementById('input-phone').value.trim(),
    street: document.getElementById('input-street').value.trim(),
    house: document.getElementById('input-house').value.trim(),
    entrance: document.getElementById('input-entrance').value.trim(),
    floor: document.getElementById('input-floor').value.trim(),
    apartment: document.getElementById('input-apartment').value.trim(),
    intercom: document.getElementById('input-intercom').value.trim(),
    numPersons: document.getElementById('input-persons').value,
    paymentType: document.querySelector('input[name="payment"]:checked').value,
    changeFrom: document.getElementById('input-change').value.trim() || null,
    comment: document.getElementById('textarea-comment').value.trim()
  };
  if (!info.name || !info.phone || !info.street || !info.house) {
    return alert('Заполните все обязательные поля.');
  }
  if (!cart.length) {
    return alert('Корзина пуста.');
  }

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

  window.Telegram.WebApp.sendData(JSON.stringify(order));
  localStorage.removeItem('cartData');
  window.Telegram.WebApp.close();
}
