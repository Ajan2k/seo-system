// ui/static/script.js – Production Dashboard JS
// ════════════════════════════════════════════════════════════════

'use strict';

const API = '/api';

// ── State ─────────────────────────────────────────────────────────────
let _sites = [];
let _posts = [];
let _filteredPosts = [];

// ── API Fetch Wrapper ───────────────────────────────────────────────────
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('blogai_token');
    const headers = { ...options.headers };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return fetch(url, { ...options, headers });
}

// ── Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([loadWebsites(), loadPosts()]);
    await checkApiStatus();
    setupKeyboardShortcuts();
});

// ── Keyboard Shortcuts ────────────────────────────────────────────────
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            closeWebsiteModal();
        }
        // Ctrl/Cmd + Enter to generate
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            const btn = document.getElementById('generate-btn');
            if (btn && !btn.disabled) generateBlog();
        }
    });
}

// ── API Status ────────────────────────────────────────────────────────
async function checkApiStatus() {
    try {
        const res = await fetch('/health');
        const data = await res.json();
        const el = document.getElementById('api-status');
        if (data.status === 'healthy') {
            el.innerHTML = '<span class="status-dot"></span><span class="status-text">Connected</span>';
        } else {
            el.innerHTML = '<span class="status-dot" style="background:var(--warning)"></span><span class="status-text">Degraded</span>';
        }
    } catch {
        const el = document.getElementById('api-status');
        el.innerHTML = '<span class="status-dot" style="background:var(--danger)"></span><span class="status-text">Offline</span>';
    }
}

