// js/app.js

// 1) Подготовка инициализации после полной загрузки страницы
document.addEventListener('DOMContentLoaded', async () => {
  // Загрузить шаблон модального окна и привязать логику
  await loadModalTemplate();

  // Инициализировать Telegram WebApp
  const tg = window.Telegram.WebApp;
  tg.expand();

  // Восстановить корзину и обновить счётчик
  loadCart();
  bindCartButton();
  bindPaymentToggle();

  // Загрузить и отрисовать меню
  await fetchMenu();
});

// 2) Загрузка и инициализация модалки
async function loadModalTemplate() {
  const html = await fetch('components/product-modal.html').then(r => r.text());
  document.getElementById('product-modal-container').innerHTML = html;
  // После вставки в DOM — привязать кнопку «Добавить в корзину»
  document.getElementById('modal-add-btn')
    .addEventListener('click', onModalAdd);
}

// 3) Общие переменные
const API_BASE = "http://127.0.0.1:8000";
let cart = [];
let categories = {};
let currentItem = null;

// 4) Привязка кнопки корзины
function bindCartButton() {
  document.getElementById('cart-button')
    .addEventListener('click', showCart);
}

// 5) Переключатель «Сдача с»
function bindPaymentToggle() {
  document.getElementById('pay-cash').addEventListener('change', toggleChange);
  document.getElementById('pay-card').addEventListener('change', toggleChange);
}
function toggleChange() {
  document.getElementById('change-container').style.display =
    document.getElementById('pay-cash').checked ? 'block' : 'none';
}

// 6) Загрузка меню
async function fetchMenu() {
  try {
    const resp = await fetch(`${API_BASE}/menu`, { mode: 'cors' });
    if (!resp.ok) throw new Error(resp.status);
    categories = await resp.json();
    renderCategories();
    // Показать первую категорию по умолчанию
    const first = Object.keys(categories)[0];
    if (first) showItems(first);
  } catch (e) {
    console.error(e);
    alert('Не удалось загрузить меню');
  }
}

// 7) Рендер категорий
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

// 8) Рендер товаров и навешивание открытия модалки
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

// 9) Открытие модалки
function openModal(categoryId, item) {
  currentItem = item;
  document.getElementById('modal-title').textContent = item.name;
  document.getElementById('modal-image').src = item.image || 'images/placeholder.png';
  document.getElementById('modal-desc').innerHTML = item.description || 'Описание недоступно';
  renderModifiers(item.modifiers || []);
  // Вызов Bootstrap-модали по элементу
  const modalEl = document.getElementById('productModal');
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

// 10) Рендер модификаторов
function renderModifiers(mods) {
  const ctr = document.getElementById('modal-modifiers');
  ctr.innerHTML = '';
  if (mods.length === 0) {
    ctr.style.display = 'none';
    return;
  }
  ctr.style.display = 'block';
  mods.forEach(group => {
    const wrapper = document.createElement('div');
    wrapper.innerHTML = `<p class="mb-1"><strong>${group.name}</strong></p>`;
    group.options.forEach(opt => {
      const id = `mod-${group.id}-${opt.id}`;
      wrapper.innerHTML += `
        <div class="form-check">
          <input class="form-check-input"
                 type="${group.type==='Single'?'radio':'checkbox'}"
                 name="mod-${group.id}" id="${id}" value="${opt.id}">
          <label class="form-check-label" for="${id}">
            ${opt.name} (+${opt.cost}₽)
          </label>
        </div>`;
    });
    ctr.append(wrapper);
  });
}

// 11) Добавление из модалки
function onModalAdd() {
  const selected = [];
  (currentItem.modifiers||[]).forEach(group => {
    document.getElementsByName(`mod-${group.id}`).forEach(inp => {
      if (inp.checked) selected.push(inp.value);
    });
  });
  addToCart(currentItem, selected);
  const modalEl = document.getElementById('productModal');
  bootstrap.Modal.getInstance(modalEl).hide();
}

// 12) Работа с корзиной
function loadCart() {
  cart = JSON.parse(localStorage.getItem('cartData')||'[]');
  updateCartCount();
}
function saveCart() {
  localStorage.setItem('cartData', JSON.stringify(cart));
}
function updateCartCount() {
  document.getElementById('cart-count').textContent =
    cart.reduce((sum,i)=>sum+i.quantity,0);
}
function addToCart(item, mods=[]) {
  const key = (item.externalId||item.id)+mods.join(',');
  let ci = cart.find(i=>i.key===key);
  if (ci) ci.quantity++; else cart.push({ key, externalId:item.externalId||item.id, name:item.name, price:item.price, quantity:1, modifiers:mods });
  saveCart(); updateCartCount();
}

// 13) Переходы между экранами
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

// 14) Рендер и изменение корзины
function renderCartItems() {
  const ctr = document.getElementById('cart-items');
  ctr.innerHTML = '';
  if (!cart.length) { ctr.innerHTML = '<p>Корзина пуста</p>'; return; }
  let total = 0;
  cart.forEach((item, idx) => {
    total += item.price * item.quantity;
    const div = document.createElement('div');
    div.className = 'cart-item d-flex justify-content-between align-items-center mb-2';
    div.innerHTML = `
      <span>${item.name}</span>
      <div class="d-flex align-items-center">
        <button class="btn btn-sm btn-outline-secondary me-2" onclick="changeQty(${idx}, -1)">−</button>
        <span>${item.quantity}</span>
        <button class="btn btn-sm btn-outline-secondary ms-2" onclick="changeQty(${idx}, +1)">+</button>
        <span class="mx-3">${item.price*item.quantity}₽</span>
        <button class="btn btn-sm btn-danger" onclick="removeFromCart(${idx})">×</button>
      </div>`;
    ctr.append(div);
  });
  ctr.insertAdjacentHTML('beforeend', `<div class="cart-total"><strong>Итого: ${total}₽</strong></div>`);
}
function changeQty(i, delta) {
  cart[i].quantity += delta;
  if (cart[i].quantity < 1) cart.splice(i,1);
  saveCart(); renderCartItems(); updateCartCount();
}
function removeFromCart(i) {
  cart.splice(i,1);
  saveCart(); renderCartItems(); updateCartCount();
}

// 15) Отправка заказа (время доставки убрано)
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
  if (!info.name||!info.phone||!info.street||!info.house) {
    return alert('Заполните все обязательные поля.');
  }
  if (!cart.length) {
    return alert('Корзина пуста.');
  }
  const order = { items: cart.map(i=>({
    externalId: i.externalId, name: i.name, price: i.price, quantity: i.quantity, modifiers: i.modifiers
  })), delivery_info: info };
  window.Telegram.WebApp.sendData(JSON.stringify(order));
  localStorage.removeItem('cartData');
  window.Telegram.WebApp.close();
}
