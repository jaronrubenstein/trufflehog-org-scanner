"""Report compilation module for TruffleHog organization scans.

This module processes individual repository scan JSON files, merges them,
sorts results prioritizing compromised repositories, and generates a beautifully-designed,
responsive, and fully accessible light-mode-by-default HTML summary dashboard.
"""

import os
import json
from typing import Any

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TruffleHog Scan Dashboard</title>
    <style>
        :root {
            /* Brand Slate Light Theme (Subtle blue-slate neutral tinting) */
            --bg-primary: #f1f3f5;
            --bg-secondary: #ffffff;
            --text-primary: #1a1e21;
            --text-secondary: #5a626a;
            --border-color: #e2e6ea;
            --color-pass: #198754;
            --color-fail: #dc3545;
            --color-warn: #fd7e14;
            --color-info: #0d6efd;
            --shadow: 0 4px 6px rgba(13, 110, 253, 0.03), 0 1px 3px rgba(0, 0, 0, 0.02);
            --transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        [data-theme="dark"] {
            /* Brand Slate Dark Theme */
            --bg-primary: #0f1114;
            --bg-secondary: #171a1f;
            --text-primary: #f1f3f5;
            --text-secondary: #8a949d;
            --border-color: #2d3139;
            --shadow: 0 4px 6px rgba(0, 0, 0, 0.25), 0 1px 3px rgba(0, 0, 0, 0.15);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            margin: 0;
            padding: 2rem 1rem;
            transition: var(--transition);
            line-height: 1.5;
        }

        @media (min-width: 768px) {
            body {
                padding: 2.5rem 2rem;
            }
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
        }

        h1 { 
            margin: 0; 
            font-size: 1.75rem; 
            font-weight: 800;
            letter-spacing: -0.025em;
        }
        @media (min-width: 576px) {
            h1 { font-size: 2.25rem; }
        }

        .theme-toggle {
            cursor: pointer;
            padding: 0.6rem 1.2rem;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-weight: 600;
            box-shadow: var(--shadow);
            transition: var(--transition);
        }
        .theme-toggle:hover {
            border-color: var(--color-info);
            transform: translateY(-1px);
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }

        .card {
            background: var(--bg-secondary);
            padding: 1.5rem;
            border-radius: 12px;
            box-shadow: var(--shadow);
            border: 1px solid var(--border-color);
            transition: var(--transition);
        }
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 12px rgba(0, 0, 0, 0.05);
        }

        .card-title {
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 0.5rem;
            font-weight: 700;
            letter-spacing: 0.05em;
        }

        .card-value {
            font-size: 2.25rem;
            font-weight: 800;
            line-height: 1;
        }

        /* Elegant Top Border Accents */
        .card.pass { border-top: 4px solid var(--color-pass); }
        .card.fail { border-top: 4px solid var(--color-fail); }
        .card.info { border-top: 4px solid var(--color-info); }
        .card.warn { border-top: 4px solid var(--color-warn); }

        .controls {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }

        .search-input {
            flex: 1;
            min-width: 280px;
            padding: 0.75rem 1.25rem;
            border-radius: 10px;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            color: var(--text-primary);
            font-size: 1rem;
            box-shadow: var(--shadow);
            transition: var(--transition);
        }
        .search-input:focus {
            outline: none;
            border-color: var(--color-info);
            box-shadow: 0 0 0 3px rgba(13, 110, 253, 0.15);
        }

        .filter-btn {
            padding: 0.75rem 1.25rem;
            border-radius: 10px;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            color: var(--text-primary);
            cursor: pointer;
            font-weight: 700;
            font-size: 0.95rem;
            box-shadow: var(--shadow);
            transition: var(--transition);
        }
        .filter-btn:hover {
            border-color: var(--color-info);
        }
        .filter-btn.active {
            background: var(--color-info);
            color: white;
            border-color: var(--color-info);
        }

        .repo-row {
            background: var(--bg-secondary);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            margin-bottom: 1rem;
            box-shadow: var(--shadow);
            overflow: hidden;
            transition: var(--transition);
        }

        .repo-header {
            padding: 1.25rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            transition: var(--transition);
        }
        .repo-header:hover {
            background-color: var(--bg-primary);
        }
        .repo-header:focus-visible {
            outline: none;
            box-shadow: inset 0 0 0 3px var(--color-info);
        }

        .repo-info {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .repo-name {
            font-weight: 700;
            font-size: 1.1rem;
            letter-spacing: -0.01em;
        }

        .badge {
            padding: 0.3rem 0.75rem;
            border-radius: 30px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }

        .badge.pass { background: #d1e7dd; color: #0f5132; }
        .badge.fail { background: #f8d7da; color: #842029; }
        .badge.private { background: #e2e3e5; color: #41464b; }

        .findings-detail {
            display: none;
            padding: 1.5rem;
            border-top: 1px solid var(--border-color);
            background: var(--bg-primary);
            transition: var(--transition);
        }

        .findings-detail.active { display: block; }

        /* Responsive Table Container */
        .table-container {
            width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            margin-top: 1rem;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 600px;
        }

        th, td {
            text-align: left;
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.95rem;
        }

        tr:last-child td {
            border-bottom: none;
        }

        th {
            color: var(--text-secondary);
            font-weight: 700;
            background: var(--bg-primary);
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 0.05em;
        }

        .secret-masked {
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            background: #e9ecef;
            padding: 0.25rem 0.5rem;
            border-radius: 6px;
            font-size: 0.85rem;
            border: 1px solid var(--border-color);
        }
        [data-theme="dark"] .secret-masked {
            background: #2b3035;
        }
        
        pre {
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            background: #f8d7da;
            color: #842029;
            padding: 1rem;
            border-radius: 8px;
            margin: 0;
            overflow-x: auto;
        }
        [data-theme="dark"] pre {
            background: #2c0b0e;
            color: #ea868f;
        }
    </style>
</head>
<body data-theme="light">
    <div class="container">
        <header class="header">
            <h1>🛡️ TruffleHog Scan Dashboard</h1>
            <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle dark/light mode">🌓 Dark Mode</button>
        </header>

        <section class="stats-grid" aria-label="Scan Statistics">
            <div class="card info">
                <div class="card-title">Scanned Repositories</div>
                <div class="card-value" id="stat-scanned">0</div>
            </div>
            <div class="card pass">
                <div class="card-title">Clean Repositories</div>
                <div class="card-value" id="stat-clean">0</div>
            </div>
            <div class="card fail">
                <div class="card-title">Compromised</div>
                <div class="card-value" id="stat-compromised">0</div>
            </div>
            <div class="card warn">
                <div class="card-title">Total Secrets Found</div>
                <div class="card-value" id="stat-secrets">0</div>
            </div>
        </section>

        <section class="controls" aria-label="Controls and Filters">
            <input type="text" class="search-input" id="search-input" placeholder="Search repositories..." oninput="filterRepos()" aria-label="Search repositories">
            <button class="filter-btn active" id="btn-all" onclick="setFilter('all')">All</button>
            <button class="filter-btn" id="btn-clean" onclick="setFilter('clean')">Clean</button>
            <button class="filter-btn" id="btn-compromised" onclick="setFilter('compromised')">Compromised</button>
        </section>

        <main id="repo-list" aria-label="Repository Scan Results"></main>
    </div>

    <script>
        const scanData = __SCAN_DATA_PLACEHOLDER__;
        let activeFilter = 'all';

        function init() {
            let scanned = scanData.length;
            let clean = scanData.filter(r => r.scan_status === 'clean').length;
            let compromised = scanData.filter(r => r.scan_status === 'compromised').length;
            let totalSecrets = scanData.reduce((acc, r) => acc + (r.findings ? r.findings.length : 0), 0);

            document.getElementById('stat-scanned').innerText = scanned;
            document.getElementById('stat-clean').innerText = clean;
            document.getElementById('stat-compromised').innerText = compromised;
            document.getElementById('stat-secrets').innerText = totalSecrets;

            renderList();
        }

        function renderList() {
            const container = document.getElementById('repo-list');
            container.innerHTML = '';
            
            const searchTerm = document.getElementById('search-input').value.toLowerCase();

            scanData.forEach((repo, idx) => {
                const matchesSearch = repo.repo_name.toLowerCase().includes(searchTerm);
                const matchesFilter = activeFilter === 'all' || repo.scan_status === activeFilter;

                if (!matchesSearch || !matchesFilter) return;

                const row = document.createElement('div');
                row.className = 'repo-row';

                let findingsHTML = '<p style="margin: 0; font-weight: 500;">No findings. Repository is clean.</p>';
                if (repo.findings && repo.findings.length > 0) {
                    findingsHTML = `
                        <div class="table-container">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Detector</th>
                                        <th>File Path</th>
                                        <th>Line</th>
                                        <th>Commit</th>
                                        <th>Masked Key</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${repo.findings.map(f => `
                                        <tr>
                                            <td><strong>${escapeHTML(f.detector)}</strong></td>
                                            <td><code>${escapeHTML(f.file)}</code></td>
                                            <td>${f.line}</td>
                                            <td><code>${escapeHTML((f.commit || '').substring(0, 8))}</code></td>
                                            <td><span class="secret-masked">${escapeHTML(f.redacted)}</span></td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                } else if (repo.error) {
                    findingsHTML = `<pre>Error scanning repo: ${escapeHTML(repo.error)}</pre>`;
                }

                row.innerHTML = `
                    <div class="repo-header" 
                         role="button" 
                         tabindex="0" 
                         aria-expanded="false"
                         aria-controls="detail-${idx}"
                         onclick="toggleDetail(${idx})" 
                         onkeydown="handleHeaderKey(event, ${idx})">
                        <div class="repo-info">
                            <span class="repo-name">${escapeHTML(repo.repo_name)}</span>
                            ${repo.is_private ? '<span class="badge private">Private</span>' : ''}
                        </div>
                        <div>
                            <span class="badge ${repo.scan_status === 'clean' ? 'pass' : 'fail'}">
                                ${repo.scan_status === 'clean' ? 'PASSED' : 'COMPROMISED'}
                            </span>
                        </div>
                    </div>
                    <div class="findings-detail" id="detail-${idx}">
                        ${findingsHTML}
                    </div>
                `;
                container.appendChild(row);
            });
        }

        function toggleDetail(idx) {
            const el = document.getElementById(`detail-${idx}`);
            const header = el.previousElementSibling;
            const isExpanding = !el.classList.contains('active');
            
            el.classList.toggle('active');
            header.setAttribute('aria-expanded', isExpanding ? 'true' : 'false');
        }

        function handleHeaderKey(event, idx) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                toggleDetail(idx);
            }
        }

        function filterRepos() {
            renderList();
        }

        function setFilter(filter) {
            activeFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(`btn-${filter}`).classList.add('active');
            renderList();
        }

        function toggleTheme() {
            const body = document.body;
            const current = body.getAttribute('data-theme');
            const target = current === 'dark' ? 'light' : 'dark';
            body.setAttribute('data-theme', target);
            document.querySelector('.theme-toggle').innerText = target === 'dark' ? '☀️ Light Mode' : '🌓 Dark Mode';
        }

        function escapeHTML(str) {
            if (!str) return '';
            return str.replace(/[&<>'"]/g, 
                tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
            );
        }

        window.onload = init;
    </script>
</body>
</html>
"""

def generate_html_report(output_dir: str) -> str:
    """Collects individual JSON repository scan results and builds a cohesive summary HTML page.
    
    Loads all JSON reports from the output_dir/repos/ subdirectory,
    sorts findings to prioritize compromised repositories, saves a combined summary.json,
    and writes the final summary.html.
    """
    results = []
    
    repos_dir = os.path.join(output_dir, "repos")
    
    # Securely list directory and parse JSON scan files
    if os.path.exists(repos_dir):
        for filename in os.listdir(repos_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(repos_dir, filename)
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        # Basic validation to verify schema
                        if "repo_name" in data and "scan_status" in data:
                            results.append(data)
                except Exception:
                    # Ignore unreadable/corrupted files gracefully as per robustness specifications
                    continue
                
    # Sort results prioritizing 'compromised' status, then alphabetically by name
    results.sort(key=lambda x: (x.get("scan_status") != "compromised", x.get("repo_name", "")))
    
    # Save a global dataset for programmatic consumption
    summary_path = os.path.join(output_dir, "summary.json")
    try:
        with open(summary_path, "w") as f:
            json.dump(results, f, indent=2)
    except IOError:
        pass
        
    # Generate interactive light-mode HTML file
    html_content = HTML_TEMPLATE.replace("__SCAN_DATA_PLACEHOLDER__", json.dumps(results))
    html_path = os.path.join(output_dir, "summary.html")
    with open(html_path, "w") as f:
        f.write(html_content)
        
    return html_path
