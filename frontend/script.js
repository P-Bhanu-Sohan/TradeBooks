// script.js
const API_BASE_URL = 'http://localhost:8000';
const PROFIT_BOOK_ENDPOINT = '/api/profit-book';
const INITIAL_CAPITAL = 1000.00;
let pnlChart, volumeChart;
let isRefreshing = false;

// Debugging function
function debugLog(message, data = null) {
    console.log(`[DEBUG] ${new Date().toISOString()} - ${message}`);
    if (data) console.log(data);
}

// Initialize charts
function initCharts() {
    const pnlCtx = document.getElementById('pnlChart').getContext('2d');
    pnlChart = new Chart(pnlCtx, {
        type: 'line',
        data: { datasets: [{
            label: 'Cumulative P&L',
            borderColor: '#00e676',
            backgroundColor: 'rgba(0, 230, 118, 0.1)',
            borderWidth: 3,
            fill: true
        }]},
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: (context) => `$${context.parsed.y.toFixed(2)}`
                    }
                }
            }
        }
    });

    const volumeCtx = document.getElementById('volumeChart').getContext('2d');
    volumeChart = new Chart(volumeCtx, {
        type: 'bar',
        data: { datasets: [{
            label: 'Volume',
            backgroundColor: 'rgba(0, 198, 255, 0.7)',
            borderColor: 'rgba(0, 198, 255, 1)',
            borderWidth: 1
        }]},
        options: { responsive: true, maintainAspectRatio: false }
    });
}

// Update timestamp display
function updateTimestamp() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-IN', {hour12:false}) + ' IST';
    document.getElementById('timestamp').textContent = timeStr;
    document.getElementById('positionsTimestamp').textContent = `Last updated: ${timeStr}`;
}

// Fetch trades with enhanced error handling
async function fetchTrades() {
    try {
        debugLog('Fetching trades from API');
        const response = await fetch(API_BASE_URL + PROFIT_BOOK_ENDPOINT);
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        debugLog(`Received ${data.length} trades`, data);
        return data;
    } catch (error) {
        console.error('Fetch error:', error);
        showError(`API Connection Error: ${error.message}`);
        return [];
    }
}

