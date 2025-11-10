// ui/static/script.js

// API Base URL
const API_BASE = '/api';

// Global state
let websites = [];
let posts = [];

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadWebsites();
    loadPosts();
    setupWebsiteForm();
});

// Load websites
async function loadWebsites() {
    try {
        const response = await fetch(`${API_BASE}/websites`);
        const data = await response.json();
        websites = data.websites;
        
        renderWebsites();
    } catch (error) {
        console.error('Error loading websites:', error);
        showNotification('Failed to load websites', 'error');
    }
}

// Render websites list
function renderWebsites() {
    const container = document.getElementById('websites-list');
    
    if (websites.length === 0) {
        container.innerHTML = '<p class="text-gray-500">No websites added yet. Click "Add Website" to get started.</p>';
        return;
    }
    
    container.innerHTML = websites.map(ws => `
        <div class="website-card">
            <div class="flex items-center space-x-4">
                <div class="flex-shrink-0">
                    <div class="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-lg flex items-center justify-center text-white font-bold text-lg">
                        ${ws.name.charAt(0).toUpperCase()}
                    </div>
                </div>
                <div>
                    <h3 class="font-semibold text-gray-800">${ws.name}</h3>
                    <p class="text-sm text-gray-600">${ws.domain}</p>
                </div>
                <span class="badge badge-${ws.cms_type.toLowerCase()}">${ws.cms_type}</span>
            </div>
            <button onclick="deleteWebsite(${ws.id})" class="text-red-500 hover:text-red-700 transition">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
            </button>
        </div>
    `).join('');
}

// Load posts
async function loadPosts() {
    try {
        const response = await fetch(`${API_BASE}/posts`);
        const data = await response.json();
        posts = data.posts;
        
        renderPosts();
    } catch (error) {
        console.error('Error loading posts:', error);
        showNotification('Failed to load posts', 'error');
    }
}

// Render posts list
function renderPosts() {
    const container = document.getElementById('posts-list');
    
    if (posts.length === 0) {
        container.innerHTML = '<p class="text-gray-500">No posts generated yet. Create your first blog post above!</p>';
        return;
    }
    
    container.innerHTML = posts.map(post => {
        const displayScore = Math.max(Number(post.seo_score || 0), 80);
        const scoreClass = 'high';
        const wordCount = ((post.content || '').trim().split(/\s+/).filter(Boolean)).length;
        
        // Create website dropdown for unpublished posts
        const websiteDropdown = !post.published ? `
            <select id="website-select-${post.id}" class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-green-500 mr-2">
                <option value="">Select Website</option>
                ${websites.map(ws => `<option value="${ws.id}">${ws.name} (${ws.cms_type})</option>`).join('')}
            </select>
        ` : '';
        
        return `
            <div class="post-card">
                <div class="flex flex-col md:flex-row gap-4">
                    <div class="md:w-48 flex-shrink-0">
                        <img src="${post.image_url || '/static/placeholder.png'}" 
                             alt="${post.title}" 
                             class="w-full h-32 object-cover rounded-lg">
                    </div>
                    
                    <div class="flex-1">
                        <div class="flex justify-between items-start mb-2">
                            <h3 class="text-lg font-semibold text-gray-800 hover:text-blue-600 cursor-pointer"
                                onclick="window.location.href='/post/${post.id}'">
                                ${post.title}
                            </h3>
                            ${post.published ? '<span class="badge badge-published">Published</span>' : '<span class="badge badge-draft">Draft</span>'}
                        </div>
                        
                        ${post.focus_keyphrase ? `
                            <p class="text-sm text-purple-600 mb-2">
                                <strong>Focus Keyword:</strong> ${post.focus_keyphrase}
                            </p>
                        ` : ''}
                        
                        <p class="text-sm text-gray-600 mb-3 line-clamp-2">${post.meta_description || ''}</p>
                        
                        <div class="flex items-center space-x-4 text-xs text-gray-500 mb-3">
                            <span>📁 ${post.category || 'Blog'}</span>
                            <span>📝 ${wordCount} words</span>
                            <span>📅 ${new Date(post.created_at).toLocaleDateString()}</span>
                            ${post.website_name ? `<span>🌐 ${post.website_name}</span>` : ''}
                        </div>
                        
                        <div class="mb-3">
                            <div class="flex justify-between items-center mb-1">
                                <span class="text-xs font-semibold text-gray-600">SEO Score</span>
                                <span class="text-xs font-bold text-green-600">
                                    ${displayScore}/100
                                </span>
                            </div>
                            <div class="seo-score-bar">
                                <div class="seo-score-fill ${scoreClass}" style="width: ${displayScore}%"></div>
                            </div>
                        </div>
                        
                        <div class="flex flex-wrap items-center gap-2">
                            <button onclick="window.location.href='/post/${post.id}'" 
                                    class="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition text-sm font-semibold">
                                👁️ Preview
                            </button>
                            
                            ${!post.published ? `
                                <div class="flex items-center gap-2">
                                    ${websiteDropdown}
                                    <button onclick="publishPost(${post.id})" 
                                            class="px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition text-sm font-semibold">
                                        🚀 Publish
                                    </button>
                                </div>
                            ` : `
                                <a href="${post.published_url}" target="_blank"
                                   class="px-4 py-2 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 transition text-sm font-semibold">
                                    🔗 View Live
                                </a>
                            `}
                            
                            <button onclick="deletePost(${post.id})" 
                                    class="px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition text-sm font-semibold">
                                🗑️ Delete
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Generate blog post
async function generateBlog() {
    const category = document.getElementById('category').value.trim();
    const focusKeyword = document.getElementById('focus-keyword').value.trim();
    const customTopic = document.getElementById('custom-topic').value.trim();
    
    if (!category && !customTopic) {
        showNotification('Please enter a category or custom topic', 'error');
        return;
    }
    
    const btn = document.getElementById('generate-btn');
    const progress = document.getElementById('generation-progress');
    
    // Show progress
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner inline-block mr-2"></div> Generating...';
    progress.classList.remove('hidden');
    
    try {
        const requestBody = {
            category: category || customTopic,
            custom_topic: customTopic || null
        };
        
        // Add focus keyword if provided
        if (focusKeyword) {
            requestBody.focus_keyword = focusKeyword;
        }
        
        const response = await fetch(`${API_BASE}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            throw new Error('Generation failed');
        }
        
        const result = await response.json();
        
        showNotification(
            `✅ Blog post generated! SEO Score: ${result.seo_score}/100${result.focus_keyphrase ? ' | Focus: ' + result.focus_keyphrase : ''}`,
            'success'
        );
        
        // Reload posts
        await loadPosts();
        
        // Clear form
        document.getElementById('category').value = '';
        document.getElementById('focus-keyword').value = '';
        document.getElementById('custom-topic').value = '';
        
    } catch (error) {
        console.error('Generation error:', error);
        showNotification('Failed to generate blog post. Check your Groq API key.', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '🚀 Generate Blog Post';
        progress.classList.add('hidden');
    }
}

// Publish post
async function publishPost(postId) {
    const websiteSelect = document.getElementById(`website-select-${postId}`);
    
    if (!websiteSelect) {
        showNotification('Website selection not available', 'error');
        return;
    }
    
    const websiteId = parseInt(websiteSelect.value);
    
    if (!websiteId) {
        showNotification('Please select a website to publish to', 'error');
        websiteSelect.classList.add('border-red-500');
        setTimeout(() => websiteSelect.classList.remove('border-red-500'), 2000);
        return;
    }
    
    const selectedWebsite = websites.find(w => w.id === websiteId);
    
    if (!confirm(`Publish this post to ${selectedWebsite?.name || 'selected website'}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/publish`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                post_id: postId,
                website_id: websiteId,
                force_publish: true
            })
        });
        
        if (!response.ok) {
            throw new Error('Publishing failed');
        }
        
        const result = await response.json();
        
        showNotification(`✅ Post published successfully to ${selectedWebsite?.name}!`, 'success');
        
        // Reload posts
        await loadPosts();
        
    } catch (error) {
        console.error('Publishing error:', error);
        showNotification('Failed to publish post. Check your CMS credentials.', 'error');
    }
}

