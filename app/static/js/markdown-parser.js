/**
 * Markdown Parser Configuration
 * Configures marked.js with security and rendering options
 */

(function() {
    'use strict';

    // Configure marked options
    marked.setOptions({
        gfm: true,
        breaks: true,
        pedantic: false,
        sanitize: false,
        smartLists: true,
        smartypants: false,
        xhtml: false,
        langPrefix: 'language-'
    });

    // Add code language mapping for Prism
    marked.Renderer.prototype.code = function(code, language, isEscaped) {
        // Map common language names to Prism-compatible names
        const langMap = {
            'js': 'javascript',
            'ts': 'typescript',
            'py': 'python',
            'rb': 'ruby',
            'sh': 'bash',
            'shell': 'bash',
            'yml': 'yaml',
            'md': 'markdown',
            'c++': 'cpp',
            'c#': 'csharp',
            'objc': 'objectivec'
        };

        const prismLang = langMap[language] || language || 'plaintext';

        // Escape HTML in code
        const escapedCode = code
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');

        return `<div class="code-block-wrapper">
            <div class="code-block-header">
                <span class="code-lang">${prismLang}</span>
                <button class="copy-code-btn" title="Copy code" data-code="${encodeURIComponent(escapedCode)}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                </button>
            </div>
            <pre class="code-block"><code class="language-${prismLang}">${escapedCode}</code></pre>
        </div>`;
    };

    // Custom renderer for tables
    marked.Renderer.prototype.table = function(header, body) {
        return `<div class="table-wrapper">
            <table>
                <thead>${header}</thead>
                <tbody>${body}</tbody>
            </table>
        </div>`;
    };

    // Custom renderer for blockquotes
    marked.Renderer.prototype.blockquote = function(quote) {
        return `<blockquote>${quote}</blockquote>`;
    };

    // Custom renderer for lists
    marked.Renderer.prototype.list = function(body, ordered) {
        const type = ordered ? 'ol' : 'ul';
        return `<${type} class="${ordered ? 'ordered-list' : 'unordered-list'}">${body}</${type}>`;
    };

    // Custom renderer for links
    marked.Renderer.prototype.link = function(href, title, text) {
        const titleAttr = title ? ` title="${title}"` : '';
        const targetAttr = href.startsWith('http') ? ' target="_blank" rel="noopener noreferrer"' : '';
        return `<a href="${href}"${titleAttr}${targetAttr}>${text}</a>`;
    };

    // Custom renderer for images
    marked.Renderer.prototype.image = function(href, title, text) {
        const titleAttr = title ? ` title="${title}"` : '';
        return `<img src="${href}" alt="${text}"${titleAttr} class="rendered-image">`;
    };

    // Custom renderer for headings
    marked.Renderer.prototype.heading = function(text, level) {
        const id = text.toLowerCase().replace(/[^\w]+/g, '-');
        return `<h${level} id="${id}" class="rendered-heading">${text}</h${level}>`;
    };

    // Parse markdown content safely
    window.parseMarkdown = function(content) {
        if (!content) return '';
        try {
            return marked.parse(content);
        } catch (error) {
            console.error('Markdown parsing error:', error);
            return `<p class="parse-error">Error rendering content</p>`;
        }
    };

    // Escape markdown content for display (without parsing)
    window.escapeMarkdown = function(content) {
        if (!content) return '';
        return content
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/`/g, '&#96;')
            .replace(/\*/g, '&#42;')
            .replace(/_/g, '&#95;');
    };

})();
