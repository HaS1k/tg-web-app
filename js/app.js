// js/app.js
// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

// Базовые переменные
const API_BASE = "http://127.0.0.1:8000";
let cart = [];
let categories = {};
let currentItem = null;

// Загрузка шаблона модалки
fetch('components/product-modal.html')
  .then(r => r.text())
  .then(html => {
    document.getElementById('product-modal-container').innerHTML = html;
    initModalLogic();
  });

// При полной загрузке документа
document.addEventListener('DOMContentLoaded', () => {
  loadCart();
  bindCartButton();
  bindPaymentToggle();
  fetchMenu();
});

// Привязка кнопки корзины
function bindCartButton() {
  const cartBtn = document.getElementById('cart-button');
  if (cartBtn) cartBtn.addEventListener('click', showCart);
}

// Переключение поля «Сдача с»
function bindPaymentToggle() {
  document.getElementById('pay-cash').addEventListener('change', toggleChange);
  document.getElementById('pay-card').addEventListener('change', toggleChange);
}
function toggleChange() {
  document.getElementById('change-container').style.display =
    document.getElementById('pay-cash').checked ? 'block' : 'none';
}

// Загрузка меню с бэкенда
async function fetchMenu() {
  try {
    const resp = await fetch(`${API_BASE}/menu`, { mode: 'cors' });
    if (!resp.ok) throw new Error(`Ошибка ${resp.status}`);
    const data = await resp.json();
    categories = data;
    renderCategories();
    const first = Object.keys(categories)[0];
    if (first) showItems(first);
  } catch (error) {
    console.error('Ошибка fetchMenu:', error);
    alert('Не удалось загрузить меню с сервера');
  }
}

// Рисуем категории
function renderCategories() {
  const ctr = document.getElementById('categories');
  ctr.innerHTML = '';
  for (let cid in categories) {
    const btn = document.createElement('button');
    btn.className = 'btn coffee-btn me-2 mb-2';
    btn.innerText = categories[cid].name;
    btn.addEventListener('click', () => showItems(cid));
    ctr.appendChild(btn);
  }
}

// Показ товаров категории и навешивание обработчика «Подробнее»
function showItems(cid) {
  const ctr = document.getElementById('items');
  ctr.innerHTML = '';
  categories[cid].items.forEach(item => {
    const col = document.createElement('div');
    col.className = 'col-12 col-sm-6 col-md-4';
    col.innerHTML = `
      <div class="product-card">
        <img src="${item.image || 'images/placeholder.png'}"
             class="product-image" alt="${item.name}"
             onerror="this.src='images/placeholder.png'" />
        <div class="p-2">
          <h6>${item.name}</h6>
          <p>${item.price} ₽</p>
          <button class="btn coffee-btn details-btn">
            Подробнее
          </button>
        </div>
      </div>
    `;
    // навешиваем обработчик с правильными параметрами
    col.querySelector('.details-btn').addEventListener('click', () => {
      openModal(cid, item.externalId || item.id);
    });
    ctr.appendChild(col);
  });
}

// Открываем модалку
function openModal(categoryId, extId) {
  const item = categories[categoryId].items
    .find(i => String(i.externalId || i.id) === String(extId));
  if (!item) return;
  currentItem = item;
  document.getElementById('modal-title').innerText = item.name;
  document.getElementById('modal-image').src = item.image || 'images/placeholder.png';
  document.getElementById('modal-desc').innerHTML = item.description || 'Описание недоступно';
  renderModifiers(item.modifiers || []);
  new bootstrap.Modal('#productModal').show();
}

// Рендерим модификаторы
function renderModifiers(mods) {
  const ctr = document.getElementById('modal-modifiers');
  ctr.innerHTML = '';
  if (mods.length === 0) {
    ctr.style.display = 'none';
    return;
  }
  ctr.style.display = 'block';
  mods.forEach(group => {
    const div = document.createElement('div');
    div.innerHTML = `<p class="mb-1"><strong>${group.name}</strong></p>`;
    group.options.forEach(opt => {
      const id = `mod-${group.id}-${opt.id}`;
      div.innerHTML += `
        <div class="form-check">
          <input class="form-check-input"
                 type="${group.type === 'Single' ? 'radio' : 'checkbox'}"
                 name="mod-${group.id}"
                 id="${id}"
                 value="${opt.id}">
          <label class="form-check-label" for="${id}">
            ${opt.name} (+${opt.cost}₽)
          </label>
        </div>
      `;
    });
    ctr.appendChild(div);
  });
}

