// ==================== THEME MANAGEMENT ====================
const themeToggle = document.getElementById('themeToggle');
const html = document.documentElement;

// Load saved theme or default to light
const currentTheme = localStorage.getItem('theme') || 'light';
html.setAttribute('data-theme', currentTheme);

themeToggle.addEventListener('click', () => {
    const theme = html.getAttribute('data-theme');
    const newTheme = theme === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
});

// ==================== STATE MANAGEMENT ====================
let currentData = null;
let currentPdfIndex = 0;
let currentScale = 1.0;
let baseScale = 1.0;
// Force fit mode to 'width' by default (override any previous 'page' setting)
localStorage.setItem('fitMode', 'width');
let fitMode = 'width';
let pdfDoc = null;
let pageRendering = false;
let currentPageNumber = 1;
let totalPages = 1;
let isPdfDragging = false;
let dragStartX = 0;
let dragStartY = 0;
let dragScrollStartLeft = 0;
let dragScrollStartTop = 0;
let activePointerId = null;

// ==================== DOM ELEMENTS ====================
// No search button: search will trigger automatically on selection
const projectSelect = document.getElementById('projectSelect');
const sampleSelect = document.getElementById('sampleSelect');
const contentArea = document.getElementById('contentArea');
const emptyState = document.getElementById('emptyState');
const errorState = document.getElementById('errorState');
const errorMessage = document.getElementById('errorMessage');
const shortTextList = document.getElementById('shortTextList');
const pdfContainer = document.getElementById('pdfContainer');
const pdfCanvas = document.getElementById('pdfCanvas');
const pdfIndicator = document.getElementById('pdfIndicator');
const pdfCounter = document.getElementById('pdfCounter');
const itemCounter = document.getElementById('itemCounter');
const prevPdfBtn = document.getElementById('prevPdf');
const nextPdfBtn = document.getElementById('nextPdf');
const zoomInBtn = document.getElementById('zoomIn');
const zoomOutBtn = document.getElementById('zoomOut');
const zoomLevel = document.getElementById('zoomLevel');
// const fitWidthBtn = document.getElementById('fitWidth'); // Removed
// const fitPageBtn = document.getElementById('fitPage'); // Removed
const prevPageBtn = document.getElementById('prevPage');
const nextPageBtn = document.getElementById('nextPage');
const pageIndicator = document.getElementById('pageIndicator');
const orchLink = document.getElementById('orchLink');
const rightPanelTitle = document.getElementById('rightPanelTitle');
const itemsSection = document.getElementById('itemsSection');
const metadataSection = document.getElementById('metadataSection');
const metadataJson = document.getElementById('metadataJson');
// Custom project dropdown elements
const projectSelectWrapper = document.getElementById('projectSelectWrapper');
const projectSelectToggle = document.getElementById('projectSelectToggle');
const projectSelectMenu = document.getElementById('projectSelectMenu');
const projectSelectList = document.getElementById('projectSelectList');
// Custom sample dropdown elements
const sampleSelectWrapper = document.getElementById('sampleSelectWrapper');
const sampleSelectToggle = document.getElementById('sampleSelectToggle');
const sampleSelectMenu = document.getElementById('sampleSelectMenu');
const sampleSelectList = document.getElementById('sampleSelectList');

// Hide the counter pill next to Open Orchestration globally
if (itemCounter) {
    itemCounter.style.display = 'none';
}

// Utility: truncate option label to fit select width
let _truncateCanvas = null;
function truncateOptionLabel(selectEl, text) {
    try {
        const select = selectEl;
        if (!select) return text;
        const canvas = _truncateCanvas || (_truncateCanvas = document.createElement('canvas'));
        const ctx = canvas.getContext('2d');
        const cs = window.getComputedStyle(select);
        // Use computed font of the select for accurate measurements
        ctx.font = cs.font || `${cs.fontSize || '14px'} ${cs.fontFamily || 'sans-serif'}`;
        const padding = 48; // approximate left/right padding + arrow width
        const maxWidth = Math.max(0, select.clientWidth - padding);
        const original = String(text);
        if (ctx.measureText(original).width <= maxWidth) return original;
        // Binary search the largest prefix that fits with an ellipsis
        let lo = 0, hi = original.length, best = '';
        while (lo <= hi) {
            const mid = (lo + hi) >> 1;
            const candidate = original.slice(0, mid) + '…';
            const w = ctx.measureText(candidate).width;
            if (w <= maxWidth) {
                best = candidate;
                lo = mid + 1;
            } else {
                hi = mid - 1;
            }
        }
        return best || '…';
    } catch {
        // Fallback to a safe length
        const maxLen = 40;
        return text.length > maxLen ? text.slice(0, maxLen - 1) + '…' : text;
    }
}

