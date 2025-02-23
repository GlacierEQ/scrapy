// Theme Management
function initTheme() {
    const theme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeToggleIcon(theme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeToggleIcon(newTheme);
}

function updateThemeToggleIcon(theme) {
    const icon = document.getElementById('theme-toggle-icon');
    icon.textContent = theme === 'light' ? '🌙' : '☀️';
}

// Form Management
function showForm(formType) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    event.currentTarget.classList.add('active');
    
    document.querySelectorAll('.form-container').forEach(form => form.classList.remove('active'));
    document.getElementById(formType + 'Form').classList.add('active');
    
    hideStatus();
    clearResults();
}

// Status Management
function showStatus(message, success) {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = message;
    statusDiv.className = 'status ' + (success ? 'success' : 'error');
    statusDiv.style.display = 'block';
    
    if (success) {
        setTimeout(hideStatus, 5000);
    }
}

function hideStatus() {
    const statusDiv = document.getElementById('status');
    statusDiv.style.display = 'none';
}

// Loading State Management
function showLoading() {
    document.getElementById('loading').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

// Results Management
function clearResults() {
    document.getElementById('results').innerHTML = '';
}

function displayResults(data) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = ''; // Clear previous results
    
    if (!data.pages || data.pages.length === 0) {
        showStatus('No results found', false);
        return;
    }
    
    data.pages.forEach(page => {
        const card = createResultCard(page);
        resultsDiv.appendChild(card);
    });
    
    if (data.compiled_report) {
        const compiledCard = createCompiledReportCard(data.compiled_report);
        resultsDiv.appendChild(compiledCard);
    }

    // Animate cards appearance
    document.querySelectorAll('.result-card').forEach((card, index) => {
        card.style.animation = `fadeIn 0.3s ease forwards ${index * 0.1}s`;
    });
}

function createResultCard(page) {
    const card = document.createElement('div');
    card.className = 'result-card';
    
    let content = `
        <div class="result-header">
            <h3 title="${page.url}">${truncateUrl(page.url, 40)}</h3>
            ${page.timestamp ? `<span class="timestamp">${formatDate(page.timestamp)}</span>` : ''}
        </div>
    `;
    
    if (page.screenshot_path) {
        content += `
            <div class="screenshot-container">
                <img src="/view/${page.screenshot_path}" alt="Screenshot" loading="lazy">
            </div>
        `;
    }
    
    if (page.analysis) {
        content += createAnalysisSection(page.analysis);
    }
    
    content += createActionLinks(page);
    
    card.innerHTML = content;
    return card;
}

function createAnalysisSection(analysis) {
    return `
        <div class="analysis-section">
            <h4>Analysis Summary</h4>
            <div class="analysis-grid">
                <div class="analysis-item" title="Total word count">
                    <span class="analysis-label">Words</span>
                    <span class="analysis-value">${analysis.content_analysis.word_count}</span>
                </div>
                <div class="analysis-item" title="Number of images found">
                    <span class="analysis-label">Images</span>
                    <span class="analysis-value">${analysis.content_analysis.images}</span>
                </div>
                <div class="analysis-item" title="Total number of links">
                    <span class="analysis-label">Links</span>
                    <span class="analysis-value">${analysis.link_analysis.total_links}</span>
                </div>
            </div>
        </div>
    `;
}

function createActionLinks(page) {
    return `
        <div class="result-links">
            ${page.html_path ? `
                <a href="/download/${page.html_path}" target="_blank" class="tooltip">
                    <span class="tooltip-text">Download HTML content</span>
                    📥 HTML
                </a>
            ` : ''}
            ${page.report_path ? `
                <a href="/download/${page.report_path}" target="_blank" class="tooltip">
                    <span class="tooltip-text">View detailed analysis report</span>
                    📊 Report
                </a>
            ` : ''}
            ${page.generated_image ? `
                <a href="/view/${page.generated_image}" target="_blank" class="tooltip">
                    <span class="tooltip-text">View AI generated image</span>
                    🎨 Image
                </a>
            ` : ''}
        </div>
    `;
}

function createCompiledReportCard(reportPath) {
    const card = document.createElement('div');
    card.className = 'result-card compiled-report';
    card.innerHTML = `
        <h3>Full Analysis Report</h3>
        <div class="result-links">
            <a href="/download/${reportPath}" target="_blank" class="tooltip">
                <span class="tooltip-text">Download complete analysis report</span>
                📊 Download Report
            </a>
        </div>
    `;
    return card;
}

// Form Submission Handlers
async function handleJefsSubmit(event) {
    event.preventDefault();
    await handleSubmit(event.target, '/scrape');
}

async function handleGeneralSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    formData.set('followLinks', form.followLinks.checked);
    formData.set('compileText', form.compileText.checked);
    await handleSubmit(form, '/scrape_general', formData);
}

async function handleSubmit(form, endpoint, formData = new FormData(form)) {
    hideStatus();
    clearResults();
    showLoading();
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showStatus(result.message, true);
            if (result.data) {
                displayResults(result.data);
            }
        } else {
            showStatus(result.message || 'An error occurred', false);
        }
    } catch (error) {
        showStatus('An error occurred while processing your request', false);
        console.error('Submission error:', error);
    } finally {
        hideLoading();
    }
}

// Utility Functions
function truncateUrl(url, maxLength) {
    if (url.length <= maxLength) return url;
    return url.substring(0, maxLength - 3) + '...';
}

function formatDate(timestamp) {
    return new Date(timestamp).toLocaleString();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    
    // Add event listeners for form submissions
    document.getElementById('scrapeJefsForm')?.addEventListener('submit', handleJefsSubmit);
    document.getElementById('scrapeGeneralForm')?.addEventListener('submit', handleGeneralSubmit);
    
    // Initialize tooltips if needed
    document.querySelectorAll('.tooltip').forEach(tooltip => {
        // Add any custom tooltip initialization here if needed
    });
});
