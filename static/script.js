const API_URL = 'http://localhost:3000/api';
const WS_URL = 'ws://localhost:3000/ws';

class KanbanApp {
  constructor() {
    this.ws = null;
    this.token = localStorage.getItem('token');
    this.refreshToken = localStorage.getItem('refreshToken');
    this.boards = [];
    this.currentBoard = null;
    this.draggedCard = null;
    this.initEventListeners();
    this.connectWebSocket();
  }

  async apiCall(endpoint, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers
      });

      if (response.status === 401) {
        const refreshed = await this.refreshAccessToken();
        if (refreshed) {
          headers['Authorization'] = `Bearer ${this.token}`;
          return fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers
          }).then(r => this.handleResponse(r));
        }
        throw new Error('Session expired');
      }

      return this.handleResponse(response);
    } catch (error) {
      this.handleApiError(error);
      throw error;
    }
  }

  async handleResponse(response) {
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || 'API error');
      return data;
    }
    return response;
  }

  async refreshAccessToken() {
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: this.refreshToken })
      });

      if (!response.ok) throw new Error('Refresh failed');

      const { token, refreshToken } = await response.json();
      this.token = token;
      this.refreshToken = refreshToken;
      localStorage.setItem('token', token);
      localStorage.setItem('refreshToken', refreshToken);
      return true;
    } catch {
      this.logout();
      return false;
    }
  }

  handleApiError(error) {
    const notification = document.getElementById('notification');
    notification.textContent = error.message || 'An error occurred';
    notification.className = 'notification error show';
    setTimeout(() => notification.classList.remove('show'), 5000);
  }

  connectWebSocket() {
    if (!this.token) return;

    this.ws = new WebSocket(`${WS_URL}?token=${this.token}`);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleWebSocketMessage(data);
    };

    this.ws.onclose = () => {
      setTimeout(() => this.connectWebSocket(), 5000);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  handleWebSocketMessage(data) {
    if (data.type === 'cardUpdate') {
      this.updateCardInDOM(data.payload);
    } else if (data.type === 'cardCreate') {
      this.addCardToDOM(data.payload);
    } else if (data.type === 'cardDelete') {
      this.removeCardFromDOM(data.payload.cardId);
    }
  }

  initEventListeners() {
    document.getElementById('loginForm')?.addEventListener('submit', this.login.bind(this));
    document.getElementById('logoutBtn')?.addEventListener('click', this.logout.bind(this));
    document.getElementById('createBoardBtn')?.addEventListener('click', () => this.openModal('boardModal'));
    document.getElementById('createCardBtn')?.addEventListener('click', () => this.openModal('cardModal'));
    document.getElementById('filterInput')?.addEventListener('input', this.filterCards.bind(this));
    
    document.querySelectorAll('.modal-close').forEach(btn => {
      btn.addEventListener('click', () => this.closeModal(btn.closest('.modal').id));
    });

    document.getElementById('boardForm')?.addEventListener('submit', this.createBoard.bind(this));
    document.getElementById('cardForm')?.addEventListener('submit', this.createCard.bind(this));
  }

  async login(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    try {
      const data = await this.apiCall('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password })
      });

      this.token = data.token;
      this.refreshToken = data.refreshToken;
      localStorage.setItem('token', data.token);
      localStorage.setItem('refreshToken', data.refreshToken);

      window.location.href = '/boards';
    } catch (error) {
      this.handleApiError(error);
    }
  }

  logout() {
    this.token = null;
    this.refreshToken = null;
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
    window.location.href = '/login';
  }

  async loadBoards() {
    try {
      const data = await this.apiCall('/boards');
      this.boards = data.boards;
      this.renderBoards();
    } catch (error) {
      this.handleApiError(error);
    }
  }

  renderBoards() {
    const container = document.getElementById('boardsContainer');
    if (!container) return;

    container.innerHTML = this.boards.map(board => `
      <div class="board-card" data-board-id="${board.id}">
        <h3>${board.name}</h3>
        <p>${board.description || ''}</p>
        <button onclick="app.selectBoard('${board.id}')">Open</button>
      </div>
    `).join('');
  }

  async selectBoard(boardId) {
    this.currentBoard = boardId;
    try {
      const data = await this.apiCall(`/boards/${boardId}`);
      this.renderBoard(data);
    } catch (error) {
      this.handleApiError(error);
    }
  }

  renderBoard(board) {
    const container = document.getElementById('boardContainer');
    if (!container) return;

    container.innerHTML = `
      <h1>${board.name}</h1>
      <div class="columns-container" id="columnsContainer">
        ${board.columns.map(column => this.renderColumn(column)).join('')}
      </div>
    `;

    this.attachDragListeners();
  }

  renderColumn(column) {
    return `
      <div class="column" data-column-id="${column.id}">
        <h2>${column.name}</h2>
        <div class="cards-container" data-column-id="${column.id}">
          ${column.cards.map(card => this.renderCard(card)).join('')}
        </div>
      </div>
    `;
  }

  renderCard(card) {
    return `
      <div class="card" 
           draggable="true" 
           data-card-id="${card.id}"
           data-column-id="${card.columnId}">
        <h3>${card.title}</h3>
        <p>${card.description || ''}</p>
        <div class="card-meta">
          <span class="priority ${card.priority}">${card.priority}</span>
          <button onclick="app.deleteCard('${card.id}')" class="delete-btn">×</button>
        </div>
      </div>
    `;
  }

  attachDragListeners() {
    document.querySelectorAll('.card').forEach(card => {
      card.addEventListener('dragstart', this.handleDragStart.bind(this));
      card.addEventListener('dragend', this.handleDragEnd.bind(this));
    });

    document.querySelectorAll('.cards-container').forEach(container => {
      container.addEventListener('dragover', this.handleDragOver.bind(this));
      container.addEventListener('drop', this.handleDrop.bind(this));
    });
  }

  handleDragStart(e) {
    this.draggedCard = e.target;
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', e.target.innerHTML);
    e.dataTransfer.setData('cardId', e.target.dataset.cardId);
  }

  handleDragEnd(e) {
    e.target.classList.remove('dragging');
    this.draggedCard = null;
  }

  handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }

  async handleDrop(e) {
    e.preventDefault();
    const cardId = e.dataTransfer.getData('cardId');
    const newColumnId = e.currentTarget.dataset.columnId;

    try {
      await this.apiCall(`/cards/${cardId}/move`, {
        method: 'PUT',
        body: JSON.stringify({ columnId: newColumnId })
      });

      const card = document.querySelector(`[data-card-id="${cardId}"]`);
      e.currentTarget.appendChild(card);
    } catch (error) {
      this.handleApiError(error);
    }
  }

  async createBoard(e) {
    e.preventDefault();
    const name = document.getElementById('boardName').value;
    const description = document.getElementById('boardDescription').value;

    try {
      await this.apiCall('/boards', {
        method: 'POST',
        body: JSON.stringify({ name, description })
      });

      this.closeModal('boardModal');
      document.getElementById('boardForm').reset();
      this.loadBoards();
    } catch (error) {
      this.handleApiError(error);
    }
  }

  async createCard(e) {
    e.preventDefault();
    const title = document.getElementById('cardTitle').value;
    const description = document.getElementById('cardDescription').value;
    const priority = document.getElementById('cardPriority').value;
    const columnId = document.getElementById('cardColumnId').value;

    try {
      await this.apiCall('/cards', {
        method: 'POST',
        body: JSON.stringify({ title, description, priority, columnId, boardId: this.currentBoard })
      });

      this.closeModal('cardModal');
      document.getElementById('cardForm').reset();
      this.selectBoard(this.currentBoard);
    } catch (error) {
      this.handleApiError(error);
    }
  }

  async deleteCard(cardId) {
    if (!confirm('Delete this card?')) return;

    try {
      await this.apiCall(`/cards/${cardId}`, {
        method: 'DELETE'
      });
      this.removeCardFromDOM(cardId);
    } catch (error) {
      this.handleApiError(error);
    }
  }

  updateCardInDOM(card) {
    const cardEl = document.querySelector(`[data-card-id="${card.id}"]`);
    if (cardEl) {
      cardEl.outerHTML = this.renderCard(card);
      this.attachDragListeners();
    }
  }

  addCardToDOM(card) {
    const container = document.querySelector(`[data-column-id="${card.columnId}"] .cards-container`);
    if (container) {
      container.insertAdjacentHTML('beforeend', this.renderCard(card));
      this.attachDragListeners();
    }
  }

  removeCardFromDOM(cardId) {
    const cardEl = document.querySelector(`[data-card-id="${cardId}"]`);
    if (cardEl) cardEl.remove();
  }

  filterCards(e) {
    const searchTerm = e.target.value.toLowerCase();
    document.querySelectorAll('.card').forEach(card => {
      const title = card.querySelector('h3').textContent.toLowerCase();
      const description = card.querySelector('p').textContent.toLowerCase();
      const match = title.includes(searchTerm) || description.includes(searchTerm);
      card.style.display = match ? 'block' : 'none';
    });
  }

  openModal(modalId) {
    document.getElementById(modalId).classList.add('show');
  }

  closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
  }
}

const app = new KanbanApp();

document.addEventListener('DOMContentLoaded', () => {
  if (window.location.pathname === '/boards' && app.token) {
    app.loadBoards();
  }
});