// Format the visible Sample ID label in the custom toggle: if it overflows,
// cut at the last underscore and append an ellipsis.
function formatSampleToggleLabel(fullText) {
    try {
        const toggle = sampleSelectToggle;
        if (!toggle) return fullText;

        // Remove .pdf extension for display
        const text = String(fullText).replace(/\.pdf$/i, '');
        const canvas = _truncateCanvas || (_truncateCanvas = document.createElement('canvas'));
        const ctx = canvas.getContext('2d');
        const cs = window.getComputedStyle(toggle);
        ctx.font = cs.font || `${cs.fontSize || '14px'} ${cs.fontFamily || 'sans-serif'}`;
        const padding = parseFloat(cs.paddingLeft || '0') + parseFloat(cs.paddingRight || '0');
        const maxWidth = Math.max(0, toggle.clientWidth - padding);
        if (ctx.measureText(text).width <= maxWidth) return text;

        const lastUnderscore = text.lastIndexOf('_');
        if (lastUnderscore > 0) {
            const candidate = text.slice(0, lastUnderscore) + '…';
            if (ctx.measureText(candidate).width <= maxWidth) return candidate;
            // As a fallback, binary search a shorter prefix up to last underscore
            let lo = 0, hi = lastUnderscore, best = '…';
            while (lo <= hi) {
                const mid = (lo + hi) >> 1;
                const cand = text.slice(0, mid) + '…';
                if (ctx.measureText(cand).width <= maxWidth) {
                    best = cand;
                    lo = mid + 1;
                } else {
                    hi = mid - 1;
                }
            }
            return best;
        }
        // No underscore to cut on; fallback to prefix ellipsis
        let lo = 0, hi = text.length, best = '…';
        while (lo <= hi) {
            const mid = (lo + hi) >> 1;
            const cand = text.slice(0, mid) + '…';
            if (ctx.measureText(cand).width <= maxWidth) {
                best = cand;
                lo = mid + 1;
            } else {
                hi = mid - 1;
            }
        }
        return best;
    } catch {
        return fullText;
    }
}

function updateSampleToggleFromSelection() {
    if (!sampleSelectToggle || !sampleSelect) return;
    const sel = sampleSelect.options[sampleSelect.selectedIndex];
    if (sel && sel.value) {
        const full = sel.title || sel.textContent || sel.value;
        sampleSelectToggle.textContent = formatSampleToggleLabel(full);
        sampleSelectToggle.title = full;
    } else {
        sampleSelectToggle.textContent = 'Sample ID…';
        sampleSelectToggle.title = 'Sample ID…';
    }
}

// Configure PDF.js worker (only if PDF.js is loaded)
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
} else {
    console.warn('PDF.js library not loaded. PDF viewing will not be available.');
}

// ==================== SEARCH FUNCTIONALITY ====================
// Removed manual search button; search is triggered on sample selection

