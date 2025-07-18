// MCP Gateway Management UI JavaScript

class MCPGatewayUI {
    constructor() {
        this.eventSource = null;
        this.connectionStatus = 'disconnected';
        this.servers = new Map();
        this.tools = [];
        this.resources = [];
        this.events = [];
        this.maxEvents = 100;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.connectToEventStream();
        this.loadInitialData();
        
        // Ensure modal is hidden on page load
        document.getElementById('config-modal').classList.remove('show');
    }
    
    setupEventListeners() {
        // Search and filter
        document.getElementById('tools-search').addEventListener('input', () => this.filterTools());
        document.getElementById('tools-server-filter').addEventListener('change', () => this.filterTools());
        document.getElementById('resources-search').addEventListener('input', () => this.filterResources());
        document.getElementById('resources-server-filter').addEventListener('change', () => this.filterResources());
        
        // Event log controls
        document.getElementById('clear-events').addEventListener('click', () => this.clearEventLog());
        document.getElementById('test-sse').addEventListener('click', () => this.testSSE());
        
        // Server management controls
        document.getElementById('refresh-servers').addEventListener('click', () => this.refreshAll());
        document.getElementById('discover-servers').addEventListener('click', () => this.discoverServers());
        
        // Configuration editor controls
        document.getElementById('config-editor-btn').addEventListener('click', () => this.openConfigEditor());
        document.getElementById('config-modal-close').addEventListener('click', () => this.closeConfigEditor());
        document.getElementById('cancel-config-btn').addEventListener('click', () => this.closeConfigEditor());
        document.getElementById('save-config-btn').addEventListener('click', () => this.saveConfiguration());
        
        // Handle page visibility for reconnection
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.connectionStatus === 'disconnected') {
                this.connectToEventStream();
            }
        });
    }
    
    testSSE() {
        console.log('Testing SSE connection...');
        
        // Close existing connection if any
        if (this.eventSource) {
            this.eventSource.close();
        }
        
        // Create new test connection
        this.eventSource = new EventSource('/api/v1/debug/sse-test');
        
        this.eventSource.onopen = () => {
            console.log('Test SSE connection opened');
        };
        
        this.eventSource.onmessage = (event) => {
            console.log('Test SSE Raw message:', event.data);
            
            try {
                // Handle potential "data: " prefix
                let jsonData = event.data;
                if (jsonData.startsWith('data: ')) {
                    jsonData = jsonData.substring(6);
                }
                
                const data = JSON.parse(jsonData);
                console.log('Test SSE Parsed data:', data);
            } catch (e) {
                console.error('Test SSE Parse error:', e);
                console.error('Test SSE Raw data:', event.data);
                
                // Try fallback parsing
                try {
                    const match = event.data.match(/data: (.+)/);
                    if (match) {
                        const extractedData = JSON.parse(match[1]);
                        console.log('Test SSE Fallback parse successful:', extractedData);
                    }
                } catch (fallbackError) {
                    console.error('Test SSE Fallback parse failed:', fallbackError);
                }
            }
        };
        
        this.eventSource.onerror = (error) => {
            console.error('Test SSE error:', error);
        };
        
        // Auto-close after 10 seconds
        setTimeout(() => {
            if (this.eventSource) {
                this.eventSource.close();
                console.log('Test SSE connection closed');
            }
        }, 10000);
    }

    connectToEventStream() {
        if (this.eventSource) {
            this.eventSource.close();
        }
        
        this.updateConnectionStatus('connecting');
        
        this.eventSource = new EventSource('/api/v1/events');
        
        this.eventSource.onopen = () => {
            console.log('SSE connection opened');
            this.updateConnectionStatus('connected');
        };
        
        this.eventSource.onmessage = (event) => {
            console.log('Raw SSE message:', event.data); // Debug log
            
            try {
                // The EventSource API should automatically strip "data: " prefix,
                // but if it's still there, we need to handle it manually
                let jsonData = event.data;
                if (jsonData.startsWith('data: ')) {
                    jsonData = jsonData.substring(6); // Remove "data: " prefix
                }
                
                const data = JSON.parse(jsonData);
                console.log('Parsed SSE data:', data); // Debug log
                this.handleSSEEvent(data);
            } catch (e) {
                console.error('Error parsing SSE event:', e);
                console.error('Raw event data:', event.data);
                console.error('Event data type:', typeof event.data);
                console.error('Event data length:', event.data.length);
                console.error('First 100 chars:', event.data.substring(0, 100));
                
                // Try to extract JSON from the raw data if it contains "data: " prefix
                try {
                    const match = event.data.match(/data: (.+)/);
                    if (match) {
                        const extractedData = JSON.parse(match[1]);
                        console.log('Fallback parse successful:', extractedData);
                        this.handleSSEEvent(extractedData);
                    }
                } catch (fallbackError) {
                    console.error('Fallback parse also failed:', fallbackError);
                }
            }
        };
        
        this.eventSource.onerror = () => {
            console.error('SSE connection error');
            this.updateConnectionStatus('disconnected');
            
            // Attempt to reconnect after 5 seconds
            setTimeout(() => {
                if (this.connectionStatus === 'disconnected') {
                    this.connectToEventStream();
                }
            }, 5000);
        };
    }
    
    updateConnectionStatus(status) {
        this.connectionStatus = status;
        const indicator = document.getElementById('connection-indicator');
        const text = document.getElementById('connection-text');
        
        indicator.className = `status-indicator ${status}`;
        
        switch (status) {
            case 'connected':
                text.textContent = 'Connected';
                break;
            case 'connecting':
                text.textContent = 'Connecting...';
                break;
            case 'disconnected':
                text.textContent = 'Disconnected';
                break;
        }
    }
    
    handleSSEEvent(data) {
        console.log('SSE Event received:', data); // Debug log
        
        switch (data.type) {
            case 'initial_status':
            case 'status_update':
                console.log('Processing status update:', data.data); // Debug log
                this.updateGatewayStatus(data.data);
                break;
            case 'server_event':
                this.handleServerEvent(data.data);
                break;
            case 'metrics_update':
                this.updateMetrics(data.data);
                break;
            case 'tool_execution':
                this.addEvent('Tool Execution', `${data.data.tool_name} on ${data.data.server_name}`, data.data.success ? 'connected' : 'failed');
                break;
            case 'resource_access':
                this.addEvent('Resource Access', `${data.data.resource_uri} from ${data.data.server_name}`, data.data.success ? 'connected' : 'failed');
                break;
            case 'server_reconnection':
                this.addEvent('Reconnection', `${data.data.server_name}: ${data.data.message}`, data.data.success ? 'connected' : 'failed');
                break;
            case 'heartbeat':
                // Silent heartbeat
                break;
            default:
                console.log('Unknown SSE event type:', data.type);
        }
    }
    
    updateGatewayStatus(data) {
        console.log('updateGatewayStatus called with:', data); // Debug log
        
        // Update gateway metrics
        if (data.gateway) {
            document.getElementById('total-servers').textContent = data.gateway.total_servers || 0;
            document.getElementById('active-servers').textContent = data.gateway.active_servers || 0;
            document.getElementById('total-tools').textContent = data.gateway.total_tools || 0;
            document.getElementById('total-resources').textContent = data.gateway.total_resources || 0;
            document.getElementById('uptime').textContent = data.gateway.uptime || '0s';
            
            const lastUpdated = new Date(data.gateway.last_updated).toLocaleTimeString();
            document.getElementById('last-updated').textContent = lastUpdated;
        }
        
        // Update servers
        if (data.servers) {
            console.log('Server data received:', data.servers); // Debug log
            console.log('Number of servers:', data.servers.length); // Debug log
            this.updateServers(data.servers);
        } else {
            console.warn('No servers data in SSE event'); // Debug log
        }
        
        // Update aggregation stats
        if (data.aggregation) {
            // Could display additional aggregation statistics
        }
    }
    
    updateServers(serversData) {
        console.log('updateServers called with:', serversData);
        console.log('serversData is array?', Array.isArray(serversData));
        console.log('serversData length:', serversData ? serversData.length : 'undefined');
        
        this.servers.clear();
        
        if (serversData && Array.isArray(serversData)) {
            serversData.forEach(server => {
                console.log('Adding server to Map:', server.name, server);
                this.servers.set(server.name, server);
            });
        }
        
        console.log('Total servers in Map:', this.servers.size);
        console.log('Servers Map contents:', [...this.servers.entries()]);
        
        this.renderServers();
        this.updateServerFilters();
    }
    
    renderServers() {
        console.log('renderServers called, servers.size:', this.servers.size);
        const container = document.getElementById('servers-container');
        console.log('Container element:', container);
        container.innerHTML = '';
        
        if (this.servers.size === 0) {
            console.log('No servers, showing empty state');
            container.innerHTML = '<div class="empty-state"><div class="icon">🔌</div><p>No MCP servers found</p><p>Click "Discover" to scan for local MCP configurations</p></div>';
            return;
        }
        
        console.log('Rendering', this.servers.size, 'servers');
        this.servers.forEach(server => {
            console.log('Creating card for server:', server.name);
            const serverCard = this.createServerCard(server);
            container.appendChild(serverCard);
        });
    }
    
    createServerCard(server) {
        const card = document.createElement('div');
        card.className = `server-card ${(server.status === 'active' || server.status === 'connected') ? 'connected' : 'disconnected'}`;
        
        const toolsCount = server.tools ? server.tools.length : 0;
        const resourcesCount = server.resources ? server.resources.length : 0;
        const lastPing = server.last_ping ? new Date(server.last_ping).toLocaleTimeString() : 'Never';
        const serverSource = server.source || 'unknown';
        
        card.innerHTML = `
            <div class="server-source ${serverSource}">${serverSource.toUpperCase()}</div>
            
            <div class="server-header">
                <div class="server-name">${server.name}</div>
            </div>
            
            <div class="server-status">
                <span class="server-status-dot ${(server.status === 'active' || server.status === 'connected') ? 'connected' : 'disconnected'}"></span>
                <span>${(server.status === 'active' || server.status === 'connected') ? 'Connected' : 'Disconnected'}</span>
            </div>
            
            <div class="server-info">
                <div class="server-info-item">
                    <span class="server-info-label">URL:</span>
                    <span class="server-info-value">${server.url}</span>
                </div>
                <div class="server-info-item">
                    <span class="server-info-label">Tools:</span>
                    <span class="server-info-value">${toolsCount}</span>
                </div>
                <div class="server-info-item">
                    <span class="server-info-label">Resources:</span>
                    <span class="server-info-value">${resourcesCount}</span>
                </div>
                <div class="server-info-item">
                    <span class="server-info-label">Last Ping:</span>
                    <span class="server-info-value">${lastPing}</span>
                </div>
            </div>
            
            ${server.status === 'failed' ? `
                <div class="server-actions">
                    <button class="btn btn-primary btn-small" onclick="mcpUI.reconnectServer('${server.name}')">
                        Reconnect
                    </button>
                </div>
            ` : ''}
            ${server.last_error ? `
                <div style="margin-top: 8px; padding: 8px; background: rgba(239, 68, 68, 0.1); border-radius: 4px; font-size: 0.75rem; color: var(--error-color);">
                    ${server.last_error}
                </div>
            ` : ''}
            
            <label class="server-toggle server-toggle-bottom-right">
                <input type="checkbox" ${server.enabled ? 'checked' : ''} 
                       onchange="mcpUI.toggleServer('${server.name}', this.checked)">
                <span class="toggle-slider"></span>
            </label>
        `;
        
        return card;
    }
    
    updateServerFilters() {
        const toolsFilter = document.getElementById('tools-server-filter');
        const resourcesFilter = document.getElementById('resources-server-filter');
        
        // Clear existing options (except "All Servers")
        toolsFilter.innerHTML = '<option value="">All Servers</option>';
        resourcesFilter.innerHTML = '<option value="">All Servers</option>';
        
        // Add server options
        this.servers.forEach(server => {
            const toolOption = document.createElement('option');
            toolOption.value = server.name;
            toolOption.textContent = server.name;
            toolsFilter.appendChild(toolOption);
            
            const resourceOption = document.createElement('option');
            resourceOption.value = server.name;
            resourceOption.textContent = server.name;
            resourcesFilter.appendChild(resourceOption);
        });
    }
    
    handleServerEvent(eventData) {
        this.addEvent(
            eventData.event_type,
            `${eventData.server_name}: ${eventData.message}`,
            eventData.event_type
        );
    }
    
    addEvent(type, message, status = 'info') {
        const event = {
            timestamp: new Date(),
            type: type,
            message: message,
            status: status
        };
        
        this.events.unshift(event);
        
        // Limit events
        if (this.events.length > this.maxEvents) {
            this.events = this.events.slice(0, this.maxEvents);
        }
        
        this.renderEvents();
    }
    
    renderEvents() {
        const container = document.getElementById('event-log');
        container.innerHTML = '';
        
        if (this.events.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="icon">📋</div><p>No events</p></div>';
            return;
        }
        
        this.events.forEach(event => {
            const eventItem = document.createElement('div');
            eventItem.className = 'event-item';
            
            eventItem.innerHTML = `
                <div class="event-timestamp">${event.timestamp.toLocaleTimeString()}</div>
                <div class="event-type ${event.status}">${event.type}</div>
                <div class="event-message">${event.message}</div>
            `;
            
            container.appendChild(eventItem);
        });
        
        // Auto-scroll if enabled
        if (document.getElementById('auto-scroll').checked) {
            container.scrollTop = 0;
        }
    }
    
    clearEventLog() {
        this.events = [];
        this.renderEvents();
    }
    
    async loadInitialData() {
        try {
            // Load servers
            await this.refreshServers();
            
            // Load tools and resources
            await this.refreshTools();
            await this.refreshResources();
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }
    
    async refreshTools() {
        try {
            console.log('Refreshing tools...');
            const toolsResponse = await fetch('/api/v1/tools');
            if (toolsResponse.ok) {
                const toolsData = await toolsResponse.json();
                this.tools = toolsData.tools || [];
                console.log(`Tools refreshed: ${this.tools.length} tools found`);
                this.renderTools();
            }
        } catch (error) {
            console.error('Error refreshing tools:', error);
        }
    }
    
    async refreshResources() {
        try {
            console.log('Refreshing resources...');
            const resourcesResponse = await fetch('/api/v1/resources');
            if (resourcesResponse.ok) {
                const resourcesData = await resourcesResponse.json();
                this.resources = resourcesData.resources || [];
                console.log(`Resources refreshed: ${this.resources.length} resources found`);
                this.renderResources();
            }
        } catch (error) {
            console.error('Error refreshing resources:', error);
        }
    }
    
    filterTools() {
        const searchTerm = document.getElementById('tools-search').value.toLowerCase();
        const serverFilter = document.getElementById('tools-server-filter').value;
        
        let filtered = this.tools;
        
        if (searchTerm) {
            filtered = filtered.filter(tool =>
                tool.prefixed_name.toLowerCase().includes(searchTerm) ||
                tool.original_name.toLowerCase().includes(searchTerm) ||
                tool.description.toLowerCase().includes(searchTerm)
            );
        }
        
        if (serverFilter) {
            filtered = filtered.filter(tool => tool.server_name === serverFilter);
        }
        
        this.renderTools(filtered);
    }
    
    renderTools(tools = this.tools) {
        const container = document.getElementById('tools-container');
        const countElement = document.getElementById('tools-count');
        
        countElement.textContent = `${tools.length} tools`;
        
        if (tools.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="icon">🔧</div><p>No tools found</p></div>';
            return;
        }
        
        container.innerHTML = '';
        tools.forEach(tool => {
            const toolCard = this.createToolCard(tool);
            container.appendChild(toolCard);
        });
    }
    
    createToolCard(tool) {
        const card = document.createElement('div');
        card.className = 'tool-card';
        
        const paramCount = Object.keys(tool.parameters?.properties || {}).length;
        
        card.innerHTML = `
            <div class="tool-header">
                <div class="tool-name">${tool.prefixed_name}</div>
                <div class="server-badge">${tool.server_name}</div>
            </div>
            <div class="tool-description">${tool.description}</div>
            <div class="tool-details">
                Original: ${tool.original_name} | Parameters: ${paramCount}
            </div>
        `;
        
        return card;
    }
    
    filterResources() {
        const searchTerm = document.getElementById('resources-search').value.toLowerCase();
        const serverFilter = document.getElementById('resources-server-filter').value;
        
        let filtered = this.resources;
        
        if (searchTerm) {
            filtered = filtered.filter(resource =>
                resource.prefixed_uri.toLowerCase().includes(searchTerm) ||
                resource.original_uri.toLowerCase().includes(searchTerm) ||
                resource.name.toLowerCase().includes(searchTerm) ||
                (resource.description && resource.description.toLowerCase().includes(searchTerm))
            );
        }
        
        if (serverFilter) {
            filtered = filtered.filter(resource => resource.server_name === serverFilter);
        }
        
        this.renderResources(filtered);
    }
    
    renderResources(resources = this.resources) {
        const container = document.getElementById('resources-container');
        const countElement = document.getElementById('resources-count');
        
        countElement.textContent = `${resources.length} resources`;
        
        if (resources.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="icon">📁</div><p>No resources found</p></div>';
            return;
        }
        
        container.innerHTML = '';
        resources.forEach(resource => {
            const resourceCard = this.createResourceCard(resource);
            container.appendChild(resourceCard);
        });
    }
    
    createResourceCard(resource) {
        const card = document.createElement('div');
        card.className = 'resource-card';
        
        card.innerHTML = `
            <div class="resource-header">
                <div class="resource-name">${resource.prefixed_uri}</div>
                <div class="server-badge">${resource.server_name}</div>
            </div>
            <div class="resource-description">${resource.description || 'No description'}</div>
            <div class="resource-details">
                Original: ${resource.original_uri}${resource.mime_type ? ` | Type: ${resource.mime_type}` : ''}
            </div>
        `;
        
        return card;
    }
    
    async reconnectServer(serverName) {
        try {
            this.showNotification('Reconnecting server...', 'info');
            
            const response = await fetch(`/api/v1/servers/${serverName}/reconnect`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showNotification(
                    `Server ${serverName}: ${result.message}`,
                    result.success ? 'success' : 'error'
                );
                
                // Refresh servers, tools, and resources after successful reconnection
                if (result.success) {
                    setTimeout(async () => {
                        this.refreshServers();
                        this.refreshTools();
                        this.refreshResources();
                    }, 100);
                }
            } else {
                this.showNotification('Reconnection failed', 'error');
            }
        } catch (error) {
            console.error('Reconnection error:', error);
            this.showNotification('Reconnection failed', 'error');
        }
    }
    
    async toggleServer(serverName, enabled) {
        try {
            const action = enabled ? 'enable' : 'disable';
            this.showNotification(`${action === 'enable' ? 'Enabling' : 'Disabling'} server ${serverName}...`, 'info');
            
            const response = await fetch(`/api/v1/servers/${serverName}/${action}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                this.showNotification(
                    `Server ${serverName} ${action}d successfully`,
                    'success'
                );
                // Refresh the servers display and tools/resources with a small delay
                // to ensure backend aggregation is complete
                setTimeout(async () => {
                    this.refreshServers();
                    this.refreshTools();
                    this.refreshResources();
                }, 100);
            } else {
                this.showNotification(`Failed to ${action} server ${serverName}`, 'error');
                // Refresh to revert the toggle state
                this.refreshServers();
            }
        } catch (error) {
            console.error(`Error toggling server ${serverName}:`, error);
            this.showNotification(`Error toggling server ${serverName}`, 'error');
            // Refresh to revert the toggle state
            this.refreshServers();
        }
    }
    
    // Server Management Methods
    
    async refreshServers() {
        try {
            const response = await fetch('/api/v1/servers', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('Servers response:', data); // Debug log
                console.log('Number of servers:', data.servers ? data.servers.length : 0); // Debug log
                console.log('First server:', data.servers ? data.servers[0] : 'none'); // Debug log
                
                this.updateServers(data.servers);  // Use updateServers for consistency
                this.showNotification('Servers refreshed successfully', 'success');
            } else {
                console.error('Failed to refresh servers:', response.status, response.statusText);
                this.showNotification('Failed to refresh servers', 'error');
            }
        } catch (error) {
            console.error('Error refreshing servers:', error);
            this.showNotification('Error refreshing servers', 'error');
        }
    }
    
    async refreshAll() {
        await this.refreshServers();
        await this.refreshTools();
        await this.refreshResources();
    }
    
    async discoverServers() {
        try {
            const response = await fetch('/api/v1/servers/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.showNotification(`Discovery completed: ${data.data.discovered_count} servers found`, 'success');
                // Refresh the display
                this.refreshServers();
            } else {
                this.showNotification('Failed to discover servers', 'error');
            }
        } catch (error) {
            console.error('Error discovering servers:', error);
            this.showNotification('Error discovering servers', 'error');
        }
    }
    
    updateServersDisplay(servers) {
        const container = document.getElementById('servers-container');
        
        if (!servers || servers.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No MCP servers found</p>
                    <p>Click "Discover" to scan for local MCP configurations</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = servers.map(server => `
            <div class="server-card ${(server.status === 'active' || server.status === 'connected') ? 'connected' : 'disconnected'}">
                <div class="server-source ${server.source || 'unknown'}">${(server.source || 'UNKNOWN').toUpperCase()}</div>
                
                <div class="server-header">
                    <div class="server-name">${server.name}</div>
                    <label class="server-toggle">
                        <input type="checkbox" ${server.enabled ? 'checked' : ''} 
                               onchange="mcpUI.toggleServer('${server.name}', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                
                <div class="server-status">
                    <span class="server-status-dot ${server.status === 'active' ? 'connected' : 'disconnected'}"></span>
                    <span>${server.status === 'active' ? 'Connected' : 'Disconnected'}</span>
                </div>
                
                <div class="server-info">
                    <div class="server-info-item">
                        <span class="server-info-label">URL:</span>
                        <span class="server-info-value">${server.url}</span>
                    </div>
                    <div class="server-info-item">
                        <span class="server-info-label">Timeout:</span>
                        <span class="server-info-value">${server.timeout}s</span>
                    </div>
                    <div class="server-info-item">
                        <span class="server-info-label">Max Retries:</span>
                        <span class="server-info-value">${server.max_retries}</span>
                    </div>
                    <div class="server-info-item">
                        <span class="server-info-label">Source:</span>
                        <span class="server-info-value">${server.source}</span>
                    </div>
                </div>
                
                <div class="server-actions">
                    <button class="btn btn-small btn-secondary" 
                            onclick="mcpUI.refreshServers()">
                        🔄 Refresh
                    </button>
                </div>
            </div>
        `).join('');
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 5000);
    }
    
    updateMetrics(metricsData) {
        // Could update additional metrics displays
        // For now, just log the metrics
        console.log('Metrics update:', metricsData);
    }
    
    destroy() {
        if (this.eventSource) {
            this.eventSource.close();
        }
    }

    // Configuration Editor Methods
    async openConfigEditor() {
        this.addEvent('info', 'Opening configuration editor...');
        
        try {
            // Load current configuration
            const response = await fetch('/api/v1/config');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const config = await response.json();
            
            // Store original config for reset
            this.originalConfig = JSON.stringify(config, null, 2);
            
            // Populate editor
            const editor = document.getElementById('config-editor');
            editor.value = this.originalConfig;
            
            // Show modal
            document.getElementById('config-modal').classList.add('show');
            
            // Update status
            this.updateConfigStatus('Configuration loaded successfully', 'success');
            
        } catch (error) {
            console.error('Error loading configuration:', error);
            this.addEvent('error', `Failed to load configuration: ${error.message}`);
            this.updateConfigStatus('Failed to load configuration', 'error');
        }
    }

    closeConfigEditor() {
        document.getElementById('config-modal').classList.remove('show');
        this.updateConfigStatus('Ready', '');
    }



    async saveConfiguration() {
        try {
            const editor = document.getElementById('config-editor');
            const configText = editor.value;
            
            // Validate JSON
            const config = JSON.parse(configText);
            
            // Basic validation
            if (!config.mcpServers || typeof config.mcpServers !== 'object') {
                throw new Error('Configuration must have an "mcpServers" object');
            }
            
            this.updateConfigStatus('Saving configuration...', '');
            
            // Save configuration
            const response = await fetch('/api/v1/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: configText
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            this.updateConfigStatus('Configuration saved successfully', 'success');
            this.addEvent('info', `Configuration updated: ${result.data.updated_servers} servers configured`);
            
            // Close modal after success
            setTimeout(() => {
                this.closeConfigEditor();
                // Refresh the UI to show updated servers
                this.refreshAll();
            }, 1500);
            
        } catch (error) {
            console.error('Error saving configuration:', error);
            this.updateConfigStatus(`Save failed: ${error.message}`, 'error');
            this.addEvent('error', `Failed to save configuration: ${error.message}`);
        }
    }

    updateConfigStatus(message, type) {
        const statusElement = document.getElementById('config-status-text');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.className = `config-status ${type}`;
        }
    }
}

// Initialize the UI when the page loads
let mcpUI;

document.addEventListener('DOMContentLoaded', () => {
    mcpUI = new MCPGatewayUI();
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (mcpUI) {
        mcpUI.destroy();
    }
});