// Логика кнопки «Добавить в корзину» в модалке
function initModalLogic() {
  document.getElementById('modal-add-btn').addEventListener('click', () => {
    const selected = [];
    (currentItem.modifiers || []).forEach(group => {
      document.getElementsByName(`mod-${group.id}`).forEach(inp => {
        if (inp.checked) selected.push(inp.value);
      });
    });
    addToCart(currentItem, selected);
    bootstrap.Modal.getInstance(document.getElementById('productModal')).hide();
  });
}

// Работа с корзиной
function addToCart(item, modifiers = []) {
  const key = (item.externalId || item.id) + modifiers.join(',');
  let ci = cart.find(i => i.key === key);
  if (ci) ci.quantity++;
  else cart.push({
    key,
    externalId: item.externalId || item.id,
    name: item.name,
    price: item.price,
    quantity: 1,
    modifiers
  });
  saveCart();
  updateCartCount();
}

function loadCart() {
  cart = JSON.parse(localStorage.getItem('cartData') || '[]');
  updateCartCount();
}

function saveCart() {
  localStorage.setItem('cartData', JSON.stringify(cart));
}

function updateCartCount() {
  const cnt = cart.reduce((sum, i) => sum + i.quantity, 0);
  document.getElementById('cart-count').innerText = cnt;
}

// Показ/скрытие экранов
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

// Рендер корзины
function renderCartItems() {
  const ctr = document.getElementById('cart-items');
  ctr.innerHTML = '';
  if (cart.length === 0) {
    ctr.innerHTML = '<p>Корзина пуста</p>';
    return;
  }
  let total = 0;
  cart.forEach((item, idx) => {
    total += item.price * item.quantity;
    const div = document.createElement('div');
    div.className = 'cart-item d-flex justify-content-between align-items-center mb-2';
    div.innerHTML = `
      <span>${item.name}</span>
      <div class="d-flex align-items-center">
        <button class="btn btn-sm btn-outline-secondary me-2" onclick="decrementQuantity(${idx})">−</button>
        <span>${item.quantity}</span>
        <button class="btn btn-sm btn-outline-secondary ms-2" onclick="incrementQuantity(${idx})">+</button>
        <span class="mx-3">${item.price * item.quantity}₽</span>
        <button class="btn btn-sm btn-danger" onclick="removeFromCart(${idx})">×</button>
      </div>
    `;
    ctr.appendChild(div);
  });
  ctr.insertAdjacentHTML('beforeend',
    `<div class="cart-total"><strong>Итого: ${total}₽</strong></div>`
  );
}

function incrementQuantity(i) {
  cart[i].quantity++;
  saveCart(); renderCartItems(); updateCartCount();
}

function decrementQuantity(i) {
  if (cart[i].quantity > 1) cart[i].quantity--;
  else cart.splice(i, 1);
  saveCart(); renderCartItems(); updateCartCount();
}

function removeFromCart(i) {
  cart.splice(i, 1);
  saveCart(); renderCartItems(); updateCartCount();
}

// Отправка заказа
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

  // Проверяем обязательные поля (время доставки убрано)
  if (!info.name || !info.phone || !info.street || !info.house) {
    alert('Пожалуйста, заполните все обязательные поля.');
    return;
  }
  if (cart.length === 0) {
    alert('Ваша корзина пуста.');
    return;
  }

  const order = {
    items: cart.map(i => ({
      externalId: i.externalId,
      name: i.name,
      price: i.price,
      quantity: i.quantity,
      modifiers: i.modifiers
    })),
    delivery_info: info
  };

  tg.sendData(JSON.stringify(order));
  localStorage.removeItem('cartData');
  tg.close();
}