// Populate Sample IDs on load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Build custom project menu from the native select options
        if (projectSelect && projectSelectList && projectSelectToggle) {
            const buildMenu = () => {
                projectSelectList.innerHTML = '';
                Array.from(projectSelect.options).forEach(opt => {
                    // Skip placeholder/disabled in menu, but keep its label for the toggle if selected
                    if (opt.disabled || !opt.value) {
                        if (opt.selected) projectSelectToggle.textContent = opt.textContent;
                        return;
                    }
                    const li = document.createElement('li');
                    li.setAttribute('role', 'option');
                    li.dataset.value = opt.value;
                    li.textContent = opt.textContent;
                    if (opt.selected) projectSelectToggle.textContent = opt.textContent;
                    li.addEventListener('click', () => {
                        // Sync native select
                        projectSelect.value = opt.value;
                        projectSelect.dispatchEvent(new Event('change'));
                        projectSelectToggle.textContent = opt.textContent;
                        projectSelectWrapper.classList.remove('open');
                        projectSelectToggle.setAttribute('aria-expanded', 'false');
                    });
                    projectSelectList.appendChild(li);
                });
            };
            buildMenu();
            // Toggle menu
            projectSelectToggle.addEventListener('click', () => {
                const isOpen = projectSelectWrapper.classList.toggle('open');
                projectSelectToggle.setAttribute('aria-expanded', String(isOpen));
            });
            document.addEventListener('click', (e) => {
                if (!projectSelectWrapper.contains(e.target)) {
                    projectSelectWrapper.classList.remove('open');
                    projectSelectToggle.setAttribute('aria-expanded', 'false');
                }
            });
            // Rebuild list if options change dynamically
            const mo = new MutationObserver(buildMenu);
            mo.observe(projectSelect, { childList: true });
        }

        // Build custom sample menu from native select options
        if (sampleSelect && sampleSelectList && sampleSelectToggle) {
            const buildSampleMenu = () => {
                sampleSelectList.innerHTML = '';
                const opts = Array.from(sampleSelect.options);
                let hasReal = false;
                opts.forEach(opt => {
                    // Skip placeholder/disabled in menu, but keep its label for the toggle if selected
                    if (opt.disabled || !opt.value) {
                        if (opt.selected) {
                            sampleSelectToggle.textContent = opt.textContent;
                            sampleSelectToggle.title = opt.textContent;
                        }
                        return;
                    }
                    hasReal = true;
                    const li = document.createElement('li');
                    li.setAttribute('role', 'option');
                    li.dataset.value = opt.value;
                    li.title = opt.textContent; // show full in tooltip if truncated
                    li.textContent = opt.textContent;
                    if (opt.selected) {
                        const full = opt.textContent;
                        sampleSelectToggle.textContent = formatSampleToggleLabel(full);
                        sampleSelectToggle.title = full;
                    }
                    li.addEventListener('click', () => {
                        // Sync native select and fire change
                        sampleSelect.value = opt.value;
                        sampleSelect.dispatchEvent(new Event('change'));
                        const full = opt.textContent;
                        sampleSelectToggle.textContent = formatSampleToggleLabel(full);
                        sampleSelectToggle.title = full; // show full value on hover
                        sampleSelectWrapper.classList.remove('open');
                        sampleSelectToggle.setAttribute('aria-expanded', 'false');
                    });
                    sampleSelectList.appendChild(li);
                });
                if (!hasReal) {
                    const li = document.createElement('li');
                    li.textContent = 'No samples available';
                    li.style.opacity = '0.7';
                    li.style.cursor = 'default';
                    sampleSelectList.appendChild(li);
                }
            };
            buildSampleMenu();
            // Toggle menu
            sampleSelectToggle.addEventListener('click', () => {
                const isOpen = sampleSelectWrapper.classList.toggle('open');
                sampleSelectToggle.setAttribute('aria-expanded', String(isOpen));
            });
            document.addEventListener('click', (e) => {
                if (!sampleSelectWrapper.contains(e.target)) {
                    sampleSelectWrapper.classList.remove('open');
                    sampleSelectToggle.setAttribute('aria-expanded', 'false');
                }
            });
            // Rebuild list when options are repopulated
            const moSample = new MutationObserver(buildSampleMenu);
            moSample.observe(sampleSelect, { childList: true });
            // Also handle manual signal after batch updates
            sampleSelect.addEventListener('optionsUpdated', () => {
                buildSampleMenu();
                updateSampleToggleFromSelection();
            });
        }
    // Load available projects and initialize selection
        try {
            const projResp = await fetch('/api/projects');
            if (projResp.ok) {
                const projData = await projResp.json();
                const options = (projData.projects || []);
                if (projectSelect) {
                    // Start with placeholder and avoid auto-selecting any project
                    projectSelect.innerHTML = '';
                    const placeholder = document.createElement('option');
                    placeholder.value = '';
                    placeholder.textContent = 'Use Case…';
                    placeholder.disabled = true;
                    placeholder.selected = true;
                    projectSelect.appendChild(placeholder);
                    options.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p.key;
                        opt.textContent = p.label || p.key;
                        projectSelect.appendChild(opt);
                    });
                }
            }
        } catch (e) {
            console.warn('Failed to load projects list', e);
        }

    // Do not auto-select a project; require user choice
    const projectKey = projectSelect ? (projectSelect.value || '') : '';
        if (orchLink) {
            orchLink.classList.add('disabled');
            orchLink.href = '#';
            orchLink.title = 'Select a use case to open orchestration';
        }
        // If no project chosen yet, leave sample select with its placeholder
        if (!projectKey) {
            sampleSelect.innerHTML = '';
            const sPlaceholder = document.createElement('option');
            sPlaceholder.value = '';
            sPlaceholder.textContent = 'Sample ID…';
            sPlaceholder.disabled = true;
            sPlaceholder.selected = true;
            sampleSelect.appendChild(sPlaceholder);
        } else {
            // Prompt Enhancer mode: hide controls and load documents list
            if (projectKey === 'promptenhancer') {
                // Hide right panel sections
                const itemsSection = document.getElementById('itemsSection');
                const metadataSection = document.getElementById('metadataSection');
                const warningsSection = document.getElementById('warningsSection');
                const orchLink = document.getElementById('orchLink');
                const dataSection = document.querySelector('.data-section');
                // Hide counters
                if (pdfCounter) { pdfCounter.textContent = ''; pdfCounter.style.display = 'none'; }
                if (pdfIndicator) { pdfIndicator.textContent = ''; pdfIndicator.style.display = 'none'; }
                if (itemsSection) itemsSection.style.display = 'none';
                if (metadataSection) metadataSection.style.display = 'none';
                if (warningsSection) warningsSection.style.display = 'none';
                if (dataSection) dataSection.style.display = 'none';
                // Disable orchestration link
                if (orchLink) {
                    orchLink.classList.add('disabled');
                    orchLink.href = '#';
                    orchLink.title = '';
                }
                // Hide sample selector entirely
                if (sampleSelectWrapper) sampleSelectWrapper.style.display = 'none';
                // Load documents list and render images
                try {
                    const docResp = await fetch(`/api/documents?project=${encodeURIComponent(projectKey)}`);
                    const docData = await docResp.json();
                    if (docResp.ok && Array.isArray(docData.documents)) {
                        currentData = { sample_id: '', short_texts: [], pdfs: docData.documents };
                        currentPdfIndex = 0;
                        // Show content area
                        emptyState.style.display = 'none';
                        errorState.classList.add('hidden');
                        contentArea.classList.remove('hidden');
                        // Render first image
                        loadImage(currentPdfIndex);
                        updatePdfControls();
                    } else {
                        showError(docData.error || 'No documents found');
                    }
                } catch (e) {
                    showError('Failed to load documents');
                }
                // Stop normal flow for sample IDs
                return;
            }
            // Enable orchestration link for selected project
            if (orchLink) {
                orchLink.classList.remove('disabled');
                orchLink.href = `/orchestration/${encodeURIComponent(projectKey)}`;
                orchLink.title = `Open orchestration for ${projectKey}`;
            }
            // Ensure sample selector and right panel visible for non-Prompt Enhancer
            if (sampleSelectWrapper) sampleSelectWrapper.style.display = '';
            const dataSection = document.querySelector('.data-section');
            const itemsSection = document.getElementById('itemsSection');
            const warningsSection = document.getElementById('warningsSection');
            if (dataSection) dataSection.style.display = '';
            if (itemsSection) itemsSection.style.display = '';
            if (warningsSection) warningsSection.style.display = '';
            // Restore counters for non-Prompt Enhancer
            if (pdfCounter) { pdfCounter.style.display = ''; }
            if (pdfIndicator) { pdfIndicator.style.display = ''; }

            const resp = await fetch(`/api/sample_ids?project=${encodeURIComponent(projectKey)}`);
            const data = await resp.json();
            if (resp.ok && Array.isArray(data.ids)) {
                // Clear existing except placeholder
                const placeholder = sampleSelect.querySelector('option[value=""]');
                sampleSelect.innerHTML = '';
                if (placeholder) {
                    sampleSelect.appendChild(placeholder);
                } else {
                    const opt = document.createElement('option');
                    opt.value = '';
                    opt.textContent = 'Select Sample ID…';
                    opt.disabled = true;
                    opt.selected = true;
                    sampleSelect.appendChild(opt);
                }
            data.ids.forEach(id => {
                const opt = document.createElement('option');
                opt.value = id; // keep full filename/value for API usage
                const raw = String(id);
                const display = raw.replace(/\.pdf$/i, '');
                // Do NOT truncate here; native select is hidden and width is 0
                opt.textContent = display;
                opt.title = raw; // show full on hover
                sampleSelect.appendChild(opt);
            });
            } else {
                console.warn('Failed to load Sample IDs:', data.error);
            }
        }
    } catch (err) {
        console.error('Error loading Sample IDs:', err);
    }

    // Collapsible sections behavior
    const collapsibles = document.querySelectorAll('.collapsible-section');
    collapsibles.forEach(section => {
        const header = section.querySelector('.collapsible-header');
        if (header) {
            header.addEventListener('click', (e) => {
                // Avoid toggling when clicking expand button
                if (e.target.closest('.expand-btn')) return;
                section.classList.toggle('open');
            });
        }
    });

    // Modal full view handling
    const modal = document.getElementById('fullViewModal');
    const modalPre = document.getElementById('modalPre');
    const modalTitle = document.getElementById('modalTitle');
    const modalClose = document.getElementById('modalClose');
    const expandButtons = document.querySelectorAll('#warningsSection .expand-btn');

    function openModal(title, text) {
        if (!modal) return;
        modalTitle.textContent = title || 'Full view';
        modalPre.textContent = text || '';
        modal.classList.add('show');
        modal.setAttribute('aria-hidden', 'false');
    }

    function closeModal() {
        if (!modal) return;
        modal.classList.remove('show');
        modal.setAttribute('aria-hidden', 'true');
    }

    expandButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const targetId = btn.getAttribute('data-target');
            const pre = document.getElementById(targetId);
            const title = 'Final Output';
            openModal(title, pre ? pre.textContent : '');
        });
    });

    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    if (modal) {
        const backdrop = modal.querySelector('.modal-backdrop');
        if (backdrop) backdrop.addEventListener('click', closeModal);
    }
});

