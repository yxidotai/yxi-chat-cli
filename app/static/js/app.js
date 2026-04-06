/**
 * yxi-chat-cli Web Interface JavaScript
 */

(function() {
    'use strict';

    // ========================================
    // State Management
    // ========================================
    const state = {
        connected: false,
        mode: 'online',
        messages: [],
        sessionId: null,
        sessionName: null,
        typing: false,
        mcpNodes: [],
        activeMcpNode: null,
        history: [],
        currentHistoryIndex: -1,
        historyBuffer: [],
        config: {
            apiKey: '',
            apiBase: 'https://api.yxi.ai/v1',
            model: 'yxi-7b-terminal'
        }
    };

    // ========================================
    // DOM Elements
    // ========================================
    const elements = {
        // Status
        connectionStatus: document.getElementById('connection-status'),
        statusDot: document.querySelector('.status-dot'),
        statusText: document.querySelector('.status-text'),
        
        // Mode toggle
        modeText: document.getElementById('mode-text'),
        modeSwitchInput: document.getElementById('mode-switch-input'),
        
        // Sidebars
        historySidebar: document.getElementById('history-sidebar'),
        settingsSidebar: document.getElementById('settings-sidebar'),
        historyList: document.getElementById('history-list'),
        
        // Buttons
        newChatBtn: document.getElementById('new-chat-btn'),
        sidebarToggle: document.getElementById('sidebar-toggle'),
        settingsBtn: document.getElementById('settings-btn'),
        settingsSidebarClose: document.getElementById('settings-sidebar-close'),
        saveApiKeyBtn: document.getElementById('save-api-key'),
        saveApiBaseBtn: document.getElementById('save-api-base'),
        saveModelBtn: document.getElementById('save-model'),
        addMcpNodeBtn: document.getElementById('add-mcp-node'),
        clearHistoryBtn: document.getElementById('clear-all-history'),
        getHelpBtn: document.getElementById('get-help'),
        exportChatBtn: document.getElementById('export-chat'),
        
        // Configuration
        apiKeyInput: document.getElementById('api-key'),
        apiBaseInput: document.getElementById('api-base'),
        modelSelect: document.getElementById('model-select'),
        mcpNodesContainer: document.getElementById('mcp-nodes'),
        
        // Chat
        welcomeScreen: document.getElementById('welcome-screen'),
        chatMessages: document.getElementById('chat-messages'),
        messageInput: document.getElementById('message-input'),
        sendBtn: document.getElementById('send-btn'),
        charCount: document.getElementById('char-count'),
        typingIndicator: document.getElementById('typing-indicator'),
        quickActions: document.getElementById('quick-actions'),
        
        // Modals
        mcpModal: document.getElementById('mcp-modal'),
        mcpModalClose: document.getElementById('mcp-modal-close'),
        mcpModalCancel: document.getElementById('mcp-modal-cancel'),
        mcpModalSave: document.getElementById('mcp-modal-save'),
        helpModal: document.getElementById('help-modal'),
        helpModalClose: document.getElementById('help-modal-close'),
        helpModalCloseBtn: document.getElementById('help-modal-close-btn'),
        helpContent: document.getElementById('help-content'),
        renameModal: document.getElementById('rename-modal'),
        renameModalClose: document.getElementById('rename-modal-close'),
        renameModalCancel: document.getElementById('rename-modal-cancel'),
        renameModalSave: document.getElementById('rename-modal-save'),
        sessionNameInput: document.getElementById('session-name-input'),
        
        // Toast container
        toastContainer: document.getElementById('toast-container')
    };

    // ========================================
    // WebSocket Connection
    // ========================================
    let websocket = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    const reconnectDelay = 3000;

    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/chat`;
        
        try {
            websocket = new WebSocket(wsUrl);
            
            websocket.onopen = () => {
                console.log('WebSocket connected');
                state.connected = true;
                reconnectAttempts = 0;
                updateConnectionStatus(true);
                showToast('Connected to server', 'success');
            };
            
            websocket.onmessage = handleWebSocketMessage;
            
            websocket.onclose = () => {
                console.log('WebSocket disconnected');
                state.connected = false;
                updateConnectionStatus(false);
                
                // Attempt to reconnect
                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    showToast(`Reconnecting... (${reconnectAttempts}/${maxReconnectAttempts})`, 'info');
                    setTimeout(connectWebSocket, reconnectDelay);
                } else {
                    showToast('Connection lost. Please refresh the page.', 'error');
                }
            };
            
            websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                showToast('Connection error occurred', 'error');
            };
            
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            showToast('Failed to connect to server', 'error');
        }
    }

    // ========================================
    // Message Handling
    // ========================================
    function handleWebSocketMessage(event) {
        try {
            const message = JSON.parse(event.data);
            
            switch (message.type) {
                case 'status':
                    updateStatus(message.data);
                    break;
                    
                case 'history':
                    loadHistory(message.data.messages);
                    break;
                    
                case 'stream':
                    updateStreamingMessage(message.data);
                    break;
                    
                case 'system':
                    handleSystemMessage(message.data);
                    break;
                    
                case 'error':
                    showToast(message.data.message, 'error');
                    stopTypingIndicator();
                    break;
                    
                case 'help':
                    showHelpContent(message.data.content);
                    break;
                    
                case 'command_result':
                    showToast(message.data.result, 'success');
                    break;
                    
                case 'mcp_result':
                    displayMcpResult(message.data);
                    break;
                    
                default:
                    console.log('Unknown message type:', message);
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    }

    // ========================================
    // UI Updates
    // ========================================
    function updateConnectionStatus(connected) {
        state.connected = connected;
        
        if (connected) {
            elements.statusDot.className = 'status-dot status-connected';
            elements.statusText.textContent = 'Connected';
        } else {
            elements.statusDot.className = 'status-dot status-disconnected';
            elements.statusText.textContent = 'Disconnected';
        }
    }

    function updateStatus(statusData) {
        state.mode = statusData.mode || 'online';
        state.activeMcpNode = statusData.active_mcp;
        state.mcpNodes = statusData.mcp_nodes || [];
        
        elements.modeText.textContent = state.mode === 'online' ? 'Online' : 'Offline';
        elements.modeSwitchInput.checked = state.mode === 'online';
        
        if (statusData.api_key_configured) {
            state.config.apiKey = '••••••••';
        }
        if (statusData.api_base) {
            state.config.apiBase = statusData.api_base;
            elements.apiBaseInput.value = statusData.api_base;
        }
        if (statusData.model) {
            state.config.model = statusData.model;
            elements.modelSelect.value = statusData.model;
        }
        
        updateMcpNodesList();
        loadAvailableModels();
    }

    // ========================================
    // Chat Functions
    // ========================================
    let currentStreamingMessage = null;
    let currentStreamingElement = null;

    function loadHistory(messages) {
        state.messages = messages || [];
        
        if (state.messages.length > 0) {
            elements.welcomeScreen.classList.add('hidden');
            elements.chatMessages.classList.remove('hidden');
            renderMessages();
            scrollToBottom();
        }
    }

    function renderMessages() {
        elements.chatMessages.innerHTML = '';
        
        state.messages.forEach((message, index) => {
            addMessageElement(message, index);
        });
        
        // Re-highlight code blocks
        if (window.Prism) {
            Prism.highlightAllUnder(elements.chatMessages);
        }
    }

    function addMessageElement(message, index = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role}`;
        messageDiv.dataset.index = index;
        
        const messageHeader = document.createElement('div');
        messageHeader.className = 'message-header';
        
        const authorSpan = document.createElement('span');
        authorSpan.className = 'message-author';
        
        if (message.role === 'user') {
            authorSpan.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg> You`;
        } else if (message.role === 'assistant') {
            authorSpan.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1V3a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v1.27c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"></path><circle cx="17" cy="11" r="1" fill="currentColor"></circle><circle cx="15" cy="14" r="1" fill="currentColor"></circle></svg> Assistant`;
        } else {
            authorSpan.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg> System`;
        }
        
        const timeSpan = document.createElement('span');
        timeSpan.className = 'message-time';
        timeSpan.textContent = formatTime(message.timestamp || Date.now());
        timeSpan.title = new Date(message.timestamp || Date.now()).toLocaleString();
        
        messageHeader.appendChild(authorSpan);
        messageHeader.appendChild(timeSpan);
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Use markdown parser for assistant messages
        if (message.role === 'assistant' || message.role === 'system') {
            messageContent.innerHTML = window.parseMarkdown ? window.parseMarkdown(message.content) : escapeHtml(message.content);
        } else {
            messageContent.innerHTML = escapeHtml(message.content).replace(/\n/g, '<br>');
        }
        
        messageDiv.appendChild(messageHeader);
        messageDiv.appendChild(messageContent);
        
        elements.chatMessages.appendChild(messageDiv);
        
        return messageDiv;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        // Within the same minute
        if (diff < 60000) {
            return 'Just now';
        }
        
        // Within the same hour
        if (diff < 3600000) {
            const mins = Math.floor(diff / 60000);
            return `${mins}m ago`;
        }
        
        // Within the same day
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        
        // Within the last week
        if (diff < 604800000) {
            return date.toLocaleDateString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' });
        }
        
        // Older
        return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }

    function updateStreamingMessage(data) {
        if (!currentStreamingElement) {
            currentStreamingElement = addMessageElement({
                role: 'assistant',
                content: ''
            });
            
            state.messages.push({
                role: 'assistant',
                content: '',
                timestamp: Date.now()
            });
            
            currentStreamingMessage = state.messages[state.messages.length - 1];
        }
        
        const content = data.accumulated || data.content || '';
        currentStreamingMessage.content = content;
        
        const messageContent = currentStreamingElement.querySelector('.message-content');
        messageContent.innerHTML = window.parseMarkdown ? window.parseMarkdown(content) : escapeHtml(content);
        
        // Re-highlight code blocks during streaming
        if (window.Prism) {
            Prism.highlightAllUnder(messageContent);
        }
        
        scrollToBottom();
    }

    function handleSystemMessage(data) {
        if (data.status === 'processing') {
            // Message is being processed
        } else if (data.status === 'complete') {
            showToast(data.message, 'success');
            stopTypingIndicator();
            
            // Complete streaming message
            if (currentStreamingElement) {
                if (window.Prism) {
                    Prism.highlightAllUnder(currentStreamingElement.querySelector('.message-content'));
                }
            }
            currentStreamingElement = null;
            currentStreamingMessage = null;
            
            // Save to history
            saveCurrentChat();
            refreshHistoryList();
            
        } else if (data.status === 'received') {
            // Message received, processing
        } else if (data.status === 'mode_changed') {
            showToast(data.message, 'success');
            updateStatusSync();
        } else if (data.status === 'cleared') {
            showToast(data.message, 'success');
            state.messages = [];
            elements.chatMessages.innerHTML = '';
            elements.welcomeScreen.classList.remove('hidden');
            elements.chatMessages.classList.add('hidden');
            saveCurrentChat();
            refreshHistoryList();
        }
    }

    function displayMcpResult(data) {
        const message = {
            role: 'assistant',
            content: `**Tool:** ${data.tool}\n\n**Result:**\n\n\`\`\`json\n${data.result}\n\`\`\``,
            timestamp: Date.now()
        };
        
        state.messages.push(message);
        addMessageElement(message);
        scrollToBottom();
        
        stopTypingIndicator();
        currentStreamingElement = null;
        currentStreamingMessage = null;
    }

    function sendMessage() {
        const content = elements.messageInput.value.trim();
        if (!content || !state.connected) return;
        
        // Add user message
        const userMessage = {
            role: 'user',
            content: content,
            timestamp: Date.now()
        };
        
        state.messages.push(userMessage);
        addMessageElement(userMessage);
        
        // Add to history buffer for up/down navigation
        state.historyBuffer.push(content);
        state.currentHistoryIndex = state.historyBuffer.length;
        
        // Clear input
        elements.messageInput.value = '';
        updateCharCount();
        scrollToBottom();
        
        // Hide welcome screen
        elements.welcomeScreen.classList.add('hidden');
        elements.chatMessages.classList.remove('hidden');
        
        // Start typing indicator
        startTypingIndicator();
        
        // Send message
        websocket.send(JSON.stringify({
            type: 'chat',
            content: content,
            mode: state.mode
        }));
    }

    function startTypingIndicator() {
        state.typing = true;
        elements.typingIndicator.classList.remove('hidden');
        elements.sendBtn.classList.add('loading');
    }

    function stopTypingIndicator() {
        state.typing = false;
        elements.typingIndicator.classList.add('hidden');
        elements.sendBtn.classList.remove('loading');
    }

    // ========================================
    // History Management
    // ========================================
    function saveCurrentChat() {
        if (state.messages.length === 0) return;
        
        // Create or update session
        let session = null;
        
        if (state.sessionId) {
            // Find existing session
            session = state.history.find(h => h.id === state.sessionId);
        }
        
        if (!session) {
            // Create new session
            session = {
                id: state.sessionId || generateSessionId(),
                name: state.sessionName || generateSessionName(),
                messages: state.messages,
                updatedAt: Date.now()
            };
            state.history.unshift(session);
            state.sessionId = session.id;
        } else {
            // Update existing session
            session.messages = state.messages.slice();
            session.updatedAt = Date.now();
        }
        
        // Sort history by updated time
        state.history.sort((a, b) => b.updatedAt - a.updatedAt);
        
        // Save to localStorage
        localStorage.setItem('yxi-chat-history', JSON.stringify(state.history));
    }

    function generateSessionId() {
        return 'session_' + Date.now();
    }

    function generateSessionName() {
        if (state.messages.length === 0) return 'New Chat';
        
        const firstMessage = state.messages.find(m => m.role === 'user');
        if (firstMessage) {
            let name = firstMessage.content.substring(0, 30);
            if (firstMessage.content.length > 30) name += '...';
            return name;
        }
        
        return 'New Chat';
    }

    function loadHistoryFromStorage() {
        try {
            const stored = localStorage.getItem('yxi-chat-history');
            if (stored) {
                state.history = JSON.parse(stored);
                refreshHistoryList();
            }
        } catch (error) {
            console.error('Error loading history:', error);
        }
    }

    function refreshHistoryList() {
        elements.historyList.innerHTML = '';
        
        state.history.forEach((session, index) => {
            const item = document.createElement('div');
            item.className = `history-item${session.id === state.sessionId ? ' active' : ''}`;
            item.dataset.index = index;
            
            item.innerHTML = `
                <span class="history-item-title">${escapeHtml(session.name)}</span>
                <div class="history-item-actions">
                    <button class="history-item-btn rename-btn" title="Rename">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                        </svg>
                    </button>
                    <button class="history-item-btn delete-btn" title="Delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    </button>
                </div>
            `;
            
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.history-item-btn')) {
                    loadSession(session.id);
                }
            });
            
            item.querySelector('.rename-btn').addEventListener('click', () => {
                openRenameModal(session.id);
            });
            
            item.querySelector('.delete-btn').addEventListener('click', () => {
                deleteSession(session.id);
            });
            
            elements.historyList.appendChild(item);
        });
    }

    function loadSession(sessionId) {
        const session = state.history.find(h => h.id === sessionId);
        if (!session) return;
        
        // Save current chat first
        if (state.messages.length > 0) {
            saveCurrentChat();
        }
        
        // Load new session
        state.sessionId = session.id;
        state.sessionName = session.name;
        state.messages = session.messages || [];
        
        if (state.messages.length > 0) {
            elements.welcomeScreen.classList.add('hidden');
            elements.chatMessages.classList.remove('hidden');
            renderMessages();
        } else {
            elements.welcomeScreen.classList.remove('hidden');
            elements.chatMessages.classList.add('hidden');
        }
        
        refreshHistoryList();
    }

    function newChat() {
        // Save current chat
        if (state.messages.length > 0) {
            saveCurrentChat();
        }
        
        // Reset state
        state.sessionId = null;
        state.sessionName = null;
        state.messages = [];
        state.historyBuffer = [];
        state.currentHistoryIndex = -1;
        
        // Clear UI
        elements.chatMessages.innerHTML = '';
        elements.welcomeScreen.classList.remove('hidden');
        elements.chatMessages.classList.add('hidden');
        
        // Focus input
        setTimeout(() => elements.messageInput.focus(), 100);
        
        refreshHistoryList();
    }

    function deleteSession(sessionId) {
        if (!confirm('Delete this chat?')) return;
        
        state.history = state.history.filter(h => h.id !== sessionId);
        localStorage.setItem('yxi-chat-history', JSON.stringify(state.history));
        
        if (state.sessionId === sessionId) {
            newChat();
        } else {
            refreshHistoryList();
        }
        
        showToast('Chat deleted', 'success');
    }

    function openRenameModal(sessionId) {
        const session = state.history.find(h => h.id === sessionId);
        if (!session) return;
        
        state.sessionId = sessionId;
        elements.sessionNameInput.value = session.name;
        elements.renameModal.classList.add('show');
        elements.sessionNameInput.focus();
    }

    function renameSession() {
        const newName = elements.sessionNameInput.value.trim();
        if (!newName) return;
        
        const session = state.history.find(h => h.id === state.sessionId);
        if (session) {
            session.name = newName;
            state.sessionName = newName;
            localStorage.setItem('yxi-chat-history', JSON.stringify(state.history));
            refreshHistoryList();
            showToast('Chat renamed', 'success');
        }
        
        elements.renameModal.classList.remove('show');
    }

    function clearAllHistory() {
        if (!confirm('Delete all chat history? This cannot be undone.')) return;
        
        state.history = [];
        localStorage.setItem('yxi-chat-history', JSON.stringify(state.history));
        newChat();
        showToast('All history cleared', 'success');
    }

    // ========================================
    // MCP Nodes
    // ========================================
    async function updateMcpNodesList() {
        try {
            const nodes = await fetchApi('/mcp/nodes');
            state.mcpNodes = nodes;
            renderMcpNodes();
        } catch (error) {
            console.error('Error loading MCP nodes:', error);
        }
    }

    function renderMcpNodes() {
        const container = elements.mcpNodesContainer;
        container.innerHTML = '';
        
        if (state.mcpNodes.length === 0) {
            container.innerHTML = '<p class="text-muted" style="font-size: 0.75rem; padding: 0.5rem;">No MCP nodes configured</p>';
            return;
        }
        
        state.mcpNodes.forEach(node => {
            const nodeDiv = document.createElement('div');
            nodeDiv.className = 'mcp-node';
            
            nodeDiv.innerHTML = `
                <div class="mcp-node-header">
                    <span class="mcp-node-name">${escapeHtml(node.name)}</span>
                    <span class="mcp-node-status ${node.active ? 'active' : ''}">${node.active ? 'Active' : 'Inactive'}</span>
                </div>
                <div class="mcp-node-url">${escapeHtml(node.url)}</div>
                <div class="mcp-node-actions">
                    ${node.active ? '' : '<button class="btn btn-sm use-btn">Use</button>'}
                    <button class="btn btn-sm btn-outline delete-btn">Delete</button>
                </div>
            `;
            
            if (!node.active) {
                nodeDiv.querySelector('.use-btn').addEventListener('click', () => useMcpNode(node.name));
            }
            
            nodeDiv.querySelector('.delete-btn').addEventListener('click', () => removeMcpNode(node.name));
            
            container.appendChild(nodeDiv);
        });
    }

    async function useMcpNode(nodeName) {
        try {
            const result = await fetchApi(`/mcp/nodes/${nodeName}/use`, 'POST');
            showToast(result.message, 'success');
            await updateMcpNodesList();
        } catch (error) {
            showToast('Error using MCP node', 'error');
        }
    }

    async function removeMcpNode(nodeName) {
        if (!confirm(`Remove MCP node "${nodeName}"?`)) return;
        
        try {
            const result = await fetchApi(`/mcp/nodes/${nodeName}`, 'DELETE');
            showToast(result.message, 'success');
            await updateMcpNodesList();
        } catch (error) {
            showToast('Error removing MCP node', 'error');
        }
    }

    // ========================================
    // Configuration
    // ========================================
    async function loadAvailableModels() {
        try {
            const models = await fetchApi('/models');
            const modelSelect = elements.modelSelect;
            
            // Save current selection
            const currentValue = modelSelect.value;
            
            // Clear existing options
            while (modelSelect.options.length > 0) {
                modelSelect.remove(0);
            }
            
            // Add model options
            models.forEach(model => {
                const option = document.createElement('option');
                const modelId = typeof model === 'object' ? (model.id || model.model || model.name) : model;
                const modelName = typeof model === 'object' ? (model.name || model.display_name || modelId) : model;
                
                option.value = modelId;
                option.textContent = modelName;
                modelSelect.appendChild(option);
            });
            
            // Restore selection or use state config
            if (currentValue && modelSelect.querySelector(`option[value="${currentValue}"]`)) {
                modelSelect.value = currentValue;
            } else {
                modelSelect.value = state.config.model;
            }
        } catch (error) {
            console.error('Error loading models:', error);
        }
    }

    async function saveApiKey() {
        const apiKey = elements.apiKeyInput.value.trim();
        if (!apiKey) {
            showToast('Please enter an API key', 'error');
            return;
        }
        
        try {
            const result = await fetchApi('/config', 'POST', { api_key: apiKey });
            state.config.apiKey = apiKey;
            localStorage.setItem('yxi-chat-config', JSON.stringify(state.config));
            showToast(result.message, 'success');
        } catch (error) {
            showToast('Error saving API key', 'error');
        }
    }

    async function saveApiBase() {
        const apiBase = elements.apiBaseInput.value.trim();
        if (!apiBase) {
            showToast('Please enter an API base URL', 'error');
            return;
        }
        
        try {
            const result = await fetchApi('/config', 'POST', { api_base: apiBase });
            state.config.apiBase = apiBase;
            localStorage.setItem('yxi-chat-config', JSON.stringify(state.config));
            showToast(result.message, 'success');
        } catch (error) {
            showToast('Error saving API base URL', 'error');
        }
    }

    async function saveModel() {
        const model = elements.modelSelect.value;
        
        try {
            const result = await fetchApi('/config', 'POST', { model });
            state.config.model = model;
            localStorage.setItem('yxi-chat-config', JSON.stringify(state.config));
            showToast(result.message, 'success');
        } catch (error) {
            showToast('Error saving model', 'error');
        }
    }

    async function addMcpNode() {
        const name = document.getElementById('mcp-name').value.trim();
        const url = document.getElementById('mcp-url').value.trim();
        const token = document.getElementById('mcp-token').value.trim();
        
        if (!name || !url) {
            showToast('Please fill in name and URL', 'error');
            return;
        }
        
        try {
            const result = await fetchApi('/mcp/nodes', 'POST', {
                name,
                url,
                token: token || undefined
            });
            showToast(result.message, 'success');
            hideModal(elements.mcpModal);
            await updateMcpNodesList();
            
            // Clear form
            document.getElementById('mcp-name').value = '';
            document.getElementById('mcp-url').value = '';
            document.getElementById('mcp-token').value = '';
        } catch (error) {
            showToast('Error adding MCP node', 'error');
        }
    }

    // ========================================
    // Help & Export
    // ========================================
    function showHelpContent(content) {
        elements.helpContent.innerHTML = window.parseMarkdown ? window.parseMarkdown(content) : escapeHtml(content);
        showModal(elements.helpModal);
    }

    function exportChat() {
        const chatData = {
            sessionName: state.sessionName || 'Untitled',
            messages: state.messages,
            config: {
                model: state.config.model,
                apiBase: state.config.apiBase
            },
            exportDate: new Date().toISOString()
        };
        
        const blob = new Blob([JSON.stringify(chatData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `yxi-chat-${state.sessionName || 'export'}-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast('Chat exported', 'success');
    }

    // ========================================
    // Keyboard Shortcuts
    // ========================================
    function handleKeyboardShortcuts(e) {
        // Don't trigger shortcuts when typing in input
        if (e.target === elements.messageInput) {
            // Enter to send (without shift)
            if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                sendMessage();
                return;
            }
            
            // Ctrl/Cmd + Enter for new line
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                const start = elements.messageInput.selectionStart;
                const end = elements.messageInput.selectionEnd;
                const value = elements.messageInput.value;
                elements.messageInput.value = value.substring(0, start) + '\n' + value.substring(end);
                elements.messageInput.selectionStart = elements.messageInput.selectionEnd = start + 1;
                updateCharCount();
                return;
            }
            
            // Up arrow for history
            if (e.key === 'ArrowUp' && elements.messageInput.selectionStart === 0 && state.historyBuffer.length > 0) {
                e.preventDefault();
                if (state.currentHistoryIndex > 0) {
                    state.currentHistoryIndex--;
                    elements.messageInput.value = state.historyBuffer[state.currentHistoryIndex];
                    updateCharCount();
                }
                return;
            }
            
            // Down arrow for history
            if (e.key === 'ArrowDown' && elements.messageInput.selectionStart === elements.messageInput.value.length && state.currentHistoryIndex < state.historyBuffer.length - 1) {
                e.preventDefault();
                state.currentHistoryIndex++;
                elements.messageInput.value = state.historyBuffer[state.currentHistoryIndex];
                updateCharCount();
                return;
            }
            
            // Escape to clear selection
            if (e.key === 'Escape') {
                elements.messageInput.blur();
                hideAllModals();
                return;
            }
        }
        
        // Global shortcuts
        if (e.key === '/' && e.target !== elements.messageInput) {
            e.preventDefault();
            elements.messageInput.focus();
        }
        
        // Ctrl/Cmd + N for new chat
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            newChat();
        }
        
        // Ctrl/Cmd + , for settings
        if ((e.ctrlKey || e.metaKey) && e.key === ',') {
            e.preventDefault();
            toggleSettingsSidebar();
        }
    }

    // ========================================
    // UI Helpers
    // ========================================
    function scrollToBottom() {
        requestAnimationFrame(() => {
            elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
        });
    }

    function updateCharCount() {
        const length = elements.messageInput.value.length;
        elements.charCount.textContent = `${length}/4000`;
        
        elements.charCount.style.color = length >= 4000 ? 'var(--error-color)' :
                                         length >= 3000 ? 'var(--warning-color)' :
                                         'var(--text-muted)';
    }

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icons = {
            success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
            error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
            warning: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
            info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
        };
        
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-message">${escapeHtml(message)}</span>
            <button class="toast-close">&times;</button>
        `;
        
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.remove();
        });
        
        elements.toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    function showModal(modal) {
        modal.classList.add('show');
    }

    function hideModal(modal) {
        modal.classList.remove('show');
    }

    function hideAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('show');
        });
    }

    function toggleSettingsSidebar() {
        elements.settingsSidebar.classList.toggle('open');
    }

    // ========================================
    // Copy Code Functionality
    // ========================================
    function setupCopyButtons() {
        document.addEventListener('click', (e) => {
            const copyBtn = e.target.closest('.copy-code-btn');
            if (!copyBtn) return;
            
            e.stopPropagation();
            
            try {
                const code = decodeURIComponent(copyBtn.dataset.code);
                navigator.clipboard.writeText(code).then(() => {
                    copyBtn.classList.add('copied');
                    copyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"></path></svg>';
                    
                    setTimeout(() => {
                        copyBtn.classList.remove('copied');
                        copyBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
                    }, 2000);
                    
                    showToast('Copied to clipboard', 'success');
                });
            } catch (error) {
                showToast('Failed to copy', 'error');
            }
        });
    }

    // ========================================
    // API Helper
    // ========================================
    async function fetchApi(endpoint, method = 'GET', data = null) {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(`/api${endpoint}`, options);
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        return response.json();
    }

    async function updateStatusSync() {
        try {
            const status = await fetchApi('/status');
            updateStatus(status);
        } catch (error) {
            console.error('Error updating status:', error);
        }
    }

    // ========================================
    // Auto-resize Textarea
    // ========================================
    function setupAutoResize() {
        elements.messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 200) + 'px';
            updateCharCount();
        });
        
        elements.messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                // Let the keydown handler in setupEventListeners handle this
            }
        });
    }

    // ========================================
    // Suggestion Cards
    // ========================================
    function setupSuggestionCards() {
        document.querySelectorAll('.suggestion-card').forEach(card => {
            card.addEventListener('click', () => {
                const prompt = card.dataset.prompt;
                elements.messageInput.value = prompt;
                elements.messageInput.focus();
            });
        });
    }

    // ========================================
    // Quick Actions
    // ========================================
    function setupQuickActions() {
        elements.quickActions.addEventListener('click', (e) => {
            const btn = e.target.closest('.quick-action-btn');
            if (!btn) return;
            
            const action = btn.dataset.action;
            
            if (action === 'clear') {
                elements.messageInput.value = '';
                updateCharCount();
                elements.messageInput.style.height = 'auto';
            }
        });
    }

    // ========================================
    // Event Listeners
    // ========================================
    function setupEventListeners() {
        // Send message
        elements.sendBtn.addEventListener('click', sendMessage);
        
        // Auto-resize textarea
        setupAutoResize();
        
        // Character count
        elements.messageInput.addEventListener('input', updateCharCount);
        
        // Keyboard shortcuts
        document.addEventListener('keydown', handleKeyboardShortcuts);
        
        // Sidebar toggle
        elements.sidebarToggle.addEventListener('click', () => {
            elements.historySidebar.classList.toggle('collapsed');
            elements.sidebarToggle.textContent = elements.historySidebar.classList.contains('collapsed') ? '▶' : '◀';
        });
        
        // Settings sidebar
        elements.settingsBtn.addEventListener('click', toggleSettingsSidebar);
        elements.settingsSidebarClose.addEventListener('click', toggleSettingsSidebar);
        
        // New chat
        elements.newChatBtn.addEventListener('click', newChat);
        
        // Mode toggle
        elements.modeSwitchInput.addEventListener('change', (e) => {
            state.mode = e.target.checked ? 'online' : 'offline';
            elements.modeText.textContent = state.mode === 'online' ? 'Online' : 'Offline';
            
            if (state.connected && websocket) {
                websocket.send(JSON.stringify({
                    type: 'command',
                    command: 'mode_change',
                    params: { mode: state.mode }
                }));
            }
        });
        
        // Configuration buttons
        elements.saveApiKeyBtn.addEventListener('click', saveApiKey);
        elements.saveApiBaseBtn.addEventListener('click', saveApiBase);
        elements.saveModelBtn.addEventListener('click', saveModel);
        
        // MCP node modal
        elements.addMcpNodeBtn.addEventListener('click', () => showModal(elements.mcpModal));
        elements.mcpModalClose.addEventListener('click', () => hideModal(elements.mcpModal));
        elements.mcpModalCancel.addEventListener('click', () => hideModal(elements.mcpModal));
        elements.mcpModalSave.addEventListener('click', addMcpNode);
        
        // Help modal
        elements.getHelpBtn.addEventListener('click', () => {
            if (websocket) {
                websocket.send(JSON.stringify({
                    type: 'command',
                    command: 'get_help'
                }));
            }
        });
        elements.helpModalClose.addEventListener('click', () => hideModal(elements.helpModal));
        elements.helpModalCloseBtn.addEventListener('click', () => hideModal(elements.helpModal));
        
        // Rename modal
        elements.renameModalClose.addEventListener('click', () => hideModal(elements.renameModal));
        elements.renameModalCancel.addEventListener('click', () => hideModal(elements.renameModal));
        elements.renameModalSave.addEventListener('click', renameSession);
        
        // Clear history
        elements.clearHistoryBtn.addEventListener('click', clearAllHistory);
        
        // Export chat
        elements.exportChatBtn.addEventListener('click', exportChat);
        
        // Close modals on backdrop click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    hideModal(modal);
                }
            });
        });
        
        // Suggestion cards
        setupSuggestionCards();
        
        // Quick actions
        setupQuickActions();
        
        // Copy buttons
        setupCopyButtons();
        
        // Window resize
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                elements.settingsSidebar.classList.remove('open');
            }
        });
    }

    // ========================================
    // Load Local Config
    // ========================================
    function loadLocalConfig() {
        try {
            const stored = localStorage.getItem('yxi-chat-config');
            if (stored) {
                const config = JSON.parse(stored);
                state.config = { ...state.config, ...config };
                
                elements.apiBaseInput.value = state.config.apiBase || '';
                elements.modelSelect.value = state.config.model || 'yxi-7b-terminal';
                if (config.apiKey && config.apiKey !== '••••••••') {
                    elements.apiKeyInput.value = config.apiKey;
                }
            }
        } catch (error) {
            console.error('Error loading local config:', error);
        }
    }

    // ========================================
    // Initialization
    // ========================================
    function init() {
        console.log('Initializing yxi-chat-cli Web Interface...');
        
        setupEventListeners();
        loadLocalConfig();
        loadHistoryFromStorage();
        connectWebSocket();
        
        // Focus input after a short delay
        setTimeout(() => {
            if (state.messages.length === 0) {
                elements.messageInput.focus();
            }
        }, 500);
        
        console.log('yxi-chat-cli Web Interface initialized');
    }

    // Start the app when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