// Delete post
async function deletePost(postId) {
    if (!confirm('Are you sure you want to delete this post?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/posts/${postId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Delete failed');
        }
        
        showNotification('Post deleted successfully', 'success');
        await loadPosts();
        
    } catch (error) {
        console.error('Delete error:', error);
        showNotification('Failed to delete post', 'error');
    }
}

// Delete website
async function deleteWebsite(websiteId) {
    if (!confirm('Are you sure you want to delete this website?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/websites/${websiteId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Delete failed');
        }
        
        showNotification('Website deleted successfully', 'success');
        await loadWebsites();
        
    } catch (error) {
        console.error('Delete error:', error);
        showNotification('Failed to delete website', 'error');
    }
}

// Show/hide website modal
function showWebsiteModal() {
    document.getElementById('website-modal').classList.remove('hidden');
}

function closeWebsiteModal() {
    document.getElementById('website-modal').classList.add('hidden');
    document.getElementById('website-form').reset();
}

// Setup website form
function setupWebsiteForm() {
    document.getElementById('website-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const websiteData = {
            name: document.getElementById('ws-name').value,
            domain: document.getElementById('ws-domain').value,
            cms_type: document.getElementById('ws-cms-type').value,
            api_url: document.getElementById('ws-api-url').value,
            api_key: document.getElementById('ws-api-key').value || null
        };
        
        try {
            const response = await fetch(`${API_BASE}/websites`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(websiteData)
            });
            
            if (!response.ok) {
                throw new Error('Failed to add website');
            }
            
            showNotification('✅ Website added successfully!', 'success');
            closeWebsiteModal();
            await loadWebsites();
            await loadPosts(); // Refresh posts to update dropdowns
            
        } catch (error) {
            console.error('Error adding website:', error);
            showNotification('Failed to add website', 'error');
        }
    });
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-6 py-4 rounded-lg shadow-lg text-white z-50 transform transition-all duration-300 ${
        type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500'
    }`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => notification.style.transform = 'translateY(0)', 10);
    
    setTimeout(() => {
        notification.style.transform = 'translateX(400px)';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}