// Fallback: delegated handler to ensure expand works even if direct binding fails
document.addEventListener('click', (e) => {
    const btn = e.target.closest && e.target.closest('.expand-btn');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    const targetId = btn.getAttribute('data-target') || 'warningsJson';
    const pre = document.getElementById(targetId);
    const titleEl = document.getElementById('modalTitle');
    const preEl = document.getElementById('modalPre');
    const modal = document.getElementById('fullViewModal');
    if (modal && titleEl && preEl) {
        titleEl.textContent = btn.getAttribute('aria-label') || 'Full view';
        preEl.textContent = pre ? pre.textContent : '';
        modal.classList.add('show');
        modal.setAttribute('aria-hidden', 'false');
    }
});

// Reload Sample IDs when project changes
if (projectSelect) {
    projectSelect.addEventListener('change', async () => {
    const projectKey = projectSelect.value;
        // Update orchestration link
        if (orchLink) {
            if (projectKey) {
                orchLink.classList.remove('disabled');
                orchLink.href = `/orchestration/${encodeURIComponent(projectKey)}`;
                orchLink.title = `Open orchestration for ${projectKey}`;
            } else {
                orchLink.classList.add('disabled');
                orchLink.href = '#';
                orchLink.title = 'Select a use case to open orchestration';
            }
        }
    // Clear any previously stored selection; require explicit choice each time
    // localStorage.setItem('selectedProject', projectKey);
        // Clear sample select
        while (sampleSelect.firstChild) sampleSelect.removeChild(sampleSelect.firstChild);
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = 'Sample ID…';
        opt.disabled = true;
        opt.selected = true;
        sampleSelect.appendChild(opt);

        try {
            // Prompt Enhancer: special flow (no sample IDs)
            if (projectKey === 'promptenhancer') {
                // Hide sample selector and right panel sections
                if (sampleSelectWrapper) sampleSelectWrapper.style.display = 'none';
                const itemsSection = document.getElementById('itemsSection');
                const metadataSection = document.getElementById('metadataSection');
                const warningsSection = document.getElementById('warningsSection');
                const dataSection = document.querySelector('.data-section');
                // Hide counters
                if (pdfCounter) { pdfCounter.textContent = ''; pdfCounter.style.display = 'none'; }
                if (pdfIndicator) { pdfIndicator.textContent = ''; pdfIndicator.style.display = 'none'; }
                if (itemsSection) itemsSection.style.display = 'none';
                if (metadataSection) metadataSection.style.display = 'none';
                if (warningsSection) warningsSection.style.display = 'none';
                if (dataSection) dataSection.style.display = 'none';
                // Disable orchestration link
                if (orchLink) {
                    orchLink.classList.add('disabled');
                    orchLink.href = '#';
                    orchLink.title = '';
                }
                // Load documents
                try {
                    const docResp = await fetch(`/api/documents?project=${encodeURIComponent(projectKey)}`);
                    const docData = await docResp.json();
                    if (docResp.ok && Array.isArray(docData.documents)) {
                        currentData = { sample_id: '', short_texts: [], pdfs: docData.documents };
                        currentPdfIndex = 0;
                        emptyState.style.display = 'none';
                        errorState.classList.add('hidden');
                        contentArea.classList.remove('hidden');
                        loadImage(currentPdfIndex);
                        updatePdfControls();
                    } else {
                        showError(docData.error || 'No documents found');
                    }
                } catch (e) {
                    showError('Failed to load documents');
                }
                return;
            }

            // For non-Prompt Enhancer projects: restore UI elements
            if (sampleSelectWrapper) sampleSelectWrapper.style.display = '';
            const itemsSection = document.getElementById('itemsSection');
            const metadataSection = document.getElementById('metadataSection');
            const warningsSection = document.getElementById('warningsSection');
            const dataSection = document.querySelector('.data-section');
            if (pdfCounter) pdfCounter.style.display = '';
            if (pdfIndicator) pdfIndicator.style.display = '';
            if (itemsSection) itemsSection.style.display = '';
            if (metadataSection) metadataSection.style.display = 'none'; // Smart Judge specific
            if (warningsSection) warningsSection.style.display = '';
            if (dataSection) dataSection.style.display = '';
            // Clear content area until sample is selected
            contentArea.classList.add('hidden');
            emptyState.style.display = '';
            errorState.classList.add('hidden');

            const resp = await fetch(`/api/sample_ids?project=${encodeURIComponent(projectKey)}`);
            const data = await resp.json();
        if (resp.ok && Array.isArray(data.ids)) {
                data.ids.forEach(id => {
                    const o = document.createElement('option');
                    o.value = id; // keep full filename/value for API usage
                    const raw = String(id);
                    const display = raw.replace(/\.pdf$/i, '');
            // Do NOT truncate here; native select is hidden and width is 0
            o.textContent = display;
                    o.title = raw;
                    sampleSelect.appendChild(o);
                });
                // If custom sample menu exists, refresh it to reflect new options
                if (typeof sampleSelectList !== 'undefined' && sampleSelectList) {
                    // Manually trigger MutationObserver alternative by rebuilding
                    const event = new Event('optionsUpdated');
                    sampleSelect.dispatchEvent(event);
                }
            } else {
                showError(data.error || 'Failed to load Sample IDs');
            }
        } catch (e) {
            showError('Failed to load Sample IDs');
        }
    // No manual search button; nothing to enable/disable
    // Do not change Sample Details panel on project change; wait for sample selection
    });
}

