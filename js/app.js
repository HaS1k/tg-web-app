const tg = window.Telegram.WebApp;
tg.expand();

let cart = [];
let categories = {};
let currentItem = null;

// Загрузка компонента модалки
fetch('components/product-modal.html')
  .then(r => r.text())
  .then(html => {
    document.getElementById('product-modal-container').innerHTML = html;
    initModalLogic();
  });

document.addEventListener('DOMContentLoaded', () => {
  loadCart();
  fetchMenu();
});

async function fetchMenu() {
  try {
    const resp = await fetch('/menu');
    const data = await resp.json();
    categories = data;
    renderCategories();
  } catch (e) {
    console.error(e);
  }
}

function renderCategories() {
  const ctr = document.getElementById('categories');
  ctr.innerHTML = '';
  for (let cid in categories) {
    const btn = document.createElement('button');
    btn.className = 'btn coffee-btn me-2 mb-2';
    btn.innerText = categories[cid].name;
    btn.onclick = () => showItems(cid);
    ctr.append(btn);
  }
}

function showItems(cid) {
  const ctr = document.getElementById('items');
  ctr.innerHTML = '';
  categories[cid].items.forEach(item => {
    const col = document.createElement('div');
    col.className = 'col-12 col-sm-6 col-md-4';
    col.innerHTML = `
      <div class="product-card">
        <img src="${item.image||'images/placeholder.png'}"
             class="product-image" alt="${item.name}"/>
        <div class="p-2">
          <h6>${item.name}</h6>
          <p>${item.price} ₽</p>
          <button class="btn coffee-btn" onclick="openModal(${cid}, '${item.externalId||item.id}')">
            Подробнее
          </button>
        </div>
      </div>
    `;
    ctr.append(col);
  });
}

function openModal(categoryId, extId) {
  currentItem = categories[categoryId].items.find(i =>
    (i.externalId||i.id) == extId);
  if (!currentItem) return;
  // заполняем modal
  document.getElementById('modal-title').innerText = currentItem.name;
  document.getElementById('modal-image').src = currentItem.image||'images/placeholder.png';
  document.getElementById('modal-desc').innerText = currentItem.description||'Описание недоступно';
  renderModifiers(currentItem.modifiers||[]);
  // показываем
  new bootstrap.Modal('#productModal').show();
}

function renderModifiers(mods) {
  const ctr = document.getElementById('modal-modifiers');
  ctr.innerHTML = '';
  mods.forEach(group => {
    const div = document.createElement('div');
    div.innerHTML = `<p class="mb-1"><strong>${group.name}</strong></p>`;
    group.options.forEach(opt => {
      const id = `mod-${group.id}-${opt.id}`;
      div.innerHTML += `
        <div class="form-check">
          <input class="form-check-input" type="${
            group.type === 'Single' ? 'radio' : 'checkbox'
          }" name="mod-${group.id}" id="${id}" value="${opt.id}">
          <label class="form-check-label" for="${id}">
            ${opt.name} (+${opt.cost}₽)
          </label>
        </div>
      `;
    });
    ctr.append(div);
  });
}

function initModalLogic() {
  document.getElementById('modal-add-btn').onclick = () => {
    // Собираем выбранные модификаторы
    const selected = [];
    (currentItem.modifiers||[]).forEach(group => {
      document.getElementsByName(`mod-${group.id}`).forEach(inp => {
        if (inp.checked) selected.push(inp.value);
      });
    });
    addToCart(currentItem, selected);
    bootstrap.Modal.getInstance(document.getElementById('productModal')).hide();
  };
}

function addToCart(item, modifiers=[]) {
  const key = (item.externalId||item.id) + (modifiers.join(',')||'');
  let cartItem = cart.find(i => i.key === key);
  if (cartItem) {
    cartItem.quantity++;
  } else {
    cart.push({
      key,
      externalId: item.externalId||item.id,
      name: item.name,
      price: item.price,
      quantity: 1,
      modifiers
    });
  }
  saveCart();
  updateCartCount();
}

function loadCart() {
  const data = localStorage.getItem('cartData');
  if (data) cart = JSON.parse(data);
  updateCartCount();
}

function saveCart() {
  localStorage.setItem('cartData', JSON.stringify(cart));
}

function updateCartCount() {
  document.getElementById('cart-count').innerText =
    cart.reduce((sum,i)=>sum+i.quantity,0);
}

function backToMain() {
  document.getElementById('cart-content').classList.add('d-none');
  document.getElementById('main-content').classList.remove('d-none');
}
function showOrderForm() {
  document.getElementById('cart-content').classList.add('d-none');
  document.getElementById('order-form').classList.remove('d-none');
}
function backToCart() {
  document.getElementById('order-form').classList.add('d-none');
  document.getElementById('cart-content').classList.remove('d-none');
}

function submitOrder() {
  // собираем payload как раньше, включая modifiers
  const order = {
    items: cart.map(i => ({
      externalId: i.externalId,
      price: i.price,
      quantity: i.quantity,
      modifiers: i.modifiers
    })),
    delivery_info: { /* ... */ }
  };
  tg.sendData(JSON.stringify(order));
  tg.close();
}
