// Tailwind CSS Configuration
tailwind.config = {
    theme: {
        extend: {
            colors: {
                'custom-purple': '#6D5BD0',
                'custom-light-purple': '#F0EEFF',
                'custom-background': '#F8F9FE',
                'custom-gray': '#A0AEC0',
                'custom-dark-gray': '#4A5568',
                'custom-light-gray': '#F7FAFC',
                'custom-green': '#48BB78',
                'custom-red': '#F56565',
            },
            fontFamily: {
                inter: ['Inter', 'sans-serif'],
            },
        }
    }
};

// Main script execution after the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function () {
    
    // --- Live Time Functionality ---
    const timeElement = document.getElementById('live-time');
    function updateTime() {
        const now = new Date();
        const options = { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true };
        if(timeElement) {
            timeElement.textContent = now.toLocaleDateString('en-US', options).replace(',', '');
        }
    }
    updateTime();
    setInterval(updateTime, 60000); // Update every minute

    // --- NEW: Data Fetching and Rendering Functions ---

    // Fetch and render all recent orders
    const fetchAllOrders = () => {
        const tableBody = document.getElementById('all-orders-table-body');
        if (!tableBody) return;
        tableBody.innerHTML = '<tr><td colspan="6" class="p-4 text-center">Loading...</td></tr>'; // Show loading state

        fetch('/api/all_orders')
            .then(response => response.json())
            .then(data => {
                tableBody.innerHTML = ''; // Clear loading/previous data
                if (data.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-gray-500">No orders found.</td></tr>';
                    return;
                }
                data.forEach(order => {
                    const statusClass = order.STATUS === 'SUCCESSFUL' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-yellow-100 text-yellow-800';
                    const statusText = order.STATUS === 'SUCCESSFUL' ? 'Delivered' : 'Pending';

                    const row = `
                        <tr class="border-b border-gray-100">
                            <td class="p-2 font-semibold">#${order.BILL_ID}</td>
                            <td class="p-2">${order.CUSTOMER_NAME}</td>
                            <td class="p-2">Rs ${order.TOTAL_AMOUNT.toFixed(2)}</td>
                            <td class="p-2">${order.PAYMENT_DATE}</td>
                            <td class="p-2">${order.PAYMENT_METHOD}</td>
                            <td class="p-2">
                                <span class="${statusClass} text-xs font-medium px-2 py-0.5 rounded-full">${statusText}</span>
                            </td>
                        </tr>
                    `;
                    tableBody.insertAdjacentHTML('beforeend', row);
                });
            })
            .catch(error => {
                console.error('Error fetching all orders:', error);
                tableBody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-red-500">Failed to load orders.</td></tr>';
            });
    };

    // Fetch and render all recent dues
    const fetchAllDues = () => {
        const dueList = document.getElementById('all-dues-list');
        if (!dueList) return;
        dueList.innerHTML = '<li class="text-center p-4">Loading...</li>';

        fetch('/api/all_dues')
            .then(response => response.json())
            .then(data => {
                dueList.innerHTML = '';
                if (data.length === 0) {
                    dueList.innerHTML = '<li class="text-sm text-center text-gray-500 py-4">No outstanding dues.</li>';
                    return;
                }
                data.forEach(due => {
                    const avatarLetter = due.CUSTOMER_NAME ? due.CUSTOMER_NAME[0].toUpperCase() : '?';
                    const item = `
                        <li class="flex items-center justify-between text-sm">
                            <div class="flex items-center">
                                <img src="https://placehold.co/28x28/E2E8F0/4A5568?text=${avatarLetter}" alt="Avatar" class="rounded-full mr-2">
                                <span>${due.CUSTOMER_NAME}</span>
                            </div>
                            <div class="text-right">
                                <p class="font-semibold text-xs">₹ ${due.unpaid_amount.toFixed(2)}</p>
                                <p class="text-xs text-custom-gray">${due.due_date}</p>
                            </div>
                        </li>
                    `;
                    dueList.insertAdjacentHTML('beforeend', item);
                });
            })
            .catch(error => {
                console.error('Error fetching all dues:', error);
                dueList.innerHTML = '<li class="text-center p-4 text-red-500">Failed to load dues.</li>';
            });
    };

    // Fetch and render all order statuses
    const fetchAllStatuses = () => {
        const statusList = document.getElementById('all-status-list');
        if(!statusList) return;
        statusList.innerHTML = '<li class="text-center p-4">Loading...</li>';

        fetch('/api/all_statuses')
            .then(response => response.json())
            .then(data => {
                statusList.innerHTML = '';
                 if (data.length === 0) {
                    statusList.innerHTML = '<li class="text-sm text-center text-gray-500 py-4">No status data available.</li>';
                    return;
                }
                data.forEach(status => {
                     const item = `
                        <li class="flex items-center justify-between text-sm p-2 rounded-lg hover:bg-gray-50">
                            <span class="font-semibold text-gray-700">${status.status}</span>
                            <span class="bg-custom-light-purple text-custom-purple font-bold text-xs px-2 py-1 rounded-full">${status.count}</span>
                        </li>
                    `;
                    statusList.insertAdjacentHTML('beforeend', item);
                });
            })
             .catch(error => {
                console.error('Error fetching all statuses:', error);
                statusList.innerHTML = '<li class="text-center p-4 text-red-500">Failed to load statuses.</li>';
            });
    };

    // --- Main Content View Switching ---
    const dashboardView = document.getElementById('dashboard-view');
    const allOrdersView = document.getElementById('all-orders-view');
    const seeAllOrdersBtn = document.getElementById('see-all-orders-btn');
    const backToDashboardBtns = document.querySelectorAll('.back-to-dashboard-btn');

    if (seeAllOrdersBtn) {
        seeAllOrdersBtn.addEventListener('click', () => {
            fetchAllOrders(); // <-- ADDED THIS CALL
            dashboardView.classList.add('hidden');
            allOrdersView.classList.remove('hidden');
            allOrdersView.classList.add('flex');
        });
    }

    backToDashboardBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            allOrdersView.classList.add('hidden');
            allOrdersView.classList.remove('flex');
            dashboardView.classList.remove('hidden');
        });
    });

    // --- Right Sidebar View Switching ---
    const summaryView = document.getElementById('summary-view');
    const allDuesView = document.getElementById('all-dues-view');
    const allStatusView = document.getElementById('all-status-view');
    const seeAllDuesBtn = document.getElementById('see-all-dues-btn');
    const seeAllStatusBtn = document.getElementById('see-all-status-btn');
    const backToSummaryBtns = document.querySelectorAll('.back-to-summary-btn');

    if (seeAllDuesBtn) {
        seeAllDuesBtn.addEventListener('click', () => {
            fetchAllDues(); // <-- ADDED THIS CALL
            summaryView.classList.add('hidden');
            allDuesView.classList.remove('hidden');
            allDuesView.classList.add('flex');
        });
    }

    if (seeAllStatusBtn) {
        seeAllStatusBtn.addEventListener('click', () => {
            fetchAllStatuses(); // <-- ADDED THIS CALL
            summaryView.classList.add('hidden');
            allStatusView.classList.remove('hidden');
            allStatusView.classList.add('flex');
        });
    }

    backToSummaryBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            allDuesView.classList.add('hidden');
            allDuesView.classList.remove('flex');
            allStatusView.classList.add('hidden');
            allStatusView.classList.remove('flex');
            summaryView.classList.remove('hidden');
        });
    });

    // --- Chart.js Configurations (No changes here) ---

    // Finance Flow Chart
    const financeFlowCtx = document.getElementById('financeFlowChart');
    if (financeFlowCtx && typeof salesReportData !== 'undefined') {
        new Chart(financeFlowCtx, {
            type: 'line',
            data: {
                labels: salesReportData.labels,
                datasets: [{
                    label: 'Finance Flow',
                    data: salesReportData.flow_data,
                    borderColor: '#6D5BD0',
                    backgroundColor: 'rgba(109, 91, 208, 0.2)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: { 
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });
    }

    // Total Order Chart
    const totalOrderCtx = document.getElementById('totalOrderChart');
    if (totalOrderCtx && typeof salesReportData !== 'undefined') {
        new Chart(totalOrderCtx, {
            type: 'line',
            data: {
                labels: salesReportData.labels,
                datasets: [{
                    label: 'Orders',
                    data: salesReportData.order_count_data,
                    borderColor: '#48BB78',
                    backgroundColor: 'rgba(72, 187, 120, 0.2)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: { 
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });
    }

    // Category Doughnut Chart
    const categoryCtx = document.getElementById('categoryChart');
    if (categoryCtx && typeof categoryChartData !== 'undefined') {
        new Chart(categoryCtx, {
            type: 'doughnut',
            data: {
                labels: categoryChartData.labels,
                datasets: [{
                    data: categoryChartData.data,
                    backgroundColor: ['#3B82F6', '#8B5CF6', '#D1D5DB'],
                    borderWidth: 1
                }]
            },
            options: { 
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    // Order Status Doughnut Chart
    const statusCtx = document.getElementById('statusChart');
    if(statusCtx && typeof statusChartData !== 'undefined') {
        new Chart(statusCtx, {
            type: 'doughnut',
            data: {
                labels: statusChartData.labels,
                datasets: [{
                    data: statusChartData.data,
                    backgroundColor: ['#48BB78', '#F6AD55'],
                    borderWidth: 1
                }]
            },
            options: { 
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                 plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
});