async function handleSearch() {
    const sampleId = sampleSelect ? (sampleSelect.value || '').trim() : '';
    const projectKey = projectSelect ? (projectSelect.value || '') : '';
    console.log('Search clicked, sample ID:', sampleId);

    if (!projectKey) {
        showError('Please select a use case');
        return;
    }

    if (!sampleId) {
        showError('Please select a sample ID');
        return;
    }

    setSearchLoading(true);

    try {
        console.log('Fetching data for sample:', sampleId);
    const response = await fetch(`/api/sample/${sampleId}?project=${encodeURIComponent(projectKey)}`);
        const data = await response.json();
        console.log('Response:', response.status, data);

        if (!response.ok) {
            showError(data.error || 'Sample ID not found');
            return;
        }

        currentData = data;
        currentPdfIndex = 0;
        displayData();

    // Toggle right panel sections based on the active project AFTER data is loaded
    const isSmartActive = projectKey === 'smartjudge';
    const isPrompt = projectKey === 'promptenhancer';
    if (rightPanelTitle) rightPanelTitle.textContent = 'Sample Details';
    if (itemsSection) itemsSection.style.display = (isSmartActive || isPrompt) ? 'none' : '';
    if (metadataSection) metadataSection.style.display = isSmartActive ? '' : 'none';
    const warningsSection = document.getElementById('warningsSection');
    // Hide final output section for both Smart Judge and Prompt Enhancer
    if (warningsSection) warningsSection.style.display = (isPrompt || isSmartActive) ? 'none' : '';

        // Load Final outputs for this Sample ID and populate sections (skip for Prompt Enhancer)
        try {
            if (isPrompt) {
                const warningsPre = document.getElementById('warningsJson');
                if (warningsPre) warningsPre.textContent = '';
            } else {
            const finalOutputsResp = await fetch(`/api/finalOutputs/${encodeURIComponent(currentData.sample_id)}?project=${encodeURIComponent(projectKey)}`);
            const finalOutputsData = await finalOutputsResp.json();
            const warningsPre = document.getElementById('warningsJson');
            const warningsSection = document.getElementById('warningsSection');
            if (finalOutputsResp.ok) {
                // Pretty print warnings (array or object)
                let warningsStr = '';
                if (Array.isArray(finalOutputsData.warnings) && finalOutputsData.warnings.length) {
                    warningsStr = finalOutputsData.warnings.map(w => `- ${w}`).join('\n');
                } else if (finalOutputsData.warnings) {
                    warningsStr = JSON.stringify(finalOutputsData.warnings, null, 2);
                } else {
                    warningsStr = 'No warnings available for this Sample ID.';
                }
                if (warningsPre) warningsPre.textContent = warningsStr;

                // Smart Judge: fetch metadata.jsonl and render
                if (projectKey === 'smartjudge' && metadataJson) {
                    try {
                        const metaResp = await fetch(`/api/metadata/${encodeURIComponent(currentData.sample_id)}?project=${encodeURIComponent(projectKey)}`);
                        const metaData = await metaResp.json();
                        if (metaResp.ok) {
                            const payload = (metaData && metaData.metadata !== undefined) ? metaData.metadata : metaData;
                            metadataJson.textContent = JSON.stringify(payload, null, 2);
                        } else {
                            metadataJson.textContent = metaData.error || 'No metadata available for this Sample ID.';
                        }
                    } catch (me) {
                        metadataJson.textContent = 'Failed to load metadata.';
                    }
                }
            } else {
                if (warningsPre) warningsPre.textContent = 'No warnings available for this Sample ID.';
                if (projectKey === 'smartjudge' && metadataJson) {
                    metadataJson.textContent = 'No metadata available for this Sample ID.';
                }
            }
            }
        } catch (e) {
            console.error('Failed to load Final outputs:', e);
            if (projectKey === 'smartjudge' && metadataJson) {
                metadataJson.textContent = 'Failed to load metadata.';
            }
        }

    } catch (error) {
        console.error('Error in handleSearch:', error);
        showError('An error occurred while fetching data');
        console.error(error);
    } finally {
        setSearchLoading(false);
    }
}