// ── Navigation ────────────────────────────────────────────────────────
function setActiveNav(el) {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

// ── Stats ─────────────────────────────────────────────────────────────
function updateStats() {
    const total = _posts.length;
    const published = _posts.filter(p => p.published).length;
    const avgSeo = total
        ? Math.round(_posts.reduce((s, p) => s + (p.seo_score || 0), 0) / total)
        : 0;
    const sites = _sites.length;

    animateNumber('stat-total-posts', total);
    animateNumber('stat-published', published);
    animateNumber('stat-avg-seo', avgSeo);
    animateNumber('stat-websites', sites);

    document.getElementById('posts-count').textContent = total;
    document.getElementById('sites-count').textContent = sites;
}

function animateNumber(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    const start = parseInt(el.textContent) || 0;
    const step = Math.ceil(Math.abs(target - start) / 20) || 1;
    let current = start;

    const tick = () => {
        current += (current < target ? step : -step);
        if ((step > 0 && current >= target) || (step < 0 && current <= target)) {
            el.textContent = target;
            return;
        }
        el.textContent = current;
        requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
}

// ── Websites ──────────────────────────────────────────────────────────
async function loadWebsites() {
    try {
        const res = await fetchWithAuth(`${API}/websites`);
        const data = await res.json();
        _sites = data.websites || [];
        renderWebsites();
        updateStats();
    } catch (err) {
        console.error('loadWebsites:', err);
        toast('Failed to load websites', 'error');
    }
}

function renderWebsites() {
    const container = document.getElementById('websites-list');
    if (!_sites.length) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column:1/-1">
                <div class="empty-icon">🌐</div>
                <div class="empty-title">No websites connected</div>
                <div class="empty-sub">Add a WordPress or Ghost site to start publishing</div>
            </div>`;
        return;
    }

    container.innerHTML = _sites.map(ws => `
        <div class="website-card" id="ws-${ws.id}">
            <div class="ws-header">
                <div class="ws-avatar">${esc(ws.name.charAt(0).toUpperCase())}</div>
                <div>
                    <div class="ws-name">${esc(ws.name)}</div>
                    <div class="ws-domain">${esc(ws.domain)}</div>
                </div>
            </div>
            <div class="ws-footer">
                <span class="badge badge-${ws.cms_type.toLowerCase()}">${esc(ws.cms_type)}</span>
                <button class="ws-delete" onclick="deleteWebsite(${ws.id})" aria-label="Delete website">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

async function deleteWebsite(id) {
    if (!confirm('Delete this website? Published posts will remain on the CMS.')) return;
    try {
        const res = await fetchWithAuth(`${API}/websites/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Delete failed');
        toast('Website removed', 'success');
        await loadWebsites();
        renderPosts(); // refresh dropdowns
    } catch (err) {
        toast('Failed to delete website', 'error');
    }
}

// ── Website Modal ─────────────────────────────────────────────────────
function showWebsiteModal() {
    document.getElementById('website-modal').classList.remove('hidden');
}

function closeWebsiteModal() {
    document.getElementById('website-modal').classList.add('hidden');
    document.getElementById('website-form').reset();
}

function handleModalClick(e) {
    if (e.target === e.currentTarget) closeWebsiteModal();
}

async function submitWebsiteForm(e) {
    e.preventDefault();
    const payload = {
        name: document.getElementById('ws-name').value.trim(),
        domain: document.getElementById('ws-domain').value.trim(),
        cms_type: document.getElementById('ws-cms-type').value,
        api_url: document.getElementById('ws-api-url').value.trim(),
        api_key: document.getElementById('ws-api-key').value.trim() || null,
    };
    try {
        const res = await fetchWithAuth(`${API}/websites`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error('Failed');
        toast('Website added!', 'success');
        closeWebsiteModal();
        await loadWebsites();
        renderPosts();
    } catch {
        toast('Failed to add website', 'error');
    }
}

// ── Posts ─────────────────────────────────────────────────────────────
async function loadPosts() {
    try {
        const res = await fetchWithAuth(`${API}/posts`);
        const data = await res.json();
        _posts = data.posts || [];
        _filteredPosts = [..._posts];
        renderPosts();
        updateStats();
    } catch (err) {
        console.error('loadPosts:', err);
        toast('Failed to load posts', 'error');
    }
}

function filterPosts(query) {
    const q = (query ?? document.getElementById('search-posts').value).toLowerCase();
    const status = document.getElementById('filter-status').value;

    _filteredPosts = _posts.filter(p => {
        const matchText = !q || p.title.toLowerCase().includes(q) || (p.focus_keyphrase || '').toLowerCase().includes(q);
        const matchStatus = !status
            || (status === 'published' && p.published)
            || (status === 'draft' && !p.published);
        return matchText && matchStatus;
    });
    renderPosts();
}

function renderPosts() {
    const container = document.getElementById('posts-list');
    if (!_filteredPosts.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📝</div>
                <div class="empty-title">${_posts.length ? 'No matching posts' : 'No posts yet'}</div>
                <div class="empty-sub">${_posts.length ? 'Try a different search term' : 'Generate your first AI-powered blog post above'}</div>
            </div>`;
        return;
    }

    container.innerHTML = _filteredPosts.map(post => {
        const score = Math.max(Number(post.seo_score || 0), 0);
        const scoreLabel = score >= 80 ? 'high' : score >= 60 ? 'medium' : 'low';
        const wordCount = ((post.content || '').trim().split(/\s+/).filter(Boolean)).length;

        const siteDropdown = !post.published
            ? `<select id="ws-sel-${post.id}" class="form-input" style="padding:6px 10px;font-size:0.8rem;border-radius:6px;width:auto;">
                   <option value="">Select Website…</option>
                   ${_sites.map(s => `<option value="${s.id}">${esc(s.name)} (${esc(s.cms_type)})</option>`).join('')}
               </select>`
            : '';

        return `
        <div class="post-item" id="post-${post.id}">
            ${post.image_url
                ? `<img class="post-thumb" src="${esc(post.image_url)}" alt="${esc(post.title)}" loading="lazy" onerror="this.style.display='none'">`
                : `<div class="post-thumb-placeholder">📄</div>`}
            <div class="post-body">
                <div class="post-top">
                    <div class="post-title" onclick="window.location.href='/post/${post.id}'">${esc(post.title)}</div>
                    <span class="badge badge-${post.published ? 'published' : 'draft'}">${post.published ? 'Published' : 'Draft'}</span>
                </div>
                ${post.focus_keyphrase
                ? `<div class="post-keyphrase">🔑 <span>${esc(post.focus_keyphrase)}</span></div>`
                : ''}
                <div class="post-meta-desc">${esc(post.meta_description || '')}</div>
                <div class="post-stats">
                    <span>📁 ${esc(post.category || 'Blog')}</span>
                    <span>📝 ${wordCount.toLocaleString()} words</span>
                    <span>📅 ${formatDate(post.created_at)}</span>
                    ${post.website_name ? `<span>🌐 ${esc(post.website_name)}</span>` : ''}
                </div>
                <div class="seo-bar-wrap">
                    <span class="seo-bar-label">SEO Score</span>
                    <div class="seo-bar-track">
                        <div class="seo-bar-fill ${scoreLabel}" style="width:${score}%"></div>
                    </div>
                    <span class="seo-bar-value ${scoreLabel}">${score}</span>
                </div>
                <div class="post-actions">
                    <button class="btn btn-info btn-sm" onclick="window.location.href='/post/${post.id}'">👁 Preview</button>
                    ${!post.published
                ? `${siteDropdown}
                           <button class="btn btn-success btn-sm" onclick="publishPost(${post.id})">🚀 Publish</button>`
                : `<a href="${esc(post.published_url || '#')}" target="_blank" class="btn btn-outline btn-sm">🔗 View Live</a>`}
                    <button class="btn btn-danger btn-sm" onclick="deletePost(${post.id})">🗑 Delete</button>
                </div>
            </div>
        </div>`;
    }).join('');
}

// ── Generate Blog ─────────────────────────────────────────────────────
async function generateBlog() {
    const category = document.getElementById('category').value.trim();
    const focusKw = document.getElementById('focus-keyword').value.trim();
    const customTopic = document.getElementById('custom-topic').value.trim();
    const brandName = document.getElementById('brand-name')?.value.trim() || 'Infinitetechai';
    const targetScore = parseInt(document.getElementById('target-score')?.value || '80', 10);

    if (!category && !customTopic) {
        toast('Please enter a category or custom topic', 'error');
        document.getElementById('category').focus();
        return;
    }

    const btn = document.getElementById('generate-btn');
    const progress = document.getElementById('generation-progress');
    const steps = ['step-1', 'step-2', 'step-3', 'step-4', 'step-5'];
    const msgs = [
        'Fetching trending topics…',
        'Calling LLaMA 3.3 AI…',
        'Optimizing SEO score…',
        'Generating featured image…',
        'Saving to database…',
    ];
    const pcts = [15, 40, 65, 85, 100];

    btn.disabled = true;
    btn.innerHTML = `<div class="progress-spinner" style="width:18px;height:18px;border-width:2px"></div> Generating…`;
    progress.classList.remove('hidden');

    steps.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.className = 'step';
    });

    // Simulate step progression
    let stepIdx = 0;
    const stepInterval = setInterval(() => {
        if (stepIdx > 0) {
            const prev = document.getElementById(steps[stepIdx - 1]);
            if (prev) prev.className = 'step done';
        }
        if (stepIdx < steps.length) {
            const cur = document.getElementById(steps[stepIdx]);
            if (cur) cur.className = 'step active';
            document.getElementById('progress-message').textContent = msgs[stepIdx];
            document.getElementById('progress-bar').style.width = pcts[stepIdx] + '%';
            stepIdx++;
        }
    }, 18_000 / steps.length);

    try {
        const body = {
            category: category || customTopic,
            custom_topic: customTopic || null,
            brand_name: brandName,
            target_score: targetScore,
        };
        if (focusKw) body.focus_keyword = focusKw;

        const res = await fetchWithAuth(`${API}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const text = await res.text();

        if (!res.ok) {
            let errMsg = 'Generation failed to start';
            try { errMsg = JSON.parse(text).detail || errMsg; } catch { /* */ }
            throw new Error(errMsg);
        }

        const initialResult = JSON.parse(text);

        if (!initialResult.task_id) {
            throw new Error("Invalid response from server (missing task_id)");
        }

        const taskId = initialResult.task_id;
        let isPolling = true;
        let finalResult = null;

        while (isPolling) {
            await new Promise(r => setTimeout(r, 5000)); // Poll every 5 seconds

            const statusRes = await fetchWithAuth(`${API}/generate/status/${taskId}`);
            const statusText = await statusRes.text();

            if (!statusRes.ok) {
                let errMsg = 'Status check failed';
                try { errMsg = JSON.parse(statusText).detail || errMsg; } catch { /* */ }
                throw new Error(errMsg);
            }

            const result = JSON.parse(statusText);

            if (result.status === 'completed') {
                isPolling = false;
                finalResult = result;
            } else if (result.status === 'failed') {
                isPolling = false;
                throw new Error(result.detail || "Background blog generation failed");
            }
            // If processing, loop around
        }

        clearInterval(stepInterval);
        steps.forEach(id => { const el = document.getElementById(id); if (el) el.className = 'step done'; });
        document.getElementById('progress-bar').style.width = '100%';

        const result = finalResult;

        toast(
            `Blog post generated! SEO Score: ${result.seo_score}/100${result.focus_keyphrase ? ' · Focus: ' + result.focus_keyphrase : ''
            }`,
            'success',
            8000,
        );

        // Clear form
        ['category', 'focus-keyword', 'custom-topic'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });

        await loadPosts();
    } catch (err) {
        clearInterval(stepInterval);
        toast(err.message || 'Generation failed. Check your Groq API key.', 'error', 8000);
        console.error('generateBlog:', err);
    } finally {
        await new Promise(r => setTimeout(r, 800));
        btn.disabled = false;
        btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            Generate Blog Post`;
        progress.classList.add('hidden');
        document.getElementById('progress-bar').style.width = '0%';
    }
}

// ── Publish Post ──────────────────────────────────────────────────────
async function publishPost(postId) {
    const selectEl = document.getElementById(`ws-sel-${postId}`);
    if (!selectEl) { toast('Website selector not found', 'error'); return; }

    const websiteId = parseInt(selectEl.value, 10);
    if (!websiteId) {
        toast('Please select a website first', 'error');
        selectEl.style.borderColor = 'var(--danger)';
        setTimeout(() => selectEl.style.borderColor = '', 2000);
        return;
    }

    const site = _sites.find(s => s.id === websiteId);
    if (!confirm(`Publish this post to "${site?.name || 'selected website'}"?`)) return;

    try {
        const res = await fetchWithAuth(`${API}/publish`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ post_id: postId, website_id: websiteId, force_publish: true }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Publish failed');

        toast(`Published to ${site?.name}!`, 'success');
        await loadPosts();
    } catch (err) {
        toast(err.message || 'Failed to publish. Check your CMS credentials.', 'error');
    }
}

// ── Delete Post ───────────────────────────────────────────────────────
async function deletePost(postId) {
    if (!confirm('Delete this post permanently?')) return;
    try {
        const res = await fetchWithAuth(`${API}/posts/${postId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Delete failed');
        toast('Post deleted', 'success');
        await loadPosts();
    } catch {
        toast('Failed to delete post', 'error');
    }
}

// ── Toast Notifications ───────────────────────────────────────────────
function toast(message, type = 'info', duration = 5000) {
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    const titles = { success: 'Success', error: 'Error', info: 'Info', warning: 'Warning' };

    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `
        <span class="toast-icon">${icons[type] || '•'}</span>
        <div class="toast-body">
            <div class="toast-title">${titles[type] || type}</div>
            <div class="toast-message">${esc(message)}</div>
        </div>
        <button class="toast-dismiss" onclick="dismissToast(this.parentElement)">×</button>
    `;

    document.getElementById('toast-container').appendChild(el);

    setTimeout(() => dismissToast(el), duration);
}

function dismissToast(el) {
    if (!el || el.classList.contains('leaving')) return;
    el.classList.add('leaving');
    setTimeout(() => el.remove(), 260);
}

// ── Helpers ───────────────────────────────────────────────────────────
function esc(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatDate(iso) {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
        return iso.split('T')[0];
    }
}