// Display error message
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <div style="background: #ff5252; color: white; padding: 15px; border-radius: 5px; margin: 20px;">
            <strong>Error:</strong> ${message}
        </div>
    `;
    document.querySelector('.main-content').prepend(errorDiv);
    setTimeout(() => errorDiv.remove(), 5000);
}

// Calculate metrics from trades
function calculateMetrics(trades) {
    let totalPnl = 0;
    let tradesCount = trades.length;
    let winRate = 0;
    let portfolioValue = INITIAL_CAPITAL;

    if (trades.length > 0) {
        const lastTrade = trades[trades.length - 1];
        portfolioValue = parseFloat(lastTrade.equity) || INITIAL_CAPITAL;
        totalPnl = portfolioValue - INITIAL_CAPITAL;
        
        const winningTrades = trades.filter(t => {
            const tradePnl = parseFloat(t.equity) - INITIAL_CAPITAL;
            return tradePnl > 0;
        });
        
        winRate = tradesCount > 0 ? (winningTrades.length / tradesCount) * 100 : 0;
    }

    return {
        totalPnl,
        portfolioValue,
        tradesCount,
        winRate
    };
}

// Render metrics
function renderMetrics(metrics) {
    document.getElementById('total-pnl').textContent = `$${metrics.totalPnl.toFixed(2)}`;
    document.getElementById('portfolio-value').textContent = `$${metrics.portfolioValue.toFixed(2)}`;
    document.getElementById('trades-count').textContent = metrics.tradesCount;
    document.getElementById('win-rate').textContent = `${metrics.winRate.toFixed(1)}%`;
    
    // Set color based on P&L
    const pnlElement = document.getElementById('total-pnl');
    pnlElement.className = `metric-value ${metrics.totalPnl >= 0 ? 'positive' : 'negative'}`;
}

// Render positions table
function renderPositions(trades) {
    const positions = {};
    
    // Aggregate positions
    trades.forEach(trade => {
        const symbol = trade.symbol;
        if (!positions[symbol]) {
            positions[symbol] = {
                symbol: symbol,
                quantity: 0,
                avgPrice: 0,
                totalCost: 0
            };
        }
        
        const qty = parseInt(trade.qty);
        const price = parseFloat(trade.price);
        
        if (trade.action.includes('BUY')) {
            positions[symbol].quantity += qty;
            positions[symbol].totalCost += qty * price;
            positions[symbol].avgPrice = positions[symbol].totalCost / positions[symbol].quantity;
        } else {
            positions[symbol].quantity -= qty;
        }
    });
    
    // Generate HTML
    let tableHTML = '';
    let hasPositions = false;
    
    Object.keys(positions).forEach(symbol => {
        const position = positions[symbol];
        if (position.quantity !== 0) {
            hasPositions = true;
            const marketValue = position.quantity * position.avgPrice;
            const pnl = marketValue - position.totalCost;
            
            tableHTML += `
                <tr>
                    <td>${symbol}</td>
                    <td class="${position.quantity > 0 ? 'buy-action' : 'sell-action'}">
                        ${position.quantity > 0 ? 'BUY' : 'SELL'}
                    </td>
                    <td>$${position.avgPrice.toFixed(2)}</td>
                    <td>${Math.abs(position.quantity)}</td>
                    <td>$${marketValue.toFixed(2)}</td>
                    <td class="${pnl >= 0 ? 'positive' : 'negative'}">
                        ${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(2)}
                    </td>
                </tr>
            `;
        }
    });
    
    if (!hasPositions) {
        tableHTML = `<tr><td colspan="6" style="text-align:center;padding:40px;">No active positions</td></tr>`;
    }
    
    document.getElementById('positionsTableBody').innerHTML = tableHTML;
}

// Update charts
function updateCharts(trades) {
    if (trades.length === 0) {
        debugLog('No trades available for charting');
        return;
    }
    
    // P&L chart data
    const pnlLabels = [];
    const pnlData = [];
    
    trades.forEach(trade => {
        pnlLabels.push(new Date(trade.timestamp));
        pnlData.push(parseFloat(trade.equity) - INITIAL_CAPITAL);
    });
    
    pnlChart.data.labels = pnlLabels;
    pnlChart.data.datasets[0].data = pnlData;
    pnlChart.update();
    
    // Volume chart data
    const volumeData = {};
    trades.forEach(trade => {
        const symbol = trade.symbol;
        volumeData[symbol] = (volumeData[symbol] || 0) + Math.abs(parseInt(trade.qty));
    });
    
    volumeChart.data.labels = Object.keys(volumeData);
    volumeChart.data.datasets[0].data = Object.values(volumeData);
    volumeChart.update();
    
    debugLog('Charts updated successfully');
}

// Refresh data
async function refresh() {
    if (isRefreshing) return;
    isRefreshing = true;
    
    const refreshBtn = document.getElementById('refreshBtn');
    refreshBtn.disabled = true;
    const icon = refreshBtn.querySelector('i');
    icon.classList.add('fa-spin');
    
    try {
        const trades = await fetchTrades();
        debugLog(`Processing ${trades.length} trades`);
        
        const metrics = calculateMetrics(trades);
        renderMetrics(metrics);
        
        renderPositions(trades);
        updateCharts(trades);
        updateTimestamp();
        
        debugLog('Dashboard refresh complete');
    } catch (error) {
        console.error('Refresh error:', error);
        showError(`Refresh failed: ${error.message}`);
    } finally {
        refreshBtn.disabled = false;
        icon.classList.remove('fa-spin');
        isRefreshing = false;
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard initialized');
    initCharts();
    updateTimestamp();
    
    // Set up periodic refresh
    setInterval(updateTimestamp, 1000);
    setInterval(refresh, 10000);
    
    // Manual refresh
    document.getElementById('refreshBtn').addEventListener('click', refresh);
    
    // Initial load
    refresh();
});