// Enable search when sample selection becomes valid
if (sampleSelect) {
    sampleSelect.addEventListener('change', () => {
        const hasProject = !!(projectSelect && projectSelect.value);
        const hasSample = !!(sampleSelect && sampleSelect.value);
        updateSampleToggleFromSelection();
        if (hasProject && hasSample) {
            // Auto-trigger search when a valid sample is chosen
            handleSearch();
        }
    });
}

// Re-compute truncation on resize
window.addEventListener('resize', () => {
    updateSampleToggleFromSelection();
});

// ==================== DISPLAY FUNCTIONS ====================
function displayData() {
    // Hide states
    emptyState.style.display = 'none';
    errorState.classList.add('hidden');
    contentArea.classList.remove('hidden');

    // Display short texts
    const projectKey = projectSelect ? (projectSelect.value || '') : '';
    if (projectKey !== 'smartjudge' && projectKey !== 'promptenhancer') {
        displayShortTexts();
    } else {
        // Clear items list and counter for Smart Judge
        shortTextList.innerHTML = '';
        itemCounter.textContent = '';
            if (itemCounter) itemCounter.style.display = 'none';
    }

    // Display documents (PDFs or images)
    if (currentData.pdfs.length > 0) {
        const isPrompt = projectKey === 'promptenhancer';
        if (isPrompt) {
            // Hide counters for Prompt Enhancer
            if (pdfCounter) pdfCounter.style.display = 'none';
            if (pdfIndicator) pdfIndicator.style.display = 'none';
            loadImage(currentPdfIndex);
            updatePdfControls();
        } else {
            if (pdfCounter) pdfCounter.style.display = '';
            if (pdfIndicator) pdfIndicator.style.display = '';
            loadPdf(currentPdfIndex);
            updatePdfControls();
        }
    } else {
        showNoPdfs();
    }
}

function displayShortTexts() {
    shortTextList.innerHTML = '';
    const count = Array.isArray(currentData.short_texts) ? currentData.short_texts.length : 0;
    itemCounter.textContent = `${count} item${count === 1 ? '' : 's'}`;

    if (count === 0) {
        const li = document.createElement('li');
        li.className = 'empty-note';
        li.textContent = 'No database items found for this sample.';
        shortTextList.appendChild(li);
        return;
    }

    currentData.short_texts.forEach((text) => {
        const li = document.createElement('li');
        li.textContent = text;
        shortTextList.appendChild(li);
    });
}

function showError(message) {
    emptyState.style.display = 'none';
    contentArea.classList.add('hidden');
    errorState.classList.remove('hidden');
    errorMessage.textContent = message;
}

function showNoPdfs() {
    ensurePdfCanvas();
    const ctx = pdfCanvas.getContext('2d');
    ctx.clearRect(0, 0, pdfCanvas.width, pdfCanvas.height);
    const isPrompt = (projectSelect ? projectSelect.value : '') === 'promptenhancer';
    if (!isPrompt) {
        pdfIndicator.textContent = 'No documents available';
        pdfCounter.textContent = '0 documents';
    } else {
        if (pdfIndicator) pdfIndicator.textContent = '';
        if (pdfCounter) pdfCounter.textContent = '';
        if (pdfIndicator) pdfIndicator.style.display = 'none';
        if (pdfCounter) pdfCounter.style.display = 'none';
    }
    prevPdfBtn.disabled = true;
    nextPdfBtn.disabled = true;
    totalPages = 0;
    currentPageNumber = 1;
    updatePageControls();
}

function setSearchLoading(isLoading) {
    // No visible loading spinner now; could hook into UI if needed
}

// ==================== PDF RENDERING ====================
async function loadPdf(index) {
    if (!currentData || !currentData.pdfs[index]) return;
    const projectKey = projectSelect ? (projectSelect.value || 'audit') : 'audit';
    const isInvoicing = projectKey === 'invoicing';
    const isPrompt = projectKey === 'promptenhancer';
    const fileName = currentData.pdfs[index];
    const pdfUrl = isInvoicing
        ? `/api/pdf/${encodeURIComponent(fileName)}/${encodeURIComponent(fileName)}?project=${encodeURIComponent(projectKey)}`
        : `/api/pdf/${encodeURIComponent(currentData.sample_id)}/${encodeURIComponent(fileName)}?project=${encodeURIComponent(projectKey)}`;
    ensurePdfCanvas();

    if (isPrompt) {
        // Render image instead of PDF
        return loadImage(index);
    }

    // Check if PDF.js is available
    if (typeof pdfjsLib === 'undefined') {
        console.error('PDF.js not loaded');
        pdfIndicator.textContent = 'PDF viewer unavailable';
        // Show a link to download instead
        pdfContainer.innerHTML = `<div style="text-align: center; padding: 2rem;">
            <p style="margin-bottom: 1rem;">PDF viewer unavailable</p>
            <a href="${pdfUrl}" download style="color: var(--accent-primary); text-decoration: underline;">Download PDF</a>
        </div>`;
        totalPages = 0;
        currentPageNumber = 1;
        updatePageControls();
        return;
    }

    try {
        console.log('Loading PDF:', pdfUrl);
        pdfDoc = await pdfjsLib.getDocument(pdfUrl).promise;
        currentPageNumber = 1;
        totalPages = Math.max(pdfDoc.numPages || 1, 1);

        // Calculate base scale to fit container width
        const page = await pdfDoc.getPage(1);
        const containerStyles = window.getComputedStyle(pdfContainer);
        const horizontalPadding = parseFloat(containerStyles.paddingLeft) + parseFloat(containerStyles.paddingRight);
        const verticalPadding = parseFloat(containerStyles.paddingTop) + parseFloat(containerStyles.paddingBottom);
        const containerWidth = Math.max(pdfContainer.clientWidth - horizontalPadding, 200);
        const containerHeight = Math.max(pdfContainer.clientHeight - verticalPadding, 200);
        const viewport = page.getViewport({ scale: 1 });
        if (fitMode === 'width') {
            baseScale = containerWidth / viewport.width;
        } else {
            baseScale = Math.min(containerWidth / viewport.width, containerHeight / viewport.height);
        }
    currentScale = baseScale;

    updatePageControls();
    renderAllPages();
        updatePdfControls();
        updateZoomDisplay();
    } catch (error) {
        console.error('Error loading PDF:', error);
        pdfIndicator.textContent = 'Error loading PDF';
    }
}

async function renderPage(pageNum) {
    if (!pdfDoc) return;
    if (pageRendering) return;
    pageRendering = true;

    try {
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: currentScale });

        pdfCanvas.height = viewport.height;
        pdfCanvas.width = viewport.width;

        const renderContext = {
            canvasContext: pdfCanvas.getContext('2d'),
            viewport: viewport
        };

        await page.render(renderContext).promise;
        updatePageControls();
    } catch (error) {
        console.error('Error rendering page:', error);
    } finally {
        pageRendering = false;
    }
}

async function renderAllPages() {
    if (!pdfDoc) return;
    if (pageRendering) return;
    pageRendering = true;

    try {
        // Clear container and render all pages as stacked canvases
        pdfContainer.innerHTML = '';
        for (let pageNum = 1; pageNum <= totalPages; pageNum++) {
            const page = await pdfDoc.getPage(pageNum);
            const viewport = page.getViewport({ scale: currentScale });
            const canvas = document.createElement('canvas');
            canvas.className = 'pdf-page-canvas';
            canvas.width = viewport.width;
            canvas.height = viewport.height;
            const ctx = canvas.getContext('2d');
            await page.render({ canvasContext: ctx, viewport }).promise;
            pdfContainer.appendChild(canvas);
        }
        updatePageControls();
    } catch (error) {
        console.error('Error rendering pages:', error);
    } finally {
        pageRendering = false;
    }
}

function updatePdfControls() {
    if (!currentData) return;

    const totalPdfs = currentData.pdfs.length;
    const isPrompt = (projectSelect ? projectSelect.value : '') === 'promptenhancer';
    if (!isPrompt) {
        pdfCounter.textContent = `${totalPdfs} PDF${totalPdfs !== 1 ? 's' : ''}`;
        pdfIndicator.textContent = `${currentPdfIndex + 1} / ${totalPdfs}`;
    }

    prevPdfBtn.disabled = currentPdfIndex === 0;
    nextPdfBtn.disabled = currentPdfIndex === totalPdfs - 1;

    updateZoomDisplay();
    if (pdfDoc) {
        updatePageControls();
    }
}

function updateZoomDisplay() {
    const zoomPercent = Math.round((currentScale / baseScale) * 100);
    zoomLevel.textContent = `${zoomPercent}%`;
    // Removed fitWidth and fitPage button active state updates
}

// ==================== PDF NAVIGATION ====================
prevPdfBtn.addEventListener('click', () => {
    if (currentPdfIndex > 0) {
        currentPdfIndex--;
        const projectKey = projectSelect ? (projectSelect.value || '') : '';
        const isPrompt = projectKey === 'promptenhancer';
        if (isPrompt) {
            loadImage(currentPdfIndex);
        } else {
            loadPdf(currentPdfIndex);
        }
        updatePdfControls();
    }
});

nextPdfBtn.addEventListener('click', () => {
    if (currentPdfIndex < currentData.pdfs.length - 1) {
        currentPdfIndex++;
        const projectKey = projectSelect ? (projectSelect.value || '') : '';
        const isPrompt = projectKey === 'promptenhancer';
        if (isPrompt) {
            loadImage(currentPdfIndex);
        } else {
            loadPdf(currentPdfIndex);
        }
        updatePdfControls();
    }
});

prevPageBtn.addEventListener('click', () => {
    // Disabled in continuous scroll mode
});

nextPageBtn.addEventListener('click', () => {
    // Disabled in continuous scroll mode
});

// ==================== ZOOM CONTROLS ====================
zoomInBtn.addEventListener('click', () => {
    const projectKey = projectSelect ? (projectSelect.value || '') : '';
    const isPrompt = projectKey === 'promptenhancer';
    
    if (isPrompt) {
        // For images, use simple scale increments
        const maxScale = 3.0;
        if (currentScale < maxScale) {
            currentScale += 0.25;
            applyImageZoom();
            updateZoomDisplay();
        }
    } else {
        // For PDFs, use baseScale
        const maxScale = baseScale * 3;
        if (currentScale < maxScale) {
            currentScale += baseScale * 0.25;
            renderAllPages();
            updateZoomDisplay();
        }
    }
});

zoomOutBtn.addEventListener('click', () => {
    const projectKey = projectSelect ? (projectSelect.value || '') : '';
    const isPrompt = projectKey === 'promptenhancer';
    
    if (isPrompt) {
        // For images, use simple scale increments
        const minScale = 0.5;
        if (currentScale > minScale) {
            currentScale -= 0.25;
            applyImageZoom();
            updateZoomDisplay();
        }
    } else {
        // For PDFs, use baseScale
        const minScale = baseScale * 0.5;
        if (currentScale > minScale) {
            currentScale -= baseScale * 0.25;
            renderAllPages();
            updateZoomDisplay();
        }
    }
});

// ==================== FIT MODE TOGGLES ====================
// Removed fitWidth and fitPage buttons

// ==================== DOWNLOAD ====================
// ==================== KEYBOARD SHORTCUTS ====================
document.addEventListener('keydown', (e) => {
    if (!currentData) return;

    switch (e.key) {
        case 'ArrowLeft':
            if (!prevPdfBtn.disabled) prevPdfBtn.click();
            break;
        case 'ArrowRight':
            if (!nextPdfBtn.disabled) nextPdfBtn.click();
            break;
        case 'PageUp':
            if (!prevPageBtn.disabled) {
                e.preventDefault();
                prevPageBtn.click();
            }
            break;
        case 'PageDown':
            if (!nextPageBtn.disabled) {
                e.preventDefault();
                nextPageBtn.click();
            }
            break;
        case '+':
        case '=':
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                zoomInBtn.click();
            }
            break;
        case '-':
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                zoomOutBtn.click();
            }
            break;
    }
});

pdfContainer.addEventListener('pointerdown', handlePdfPointerDown);
pdfContainer.addEventListener('pointermove', handlePdfPointerMove);
pdfContainer.addEventListener('pointerup', handlePdfPointerUpOrCancel);
pdfContainer.addEventListener('pointerleave', handlePdfPointerUpOrCancel);
pdfContainer.addEventListener('pointercancel', handlePdfPointerUpOrCancel);

function ensurePdfCanvas() {
    if (!pdfCanvas.parentElement) {
        pdfContainer.innerHTML = '';
        pdfContainer.appendChild(pdfCanvas);
    }
}

function updatePageControls() {
    const hasDoc = !!pdfDoc && totalPages > 0;
    pageIndicator.textContent = hasDoc ? `Pages ${totalPages}` : 'Pages 0';
    prevPageBtn.disabled = true;
    nextPageBtn.disabled = true;
}

// ================ IMAGE RENDERING (Prompt Enhancer) ================
function loadImage(index) {
    if (!currentData || !currentData.pdfs[index]) return;
    const projectKey = projectSelect ? (projectSelect.value || 'promptenhancer') : 'promptenhancer';
    const fileName = currentData.pdfs[index];
    const imgUrl = `/api/pdf/${encodeURIComponent(fileName)}/${encodeURIComponent(fileName)}?project=${encodeURIComponent(projectKey)}`;
    // Replace container with an image element
    pdfContainer.innerHTML = '';
    const img = document.createElement('img');
    img.src = imgUrl;
    img.alt = fileName;
    img.id = 'zoomableImage';
    img.style.maxWidth = '100%';
    img.style.height = 'auto';
    img.style.display = 'block';
    img.style.margin = '0 auto';
    img.style.transformOrigin = 'center center';
    img.style.transition = 'transform 0.2s ease';
    pdfContainer.appendChild(img);
    // Reset scale for new image
    currentScale = 1.0;
    applyImageZoom();
    updateZoomDisplay();
    // Reset PDF-specific state
    pdfDoc = null;
    totalPages = 1;
    currentPageNumber = 1;
    updatePageControls();
}

// Apply zoom transform to image
function applyImageZoom() {
    const img = document.getElementById('zoomableImage');
    if (img) {
        img.style.transform = `scale(${currentScale})`;
    }
}

function handlePdfPointerDown(e) {
    if (e.button !== 0) return;
    if (!pdfDoc || e.target !== pdfCanvas && e.target !== pdfContainer) return;

    isPdfDragging = true;
    activePointerId = e.pointerId;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragScrollStartLeft = pdfContainer.scrollLeft;
    dragScrollStartTop = pdfContainer.scrollTop;
    pdfContainer.classList.add('dragging');

    if (typeof pdfContainer.setPointerCapture === 'function') {
        try {
            pdfContainer.setPointerCapture(activePointerId);
        } catch (err) { }
    }
}

function handlePdfPointerMove(e) {
    if (!isPdfDragging || e.pointerId !== activePointerId) return;

    const deltaX = e.clientX - dragStartX;
    const deltaY = e.clientY - dragStartY;
    pdfContainer.scrollLeft = dragScrollStartLeft - deltaX;
    pdfContainer.scrollTop = dragScrollStartTop - deltaY;
    e.preventDefault();
}

function handlePdfPointerUpOrCancel(e) {
    if (!isPdfDragging || e.pointerId !== activePointerId) return;

    isPdfDragging = false;
    pdfContainer.classList.remove('dragging');

    if (typeof pdfContainer.releasePointerCapture === 'function') {
        try {
            pdfContainer.releasePointerCapture(activePointerId);
        } catch (err) { }
    }

    activePointerId = null;
}
