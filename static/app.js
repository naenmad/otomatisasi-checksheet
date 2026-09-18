/**
 * Summit Checksheet Master Automation Studio
 * Frontend Application Controller
 * Fully SVG-powered, 3-category workflow, in-web Excel logs & diff comparison table
 */

// SVG Icon Library
const ICONS = {
    folder: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>`,
    search: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,
    diff: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 3 4 4-4 4"/><path d="M20 7H4"/><path d="m8 21-4-4 4-4"/><path d="M4 17h16"/></svg>`,
    history: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/></svg>`,
    globe: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>`,
    zap: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
    clock: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
    alertCircle: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    checkCircle: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
    box: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`,
    refresh: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>`,
    play: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>`,
    info: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>`,
    download: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`,
    copy: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`,
    externalLink: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>`,
    arrowLeft: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>`,
    plus: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
    catalog: `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6 6h10"/><path d="M6 10h10"/></svg>`
};

document.addEventListener('DOMContentLoaded', () => {
    // App State
    let currentFilter = 'belum'; // 'belum', 'tidak_ada_part', or 'done'
    let docsData = { belum: [], tidak_ada_part: [], done: [], total: 0, counts: { belum: 0, tidak_ada_part: 0, done: 0 } };
    let currentDiffData = null;
    let currentDiffFilter = 'all'; // 'all', 'changed', 'added', 'modified', 'removed'
    let excelLogsData = { execution_history: [], search_history: [] };
    let currentMissingParts = [];
    let currentDetailsDoc = null;

    // Navigation & Main Panes
    const navBtns = document.querySelectorAll('.nav-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const btnRefreshAll = document.getElementById('btn-refresh-all');

    // Metrics Elements
    const countBelumEl = document.getElementById('count-belum');
    const countTidakAdaEl = document.getElementById('count-tidak-ada');
    const countDoneEl = document.getElementById('count-done');
    const countTotalEl = document.getElementById('count-total');

    // Filter Buttons & Badges
    const badgeBelumEl = document.getElementById('badge-belum');
    const badgeTidakAdaEl = document.getElementById('badge-tidak-ada');
    const badgeDoneEl = document.getElementById('badge-done');
    const filterBelumBtn = document.getElementById('filter-belum-btn');
    const filterTidakAdaBtn = document.getElementById('filter-tidak-ada-btn');
    const filterDoneBtn = document.getElementById('filter-done-btn');

    // Document Grid & Search
    const docGrid = document.getElementById('doc-grid');
    const docSearchInput = document.getElementById('doc-search-input');

    // Batch Search Elements
    const searchInputArea = document.getElementById('search-input-area');
    const btnQuickBelum = document.getElementById('btn-quick-belum');
    const btnQuickTidakAda = document.getElementById('btn-quick-tidak-ada');
    const btnExecuteSearch = document.getElementById('btn-execute-search');
    const searchSummary = document.getElementById('search-summary');
    const statSearchTotal = document.getElementById('stat-search-total');
    const statSearchAda = document.getElementById('stat-search-ada');
    const statSearchTidak = document.getElementById('stat-search-tidak');
    const btnCopyMissing = document.getElementById('btn-copy-missing');
    const searchTableWrapper = document.getElementById('search-table-wrapper');
    const searchResultsTbody = document.getElementById('search-results-tbody');

    // Diff Tab Elements
    const diffPartSelect = document.getElementById('diff-part-select');
    const btnRunDiffCompare = document.getElementById('btn-run-diff-compare');
    const diffFilterGroup = document.getElementById('diff-filter-group');
    const diffEmptyState = document.getElementById('diff-empty-state');
    const diffContent = document.getElementById('diff-content');

    // Logs Tab Elements
    const btnRefreshLogs = document.getElementById('btn-refresh-logs');
    const subtabExecBtn = document.getElementById('subtab-exec-btn');
    const subtabSearchBtn = document.getElementById('subtab-search-btn');
    const countLogExec = document.getElementById('count-log-exec');
    const countLogSearch = document.getElementById('count-log-search');
    const subtabExec = document.getElementById('subtab-exec');
    const subtabSearch = document.getElementById('subtab-search');
    const logsTbody = document.getElementById('logs-tbody');
    const searchLogsTbody = document.getElementById('search-logs-tbody');
    const execSearchInput = document.getElementById('exec-search-input');
    const searchLogFilter = document.getElementById('search-log-filter');

    // Header Action & New Modals Elements
    const btnOpenPalette = document.getElementById('btn-open-palette');
    const modalPalette = document.getElementById('modal-palette');
    const paletteInput = document.getElementById('palette-input');
    const paletteResults = document.getElementById('palette-results');

    const btnOpenCreateFolder = document.getElementById('btn-open-create-folder');
    const modalCreateFolder = document.getElementById('modal-create-folder');
    const modalCreateFolderClose = document.getElementById('modal-create-folder-close');
    const createFolderName = document.getElementById('create-folder-name');
    const createFolderStatus = document.getElementById('create-folder-status');
    const createFolderSubmit = document.getElementById('create-folder-submit');
    const createFolderCancel = document.getElementById('create-folder-cancel');

    const btnOpenUpload = document.getElementById('btn-open-upload');
    const modalUpload = document.getElementById('modal-upload');
    const modalUploadClose = document.getElementById('modal-upload-close');
    const modalUploadCancel = document.getElementById('modal-upload-cancel');
    const modalUploadSubmit = document.getElementById('modal-upload-submit');
    const uploadDropzone = document.getElementById('upload-modal-dropzone');
    const uploadFileInput = document.getElementById('upload-file-input');
    const btnBrowseFiles = document.getElementById('btn-browse-files');
    const uploadFilesPreview = document.getElementById('upload-files-preview');
    const uploadFileCount = document.getElementById('upload-file-count');
    const uploadFileItemsList = document.getElementById('upload-file-items-list');
    const btnClearUploadFiles = document.getElementById('btn-clear-upload-files');
    const uploadStatus = document.getElementById('upload-status');
    const uploadCustomFolder = document.getElementById('upload-custom-folder');
    const uploadProgressWrap = document.getElementById('upload-progress-wrap');
    const uploadProgressBar = document.getElementById('upload-progress-bar');
    const uploadProgressText = document.getElementById('upload-progress-text');

    const dragDropOverlay = document.getElementById('drag-drop-overlay');

    // Details Action Buttons
    const btnDetailsCopyPts = document.getElementById('btn-details-copy-pts');
    const btnDetailsExportJson = document.getElementById('btn-details-export-json');
    const btnDetailsExportCsv = document.getElementById('btn-details-export-csv');
    const btnDetailsOpenFinder = document.getElementById('btn-details-open-finder');
    const btnDetailsDuplicate = document.getElementById('btn-details-duplicate');

    // Duplicate Modal Elements
    const btnOpenDuplicate = document.getElementById('btn-open-duplicate');
    const modalDuplicate = document.getElementById('modal-duplicate');
    const modalDuplicateClose = document.getElementById('modal-duplicate-close');
    const modalDuplicateCancel = document.getElementById('modal-duplicate-cancel');
    const modalDuplicateSubmit = document.getElementById('modal-duplicate-submit');
    const dupSourceStatusBadge = document.getElementById('dup-source-status-badge');
    const dupSourcePartDisplay = document.getElementById('dup-source-part-display');
    const dupSourceMetaDisplay = document.getElementById('dup-source-meta-display');
    const dupSourcePart = document.getElementById('dup-source-part');
    const dupSourceStatus = document.getElementById('dup-source-status');
    const dupTargetPart = document.getElementById('dup-target-part');
    const dupTargetStatus = document.getElementById('dup-target-status');
    const dupRenameFiles = document.getElementById('dup-rename-files');
    const dupTargetSpinner = document.getElementById('dup-target-spinner');
    const dupTargetAutocomplete = document.getElementById('dup-target-autocomplete');
    const dupSnippetPreview = document.getElementById('dup-snippet-preview');
    const dupSnippetPartNum = document.getElementById('dup-snippet-part-num');
    const dupSnippetPartName = document.getElementById('dup-snippet-part-name');
    const dupSnippetTagCategory = document.getElementById('dup-snippet-tag-category');
    const dupSnippetTagTemplate = document.getElementById('dup-snippet-tag-template');

    let dupAutocompleteTimer = null;
    let dupAutocompleteResults = [];
    let dupAutocompleteSelectedIdx = -1;

    // Modals
    const modalRun = document.getElementById('modal-run');
    const modalRunClose = document.getElementById('modal-run-close');
    const modalRunCancel = document.getElementById('modal-run-cancel');
    const modalRunStart = document.getElementById('modal-run-start');
    const modalRunPart = document.getElementById('modal-run-part');
    const modalSubmitToggle = document.getElementById('modal-submit-toggle');
    const runOutputBox = document.getElementById('run-output-box');
    const runOutputPre = document.getElementById('run-output-pre');
    const runSpinner = document.getElementById('run-spinner');

    const modalDetails = document.getElementById('modal-details');
    const modalDetailsClose = document.getElementById('modal-details-close');
    const modalDetailsCloseBtn = document.getElementById('modal-details-close-btn');
    const detailsMetaGrid = document.getElementById('details-meta-grid');
    const detailsGallery = document.getElementById('details-gallery');
    const detailsImgCount = document.getElementById('details-img-count');
    const detailsPtsCount = document.getElementById('details-pts-count');
    const detailsPtsTbody = document.getElementById('details-pts-tbody');

    // Image Lightbox / Fullscreen Viewer Elements
    const modalLightbox = document.getElementById('modal-lightbox');
    const lightboxTitle = document.getElementById('lightbox-title');
    const lightboxBadge = document.getElementById('lightbox-badge');
    const lightboxZoomOut = document.getElementById('lightbox-zoom-out');
    const lightboxZoomReset = document.getElementById('lightbox-zoom-reset');
    const lightboxZoomIn = document.getElementById('lightbox-zoom-in');
    const lightboxClose = document.getElementById('lightbox-close');
    const lightboxPrev = document.getElementById('lightbox-prev');
    const lightboxNext = document.getElementById('lightbox-next');
    const lightboxViewport = document.getElementById('lightbox-viewport');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxCounter = document.getElementById('lightbox-counter');
    const lightboxSubinfo = document.getElementById('lightbox-subinfo');

    // WebP Optimizer Modal Elements
    const btnOpenCompress = document.getElementById('btn-open-compress');
    const modalCompress = document.getElementById('modal-compress');
    const modalCompressClose = document.getElementById('modal-compress-close');
    const modalCompressCancel = document.getElementById('modal-compress-cancel');
    const btnStartCompress = document.getElementById('btn-start-compress');
    const statNonWebpCount = document.getElementById('stat-non-webp-count');
    const statNonWebpSize = document.getElementById('stat-non-webp-size');
    const statWebpCount = document.getElementById('stat-webp-count');
    const statWebpSize = document.getElementById('stat-webp-size');
    const statEstSavings = document.getElementById('stat-est-savings');
    const compressTargetSelect = document.getElementById('compress-target-select');
    const compressQualityRange = document.getElementById('compress-quality-range');
    const compressQualityDisplay = document.getElementById('compress-quality-display');
    const compressDeleteToggle = document.getElementById('compress-delete-toggle');
    const compressResizeToggle = document.getElementById('compress-resize-toggle');
    const compressResultBox = document.getElementById('compress-result-box');
    const compressProgress = document.getElementById('compress-progress');
    const compressSummaryBanner = document.getElementById('compress-summary-banner');
    const compressSummaryTitle = document.getElementById('compress-summary-title');
    const compressSummaryDetails = document.getElementById('compress-summary-details');
    const compressFilesListWrap = document.getElementById('compress-files-list-wrap');
    const compressFilesTbody = document.getElementById('compress-files-tbody');

    // Lightbox State
    let lightboxImages = [];
    let currentLightboxIdx = 0;
    let currentZoom = 1.0;
    let panX = 0;
    let panY = 0;
    let isPanning = false;
    let startPanX = 0;
    let startPanY = 0;

    // Navigation Switching
    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            navBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetPane = document.getElementById(targetTab);
            if (targetPane) targetPane.classList.add('active');

            if (targetTab === 'tab-logs') {
                loadExcelLogs();
            } else if (targetTab === 'tab-diff') {
                populateDiffPartSelect();
            } else if (targetTab === 'tab-catalog') {
                loadCatalogTab();
            }
        });
    });

    // Segmented Filter (Belum / Tidak Ada / Done)
    filterBelumBtn.addEventListener('click', () => {
        currentFilter = 'belum';
        updateFilterButtons();
        renderDocGrid();
    });

    filterTidakAdaBtn.addEventListener('click', () => {
        currentFilter = 'tidak_ada_part';
        updateFilterButtons();
        renderDocGrid();
    });

    filterDoneBtn.addEventListener('click', () => {
        currentFilter = 'done';
        updateFilterButtons();
        renderDocGrid();
    });

    function updateFilterButtons() {
        filterBelumBtn.classList.toggle('active', currentFilter === 'belum');
        filterTidakAdaBtn.classList.toggle('active', currentFilter === 'tidak_ada_part');
        filterDoneBtn.classList.toggle('active', currentFilter === 'done');

        const isTidakAda = currentFilter === 'tidak_ada_part';
        const bannerTidakAda = document.getElementById('tidak-ada-banner');
        const btnCheckServer = document.getElementById('btn-check-server-tidak-ada');
        if (bannerTidakAda) bannerTidakAda.style.display = isTidakAda ? 'flex' : 'none';
        if (btnCheckServer) btnCheckServer.style.display = isTidakAda ? 'inline-flex' : 'none';
    }

    // Make Metric Cards clickable to instantly filter view
    countBelumEl?.closest('.metric-card')?.addEventListener('click', () => filterBelumBtn.click());
    countTidakAdaEl?.closest('.metric-card')?.addEventListener('click', () => filterTidakAdaBtn.click());
    countDoneEl?.closest('.metric-card')?.addEventListener('click', () => filterDoneBtn.click());
    countTotalEl?.closest('.metric-card')?.addEventListener('click', () => filterDoneBtn.click());

    // Search input for docs
    docSearchInput.addEventListener('input', () => {
        renderDocGrid();
    });

    btnRefreshAll.addEventListener('click', async () => {
        await loadDocuments();
        await loadExcelLogs();
        showToast('Semua data berhasil dimuat ulang', 'info');
    });

    // =========================================================================
    // DOCUMENTS MANAGEMENT
    // =========================================================================
    async function loadDocuments() {
        try {
            const res = await fetch('/api/documents');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            docsData = data;

            countBelumEl.textContent = data.counts.belum || 0;
            countTidakAdaEl.textContent = data.counts.tidak_ada_part || 0;
            countDoneEl.textContent = data.counts.done || 0;
            countTotalEl.textContent = data.total || 0;

            badgeBelumEl.textContent = data.counts.belum || 0;
            badgeTidakAdaEl.textContent = data.counts.tidak_ada_part || 0;
            badgeDoneEl.textContent = data.counts.done || 0;

            // Auto-switch to active category if default 'belum' tab is currently empty
            if (currentFilter === 'belum' && (data.counts.belum || 0) === 0) {
                if ((data.counts.done || 0) > 0) {
                    currentFilter = 'done';
                } else if ((data.counts.tidak_ada_part || 0) > 0) {
                    currentFilter = 'tidak_ada_part';
                }
                updateFilterButtons();
            }

            populateDiffPartSelect();
            renderDocGrid();
        } catch (err) {
            console.error('Error loading documents:', err);
            showToast('Gagal memuat dokumen: ' + err.message, 'error');
            docGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; padding:3rem 1.5rem; text-align:center;">
                    ${ICONS.alertCircle}
                    <h3 style="margin-top:1rem; color:var(--rose-400);">Gagal Memuat Dokumen</h3>
                    <p style="color:var(--text-muted); margin:0.5rem 0 1.25rem 0;">${err.message}</p>
                    <button class="btn btn-primary" onclick="window.location.reload()">Muat Ulang Halaman</button>
                </div>
            `;
        }
    }

    // =========================================================================
    // CARD DRAG-AND-DROP & IMAGE UPLOAD
    // =========================================================================
    async function uploadFilesToPartCard(files, folderName, status, cardEl) {
        if (!files || files.length === 0) return;

        // Show loading overlay on card
        let loadingOverlay = cardEl ? cardEl.querySelector('.card-uploading-overlay') : null;
        if (!loadingOverlay && cardEl) {
            loadingOverlay = document.createElement('div');
            loadingOverlay.className = 'card-uploading-overlay';
            loadingOverlay.innerHTML = `
                <div class="spinner" style="width:34px; height:34px; border-width:3px;"></div>
                <div style="font-size:0.86rem; font-weight:600; color:#fff;">Mengunggah ${files.length} file...</div>
                <div style="font-size:0.75rem; color:var(--text-muted);">Menyimpan ke part ${folderName}</div>
            `;
            cardEl.appendChild(loadingOverlay);
        }

        try {
            const formData = new FormData();
            formData.append('status', status || 'belum');
            formData.append('folder_name', folderName);
            formData.append('target_folder', folderName);
            for (let i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }

            const res = await fetch('/api/documents/upload', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || `Upload gagal (HTTP ${res.status})`);
            }

            const data = await res.json();
            const count = data.saved_files?.length || files.length;
            showToast(`Berhasil menambahkan ${count} gambar ke part ${folderName}!`, 'success');

            // Reload documents and keep card highlighted
            await loadDocuments();
            const updatedCard = document.querySelector(`[data-card-folder="${folderName}"]`);
            if (updatedCard) {
                updatedCard.classList.add('card-highlight');
                setTimeout(() => updatedCard.classList.remove('card-highlight'), 2500);
            }

            // If details modal is open for this folder, refresh it too
            if (currentDetailsDoc && currentDetailsDoc.folder === folderName) {
                openDetailsModal(currentDetailsDoc.status, folderName);
            }
        } catch (err) {
            console.error('Error uploading files to card:', err);
            showToast('Gagal mengunggah file: ' + err.message, 'error');
        } finally {
            if (loadingOverlay && loadingOverlay.parentNode) {
                loadingOverlay.parentNode.removeChild(loadingOverlay);
            }
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function normalizeSearchToken(str) {
        return (str || '').toLowerCase().replace(/[^a-z0-9]/g, '').replace(/o/g, '0').replace(/i/g, '1');
    }

    function renderDocGrid(highlightFolder = null) {
        const rawQuery = docSearchInput.value.trim();
        const queryLower = rawQuery.toLowerCase();
        const queryNorm = normalizeSearchToken(rawQuery);
        const queryTokens = rawQuery.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean).map(t => normalizeSearchToken(t));

        let list = [];
        if (currentFilter === 'done') list = docsData.done || [];
        else if (currentFilter === 'tidak_ada_part') list = docsData.tidak_ada_part || [];
        else list = docsData.belum || [];

        const filtered = list.filter(item => {
            if (!rawQuery) return true;
            const pNum = item.part_number || '';
            const pName = item.part_name || '';
            const fName = item.folder_name || '';
            const eFile = item.excel_file || '';

            // 1. Standard substring match
            if (pNum.toLowerCase().includes(queryLower) ||
                pName.toLowerCase().includes(queryLower) ||
                fName.toLowerCase().includes(queryLower) ||
                eFile.toLowerCase().includes(queryLower)) {
                return true;
            }

            // 2. Normalized match (ignores dashes, spaces, and O/0 confusion)
            const normTarget = normalizeSearchToken(`${pNum} ${fName} ${pName}`);
            if (queryNorm && normTarget.includes(queryNorm)) {
                return true;
            }

            // 3. Multi-token match (all words e.g. "2120", "3m0a", "j003" exist in target)
            if (queryTokens.length > 0 && queryTokens.every(tok => normTarget.includes(tok))) {
                return true;
            }

            return false;
        });

        docGrid.innerHTML = '';
        if (filtered.length === 0) {
            let emptyTitle = "Tidak Ada Dokumen";
            let emptyMsg = "Tidak ada dokumen pada kategori ini yang cocok dengan pencarian.";
            let quickActionsHtml = "";

            if (!query) {
                const cBelum = docsData.counts?.belum || 0;
                const cTidakAda = docsData.counts?.tidak_ada_part || 0;
                const cDone = docsData.counts?.done || 0;

                if (currentFilter === 'belum') {
                    emptyTitle = "Antrean 'Belum Dikerjakan' Kosong";
                    emptyMsg = "Semua dokumen telah diproses. Dokumen Anda tersimpan rapi di kategori lainnya:";
                    quickActionsHtml = `
                        <div style="display:flex; gap:0.75rem; justify-content:center; flex-wrap:wrap; margin-top:1.25rem;">
                            ${cTidakAda > 0 ? `
                                <button type="button" class="btn btn-outline" id="quick-btn-tidak-ada" style="border-color:var(--rose-500); color:var(--rose-400);">
                                    ${ICONS.alertCircle} Lihat Belum Ada Part (${cTidakAda})
                                </button>` : ''}
                            ${cDone > 0 ? `
                                <button type="button" class="btn btn-primary" id="quick-btn-done">
                                    ${ICONS.checkCircle} Lihat Sudah Selesai (${cDone})
                                </button>` : ''}
                        </div>
                    `;
                } else if (currentFilter === 'tidak_ada_part') {
                    emptyTitle = "Tidak Ada Part yang Belum Terdaftar";
                    emptyMsg = "Semua part yang ada di folder documents sudah terdaftar di master FactoryHub.";
                } else if (currentFilter === 'done') {
                    emptyTitle = "Belum Ada Dokumen Selesai";
                    emptyMsg = "Jalankan otomatisasi pada dokumen di antrean 'Belum Dikerjakan' untuk menyelesaikannya.";
                }
            }

            docGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; padding:3.5rem 1.5rem; text-align:center;">
                    ${ICONS.folder}
                    <h3 style="margin-top:1rem; font-size:1.15rem; font-weight:600;">${emptyTitle}</h3>
                    <p style="color:var(--text-muted); max-width:520px; margin:0.5rem auto 0 auto; line-height:1.5;">${emptyMsg}</p>
                    ${quickActionsHtml}
                </div>
            `;

            const btnQuickTidakAda = document.getElementById('quick-btn-tidak-ada');
            if (btnQuickTidakAda) {
                btnQuickTidakAda.addEventListener('click', () => {
                    filterTidakAdaBtn.click();
                });
            }
            const btnQuickDone = document.getElementById('quick-btn-done');
            if (btnQuickDone) {
                btnQuickDone.addEventListener('click', () => {
                    filterDoneBtn.click();
                });
            }
            return;
        }

        filtered.forEach(item => {
            const card = document.createElement('div');
            card.className = 'doc-card';
            card.setAttribute('data-card-folder', item.folder_name);
            if (highlightFolder && item.folder_name === highlightFolder) {
                card.classList.add('card-highlight');
            }

            // Badges
            let statusBadge = '';
            if (item.status === 'done') {
                statusBadge = `<span class="badge-tag done">${ICONS.checkCircle} DONE</span>`;
            } else if (item.status === 'tidak_ada_part') {
                statusBadge = `<span class="badge-tag tidak_ada_part">${ICONS.alertCircle} BELUM ADA PART</span>`;
            } else {
                statusBadge = `<span class="badge-tag belum">${ICONS.clock} BELUM</span>`;
            }

            const typeBadge = `<span class="badge-tag ${item.file_type}">${item.file_type.toUpperCase()}</span>`;

            // Previews & Source Badge
            const previews = item.preview_details || (item.preview_images || []).map((url, i) => ({
                url: url,
                filename: `sketsa_${i+1}.png`,
                dimensions: '',
                size_kb: '',
                source: item.image_source || 'extracted',
                source_label: item.image_source_label || ''
            }));

            let thumbsHtml = '';
            if (previews.length > 0) {
                const isFolder = item.image_source === 'folder';
                const badgeText = isFolder ? 'Folder Screenshot' : 'Sketsa Ekstrak';
                const badgeClass = isFolder ? 'folder' : 'extracted';
                thumbsHtml = `
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
                        <span class="preview-source-badge ${badgeClass}" style="font-size: 0.68rem; padding: 0.15rem 0.45rem;">
                            ${isFolder ? '📁' : '⚙️'} ${badgeText} (${item.total_images || previews.length})
                        </span>
                        <span style="font-size: 0.7rem; color: var(--text-muted);">Klik untuk perbesar</span>
                    </div>
                    <div class="doc-thumbs-preview" style="margin-bottom: 0.5rem;">
                        ${previews.slice(0, 5).map((p, idx) => `
                            <img src="${p.url}" class="thumb-preview-img" data-idx="${idx}" alt="Sketsa ${idx+1}" title="${p.filename || 'Sketsa'} - Klik untuk perbesar" loading="lazy" onerror="this.style.display='none'">
                        `).join('')}
                        ${previews.length > 5 ? `<div class="thumb-more-badge" title="Lihat semua ${previews.length} sketsa">+${previews.length - 5}</div>` : ''}
                    </div>
                `;
            } else {
                thumbsHtml = `
                    <div style="font-size: 0.76rem; color: var(--text-muted); padding: 0.4rem 0; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem;">
                        <span class="preview-source-badge extracted" style="font-size: 0.68rem; padding: 0.15rem 0.45rem;">⚙️ Ekstrak Dokumen</span>
                        <span>Sketsa diekstrak saat otomasi</span>
                    </div>
                `;
            }

            // Move Actions Group
            let moveButtonsHtml = '';
            if (item.status === 'belum') {
                moveButtonsHtml = `
                    <div class="btn-move-group">
                        <button class="btn btn-outline btn-sm btn-move" data-folder="${item.folder_name}" data-from="belum" data-to="done" title="Tandai Selesai">
                            ${ICONS.checkCircle} Selesai
                        </button>
                        <button class="btn btn-outline btn-sm btn-move" data-folder="${item.folder_name}" data-from="belum" data-to="tidak_ada_part" title="Tandai Belum Ada Part">
                            ${ICONS.alertCircle} Tidak Ada
                        </button>
                    </div>
                `;
            } else if (item.status === 'tidak_ada_part') {
                moveButtonsHtml = `
                    <div class="btn-move-group">
                        <button class="btn btn-outline btn-sm btn-move" data-folder="${item.folder_name}" data-from="tidak_ada_part" data-to="belum" title="Kembalikan ke Belum">
                            ${ICONS.arrowLeft} Belum
                        </button>
                        <button class="btn btn-outline btn-sm btn-move" data-folder="${item.folder_name}" data-from="tidak_ada_part" data-to="done" title="Tandai Selesai">
                            ${ICONS.checkCircle} Selesai
                        </button>
                    </div>
                `;
            } else { // done
                moveButtonsHtml = `
                    <div class="btn-move-group">
                        <button class="btn btn-outline btn-sm btn-move" data-folder="${item.folder_name}" data-from="done" data-to="belum" title="Kembalikan ke Belum">
                            ${ICONS.arrowLeft} Belum
                        </button>
                        <button class="btn btn-outline btn-sm btn-move" data-folder="${item.folder_name}" data-from="done" data-to="tidak_ada_part" title="Pindah ke Tidak Ada Part">
                            ${ICONS.alertCircle} Tidak Ada
                        </button>
                    </div>
                `;
            }

            card.innerHTML = `
                <!-- Drop Overlay for Drag-and-Drop -->
                <div class="card-drop-overlay">
                    <div class="card-drop-content">
                        <svg class="svg-icon drop-bounce-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                        <div class="drop-text-primary">Lepaskan Gambar di Sini</div>
                        <div class="drop-text-sub">Tambah sketsa ke <strong>${item.part_number}</strong></div>
                    </div>
                </div>

                <div>
                    <div class="doc-card-top">
                        <div class="doc-badges">
                            ${statusBadge}
                            ${typeBadge}
                        </div>
                        ${moveButtonsHtml}
                    </div>

                    <div class="doc-part-number">${item.part_number}</div>
                    <div class="doc-part-name">${item.part_name || '<em>(Part Name tidak tercantum)</em>'}</div>

                    <div class="doc-meta-pills">
                        <span class="meta-pill"><strong>Doc:</strong> ${item.doc_number || '-'}</span>
                        <span class="meta-pill"><strong>Model:</strong> ${item.model || '-'}</span>
                        <span class="meta-pill"><strong>Gambar:</strong> ${item.image_count} file</span>
                    </div>

                    ${thumbsHtml}

                    <div class="card-dropzone-inline" data-folder="${item.folder_name}" data-status="${item.status}" title="Klik untuk pilih gambar atau tarik & lepas file gambar ke sini">
                        <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                        <span>Drop gambar di sini atau <strong style="color:var(--accent-blue);">pilih file</strong></span>
                        <input type="file" class="card-file-input" accept="image/*,.xlsx,.pdf" multiple style="display:none;">
                    </div>
                </div>

                <div class="doc-actions" style="margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    ${item.status === 'tidak_ada_part' ? `
                        <button class="btn btn-warning btn-check-single-server" data-folder="${item.folder_name}" data-part="${item.part_number}" style="flex: 1;" title="Cek apakah part ini sudah ditambahkan di server FactoryHub">
                            <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg>
                            <span>Cek Server</span>
                        </button>
                    ` : ''}
                    <button class="btn btn-primary btn-run" data-part="${item.part_number}" data-folder="${item.folder_name}" style="flex: 1;">
                        ${ICONS.play} Jalankan
                    </button>
                    <button class="btn btn-secondary btn-duplicate" data-status="${item.status}" data-folder="${item.folder_name}" data-part="${item.part_number}" data-name="${(item.part_name || '').replace(/"/g, '&quot;')}" data-doc="${item.excel_file || ''}" data-images="${item.image_count || 0}" title="Duplikasi Data & Gambar ke Part Baru">
                        <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg> Duplikat
                    </button>
                    <button class="btn btn-secondary btn-compare" data-part="${item.part_number}" title="Lihat Perbandingan Diff">
                        ${ICONS.diff} Diff
                    </button>
                    <button class="btn btn-secondary btn-details" data-status="${item.status}" data-folder="${item.folder_name}" title="Detail Lengkap">
                        ${ICONS.info} Detail
                    </button>
                    <button class="btn btn-secondary btn-finder" data-status="${item.status}" data-folder="${item.folder_name}" title="Buka folder di Finder Mac">
                        ${ICONS.folder} Finder
                    </button>
                </div>
            `;

            // Attach thumbnail click events inside card
            card.querySelectorAll('.thumb-preview-img').forEach(imgEl => {
                imgEl.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const idx = parseInt(imgEl.getAttribute('data-idx') || '0', 10);
                    openLightbox(previews, idx, `${item.part_number} - Pratinjau Sketsa Part`);
                });
            });

            const moreBadge = card.querySelector('.thumb-more-badge');
            if (moreBadge) {
                moreBadge.addEventListener('click', (e) => {
                    e.stopPropagation();
                    openLightbox(previews, 5, `${item.part_number} - Pratinjau Sketsa Part`);
                });
            }

            // Drag and drop event listeners on card
            let dragCounter = 0;
            card.addEventListener('dragenter', (e) => {
                if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes('Files')) {
                    e.preventDefault();
                    dragCounter++;
                    card.classList.add('drag-over');
                }
            });

            card.addEventListener('dragover', (e) => {
                if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes('Files')) {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = 'copy';
                }
            });

            card.addEventListener('dragleave', (e) => {
                dragCounter--;
                if (dragCounter <= 0) {
                    dragCounter = 0;
                    card.classList.remove('drag-over');
                }
            });

            card.addEventListener('drop', async (e) => {
                e.preventDefault();
                dragCounter = 0;
                card.classList.remove('drag-over');
                if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                    await uploadFilesToPartCard(e.dataTransfer.files, item.folder_name, item.status, card);
                }
            });

            // Inline dropzone click & file picker
            const dropzoneInline = card.querySelector('.card-dropzone-inline');
            const fileInput = card.querySelector('.card-file-input');
            if (dropzoneInline && fileInput) {
                dropzoneInline.addEventListener('click', (e) => {
                    e.stopPropagation();
                    fileInput.click();
                });
                fileInput.addEventListener('change', async (e) => {
                    if (fileInput.files && fileInput.files.length > 0) {
                        await uploadFilesToPartCard(fileInput.files, item.folder_name, item.status, card);
                    }
                });
            }

            // Clipboard paste on focused card
            card.setAttribute('tabindex', '0');
            card.addEventListener('paste', async (e) => {
                const items = e.clipboardData?.items;
                if (!items) return;
                const pastedFiles = [];
                for (let i = 0; i < items.length; i++) {
                    if (items[i].type.indexOf('image') !== -1) {
                        const blob = items[i].getAsFile();
                        if (blob) {
                            const ext = items[i].type.split('/')[1] || 'png';
                            pastedFiles.push(new File([blob], `screenshot_${Date.now()}_${i+1}.${ext}`, { type: items[i].type }));
                        }
                    }
                }
                if (pastedFiles.length > 0) {
                    e.preventDefault();
                    await uploadFilesToPartCard(pastedFiles, item.folder_name, item.status, card);
                }
            });

            docGrid.appendChild(card);
        });

        // Attach event listeners to card buttons
        docGrid.querySelectorAll('.btn-check-single-server').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const folder = btn.getAttribute('data-folder');
                const part = btn.getAttribute('data-part');
                await checkServerAvailability(folder, part);
            });
        });

        docGrid.querySelectorAll('.btn-run').forEach(btn => {
            btn.addEventListener('click', () => {
                const part = btn.getAttribute('data-part') || btn.getAttribute('data-folder');
                openRunModal(part);
            });
        });

        docGrid.querySelectorAll('.btn-duplicate').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const part = btn.getAttribute('data-part') || btn.getAttribute('data-folder');
                const status = btn.getAttribute('data-status') || 'belum';
                const folder = btn.getAttribute('data-folder') || part;
                const name = btn.getAttribute('data-name') || '';
                const doc = btn.getAttribute('data-doc') || '';
                const images = btn.getAttribute('data-images') || '0';
                openDuplicateModal({ part, status, folder, name, doc, images });
            });
        });

        docGrid.querySelectorAll('.btn-details').forEach(btn => {
            btn.addEventListener('click', () => {
                const status = btn.getAttribute('data-status');
                const folder = btn.getAttribute('data-folder');
                openDetailsModal(status, folder);
            });
        });

        docGrid.querySelectorAll('.btn-compare').forEach(btn => {
            btn.addEventListener('click', () => {
                const part = btn.getAttribute('data-part');
                switchToDiffForPart(part);
            });
        });

        docGrid.querySelectorAll('.btn-finder').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const status = btn.getAttribute('data-status');
                const folder = btn.getAttribute('data-folder');
                openInFinder(folder, status);
            });
        });

        docGrid.querySelectorAll('.btn-move').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const folder = btn.getAttribute('data-folder');
                const fromStatus = btn.getAttribute('data-from');
                const toStatus = btn.getAttribute('data-to');
                await moveDocumentFolder(folder, fromStatus, toStatus);
            });
        });
    }

    async function openInFinder(folder, status = '') {
        try {
            const res = await fetch('/api/documents/open-finder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ folder_name: folder, status: status })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Gagal membuka Finder');
            showToast(`Membuka folder '${folder}' di Finder Mac`, 'info');
        } catch (err) {
            console.error('Error opening Finder:', err);
            showToast('Gagal membuka Finder: ' + err.message, 'error');
        }
    }

    async function moveDocumentFolder(folder, fromStatus, toStatus) {
        try {
            const res = await fetch('/api/documents/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    folder_name: folder,
                    from_status: fromStatus,
                    to_status: toStatus
                })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Gagal memindahkan folder');

            showToast(`Part '${folder}' dipindahkan ke '${toStatus}'`, 'success');
            await loadDocuments();
        } catch (err) {
            console.error('Error moving doc:', err);
            showToast(err.message, 'error');
        }
    }

    // =========================================================================
    // FACTORYHUB SERVER AVAILABILITY CHECK
    // =========================================================================
    async function checkServerAvailability(folderName = null, partDisplay = null) {
        const modal = document.getElementById('modal-server-check-result');
        const loadingEl = document.getElementById('server-check-loading');
        const resultsEl = document.getElementById('server-check-results');
        const statMoved = document.getElementById('server-check-moved-count');
        const statRemaining = document.getElementById('server-check-remaining-count');
        const movedSection = document.getElementById('server-check-moved-section');
        const movedList = document.getElementById('server-check-moved-list');
        const movedListCount = document.getElementById('server-check-moved-list-count');
        const remainingSection = document.getElementById('server-check-remaining-section');
        const remainingList = document.getElementById('server-check-remaining-list');
        const remainingListCount = document.getElementById('server-check-remaining-list-count');
        const gotoBelumBtn = document.getElementById('modal-server-check-goto-belum');

        // Reset & open modal in loading state
        if (modal) {
            modal.classList.add('active');
            if (loadingEl) {
                loadingEl.style.display = 'block';
                loadingEl.innerHTML = `
                    <div class="spinner" style="width: 38px; height: 38px; border-width: 3px; border-top-color: #f59e0b; margin: 0 auto 1.25rem auto;"></div>
                    <h4 style="font-size: 1.1rem; margin-bottom: 0.5rem; color: #fff;">Menghubungi Server FactoryHub...</h4>
                    <p id="server-check-loading-desc" style="color: var(--text-muted); font-size: 0.85rem; max-width: 440px; margin: 0 auto; line-height: 1.5;">
                        ${folderName ? `Sedang memeriksa apakah part <strong>${escapeHtml(partDisplay || folderName)}</strong> sudah didaftarkan di server FactoryHub...` : `Sedang memeriksa apakah part di kategori <strong>Belum Ada Part</strong> sudah didaftarkan ke server FactoryHub. Proses ini memakan waktu beberapa detik.`}
                    </p>
                `;
            }
            if (resultsEl) resultsEl.style.display = 'none';
            if (gotoBelumBtn) gotoBelumBtn.style.display = 'none';
        }

        try {
            const res = await fetch('/api/documents/check-server-availability', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    folder_name: folderName,
                    live: true
                })
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Gagal mengecek ketersediaan server');

            // Refresh document list in background
            await loadDocuments();

            // Populate results
            if (loadingEl) loadingEl.style.display = 'none';
            if (resultsEl) resultsEl.style.display = 'block';

            const movedCount = data.moved_count || 0;
            const remainingCount = data.remaining_count || 0;

            if (statMoved) statMoved.textContent = movedCount;
            if (statRemaining) statRemaining.textContent = remainingCount;
            if (movedListCount) movedListCount.textContent = movedCount;
            if (remainingListCount) remainingListCount.textContent = remainingCount;

            // Moved list
            if (movedList) {
                if (movedCount === 0) {
                    movedSection.style.display = 'none';
                } else {
                    movedSection.style.display = 'block';
                    movedList.innerHTML = data.moved_parts.map(p => `
                        <div class="server-check-item">
                            <div style="display: flex; align-items: center; gap: 0.6rem;">
                                <span class="badge-tag done" style="font-size: 0.72rem; padding: 2px 6px;">SUDAH ADA</span>
                                <div>
                                    <div class="server-check-part-code">${escapeHtml(p.folder_name)}</div>
                                    <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(p.details || p.category || '')}</div>
                                </div>
                            </div>
                            <span style="font-size: 0.75rem; color: #34d399; font-weight: 600;">➔ Dipindahkan ke 'Belum'</span>
                        </div>
                    `).join('');
                }
            }

            // Remaining list
            if (remainingList) {
                if (remainingCount === 0) {
                    remainingSection.style.display = 'none';
                } else {
                    remainingSection.style.display = 'block';
                    remainingList.innerHTML = data.remaining_parts.map(p => `
                        <div class="server-check-item">
                            <div style="display: flex; align-items: center; gap: 0.6rem;">
                                <span class="badge-tag tidak_ada_part" style="font-size: 0.72rem; padding: 2px 6px;">BELUM ADA</span>
                                <div>
                                    <div class="server-check-part-code">${escapeHtml(p.folder_name)}</div>
                                    <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(p.reason || 'Belum terdaftar di FactoryHub')}</div>
                                </div>
                            </div>
                            <span style="font-size: 0.75rem; color: #fbbf24;">Tetap di 'Belum Ada Part'</span>
                        </div>
                    `).join('');
                }
            }

            if (movedCount > 0) {
                if (gotoBelumBtn) gotoBelumBtn.style.display = 'inline-flex';
                showToast(`[✓] ${movedCount} part ditemukan di server & dipindahkan ke Belum Dikerjakan!`, 'success');
            } else {
                showToast(`Pengecekan selesai. Belum ada part baru yang terdaftar di server.`, 'info');
            }

        } catch (err) {
            console.error('Error checking server availability:', err);
            showToast('Gagal memeriksa server: ' + err.message, 'error');
            if (loadingEl) {
                loadingEl.innerHTML = `
                    <div style="color: var(--rose-400); margin-bottom: 0.75rem;">
                        <svg class="svg-icon" style="width: 32px; height: 32px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    </div>
                    <h4 style="color: #fff; margin-bottom: 0.5rem;">Gagal Memeriksa Server FactoryHub</h4>
                    <p style="color: var(--text-muted); font-size: 0.85rem; max-width: 420px; margin: 0 auto 1.25rem auto;">${escapeHtml(err.message)}</p>
                    <button class="btn btn-secondary" onclick="document.getElementById('modal-server-check-result')?.classList.remove('active')">Tutup</button>
                `;
            }
        }
    }

    // Modal Server Check Result & Toolbar/Banner event handlers
    const btnCheckServerTidakAda = document.getElementById('btn-check-server-tidak-ada');
    const btnBannerCheckServer = document.getElementById('btn-banner-check-server');
    if (btnCheckServerTidakAda) {
        btnCheckServerTidakAda.addEventListener('click', () => checkServerAvailability(null));
    }
    if (btnBannerCheckServer) {
        btnBannerCheckServer.addEventListener('click', () => checkServerAvailability(null));
    }

    const modalServerCheck = document.getElementById('modal-server-check-result');
    const modalServerCheckClose = document.getElementById('modal-server-check-close');
    const modalServerCheckDismiss = document.getElementById('modal-server-check-dismiss');
    const modalServerCheckGotoBelum = document.getElementById('modal-server-check-goto-belum');

    if (modalServerCheckClose) {
        modalServerCheckClose.addEventListener('click', () => modalServerCheck.classList.remove('active'));
    }
    if (modalServerCheckDismiss) {
        modalServerCheckDismiss.addEventListener('click', () => modalServerCheck.classList.remove('active'));
    }
    if (modalServerCheckGotoBelum) {
        modalServerCheckGotoBelum.addEventListener('click', () => {
            modalServerCheck.classList.remove('active');
            filterBelumBtn.click();
        });
    }
    if (modalServerCheck) {
        modalServerCheck.addEventListener('click', (e) => {
            if (e.target === modalServerCheck) modalServerCheck.classList.remove('active');
        });
    }

    // =========================================================================
    // DETAILS MODAL
    // =========================================================================
    async function openDetailsModal(status, folder) {
        modalDetails.classList.add('active');
        detailsMetaGrid.innerHTML = 'Memuat metadata...';
        detailsGallery.innerHTML = '<div style="padding: 1rem; color: var(--text-muted); grid-column: 1 / -1;"><span class="spinner" style="width:14px; height:14px; margin-right:6px; display:inline-block; vertical-align:middle;"></span> Memuat galeri sketsa...</div>';
        detailsPtsTbody.innerHTML = '<tr><td colspan="5">Memuat titik inspeksi...</td></tr>';

        try {
            const res = await fetch(`/api/documents/${status}/${folder}/details`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Gagal memuat detail');

            document.getElementById('modal-details-title').textContent = `Detail Part: ${data.part_number}`;
            detailsImgCount.textContent = data.images_count;
            detailsPtsCount.textContent = data.all_points_count;
            currentDetailsDoc = { status, folder, part_number: data.part_number, data };

            const sourceBadge = document.getElementById('details-source-badge');
            if (sourceBadge) {
                const isFolder = data.image_source === 'folder';
                sourceBadge.className = `preview-source-badge ${isFolder ? 'folder' : 'extracted'}`;
                sourceBadge.textContent = `${isFolder ? '📁' : '⚙️'} ${data.image_source_label || (isFolder ? 'Folder Screenshot' : 'Ekstrak Dokumen')}`;
            }

            detailsMetaGrid.innerHTML = `
                <div class="details-meta-item"><strong>Part Number:</strong> ${data.part_number}</div>
                <div class="details-meta-item"><strong>Part Name:</strong> ${data.metadata.part_name || '-'}</div>
                <div class="details-meta-item"><strong>Doc Number:</strong> ${data.metadata.doc_number || '-'}</div>
                <div class="details-meta-item"><strong>Model:</strong> ${data.metadata.model || '-'}</div>
                <div class="details-meta-item"><strong>Tipe File:</strong> ${data.file_type.toUpperCase()}</div>
                <div class="details-meta-item"><strong>File:</strong> ${data.document_file}</div>
            `;

            if (data.images && data.images.length > 0) {
                detailsGallery.innerHTML = data.images.map((img, idx) => {
                    const url = typeof img === 'string' ? img : img.url;
                    const fn = typeof img === 'object' ? img.filename : (url.split('/').pop() || `sketsa_${idx+1}.png`);
                    const dim = (typeof img === 'object' && img.dimensions) ? img.dimensions : (typeof img === 'object' && img.width ? `${img.width} × ${img.height} px` : '-');
                    const size = (typeof img === 'object' && img.size_kb) ? `${img.size_kb} KB` : '-';
                    return `
                        <div class="gallery-card" data-idx="${idx}" title="Klik untuk memperbesar gambar">
                            <div class="gallery-card-img-wrap">
                                <img src="${url}" alt="${fn}" loading="lazy" onerror="this.src='/static/placeholder.svg'">
                                <span class="gallery-zoom-badge">
                                    <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg> Perbesar
                                </span>
                            </div>
                            <div class="gallery-card-info">
                                <div class="gallery-card-name" title="${fn}">${fn}</div>
                                <div class="gallery-card-meta">
                                    <span>${dim}</span>
                                    <span>${size}</span>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');

                detailsGallery.querySelectorAll('.gallery-card').forEach(cardEl => {
                    cardEl.addEventListener('click', () => {
                        const idx = parseInt(cardEl.getAttribute('data-idx') || '0', 10);
                        openLightbox(data.images, idx, `${data.part_number} - Detail Sketsa`);
                    });
                });
            } else {
                detailsGallery.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem; padding: 1.5rem; text-align: center; grid-column: 1 / -1;">Tidak ada file gambar fisik (ekstrak tersemat otomatis saat otomasi).</p>';
            }

            if (data.inspection_points && data.inspection_points.length > 0) {
                detailsPtsTbody.innerHTML = data.inspection_points.map(pt => `
                    <tr>
                        <td><strong>${pt.item_no || '-'}</strong></td>
                        <td>${pt.inspection_item || '-'}</td>
                        <td><code>${pt.standard || '-'}</code></td>
                        <td>${pt.method || '-'}</td>
                        <td>${pt.master_data || '-'}</td>
                    </tr>
                `).join('');
            } else {
                detailsPtsTbody.innerHTML = '<tr><td colspan="5">Tidak ada titik inspeksi yang terdeteksi.</td></tr>';
            }
        } catch (err) {
            console.error(err);
            showToast('Gagal memuat detail part: ' + err.message, 'error');
        }
    }

    modalDetailsClose.addEventListener('click', () => modalDetails.classList.remove('active'));
    modalDetailsCloseBtn.addEventListener('click', () => modalDetails.classList.remove('active'));

    const btnDetailsAddImg = document.getElementById('btn-details-add-img');
    const detailsAddImgInput = document.getElementById('details-add-img-input');
    if (btnDetailsAddImg && detailsAddImgInput) {
        btnDetailsAddImg.addEventListener('click', () => {
            detailsAddImgInput.click();
        });
        detailsAddImgInput.addEventListener('change', async () => {
            if (detailsAddImgInput.files && detailsAddImgInput.files.length > 0 && currentDetailsDoc) {
                const cardEl = document.querySelector(`[data-card-folder="${currentDetailsDoc.folder}"]`);
                await uploadFilesToPartCard(detailsAddImgInput.files, currentDetailsDoc.folder, currentDetailsDoc.status, cardEl);
            }
        });
    }

    if (detailsGallery) {
        detailsGallery.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
        });
        detailsGallery.addEventListener('drop', async (e) => {
            e.preventDefault();
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0 && currentDetailsDoc) {
                const cardEl = document.querySelector(`[data-card-folder="${currentDetailsDoc.folder}"]`);
                await uploadFilesToPartCard(e.dataTransfer.files, currentDetailsDoc.folder, currentDetailsDoc.status, cardEl);
            }
        });
    }

    // =========================================================================
    // RUN AUTOMATION MODAL & LIVE PREVIEW (REQUIREMENT 4 & 10)
    // =========================================================================
    async function loadRunModalImagePreview(part, scanMode = 'auto') {
        const galleryEl = document.getElementById('run-image-preview-gallery');
        const badgeEl = document.getElementById('run-preview-badge');
        if (!galleryEl || !badgeEl) return;

        badgeEl.className = 'preview-source-badge';
        badgeEl.textContent = 'Memuat pratinjau...';
        galleryEl.innerHTML = '<div style="font-size: 0.8rem; color: var(--text-muted); padding: 0.6rem; grid-column: 1 / -1;"><span class="spinner" style="width:14px; height:14px; margin-right: 6px; display:inline-block; vertical-align:middle;"></span> Memuat daftar gambar upload...</div>';

        try {
            const modeParam = scanMode ? `?scan_mode=${encodeURIComponent(scanMode)}` : '';
            const res = await fetch(`/api/part/${encodeURIComponent(part)}/preview-images${modeParam}`);
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || 'Gagal memuat gambar');

            const isFolder = data.source === 'folder';
            badgeEl.className = `preview-source-badge ${isFolder ? 'folder' : 'extracted'}`;
            badgeEl.textContent = `${isFolder ? '📁' : '⚙️'} ${data.source_label} (${data.total_images} file)`;

            if (data.images && data.images.length > 0) {
                galleryEl.innerHTML = data.images.map((img, idx) => `
                    <div class="run-img-thumb-card" data-idx="${idx}" title="${img.filename} (${img.dimensions}) - Klik untuk perbesar">
                        <img src="${img.url}" alt="${img.filename}" loading="lazy">
                        <div class="thumb-overlay-name">${img.filename}</div>
                    </div>
                `).join('');

                galleryEl.querySelectorAll('.run-img-thumb-card').forEach(cardEl => {
                    cardEl.addEventListener('click', () => {
                        const idx = parseInt(cardEl.getAttribute('data-idx') || '0', 10);
                        openLightbox(data.images, idx, `${part} - Pratinjau Upload FactoryHub`);
                    });
                });
            } else {
                galleryEl.innerHTML = `
                    <div style="font-size: 0.78rem; color: var(--text-muted); padding: 0.75rem; grid-column: 1 / -1; text-align: center;">
                        Tidak ada file sketsa/gambar yang terdeteksi untuk mode ini.<br>
                        <em>Checksheet akan disimpan ke FactoryHub tanpa lampiran gambar.</em>
                    </div>
                `;
            }
        } catch (err) {
            console.error('Error loading run modal preview:', err);
            badgeEl.textContent = 'Gagal memuat';
            galleryEl.innerHTML = `<div style="font-size: 0.78rem; color: var(--accent-red); padding: 0.6rem; grid-column: 1 / -1;">${err.message}</div>`;
        }
    }

    function openRunModal(part) {
        modalRunPart.value = part;
        runOutputBox.style.display = 'none';
        runOutputPre.textContent = '';
        if (runSpinner) runSpinner.style.display = 'none';
        modalRunStart.disabled = false;
        modalRunStart.innerHTML = `${ICONS.play} <span>Mulai Otomasi</span>`;
        modalRunCancel.textContent = 'Batal';
        modalRun.classList.add('active');

        const selectedRadio = document.querySelector('input[name="modal-scan-mode"]:checked');
        const scanMode = selectedRadio ? selectedRadio.value : 'auto';
        loadRunModalImagePreview(part, scanMode);
    }

    // Dynamic reload preview when scan mode changes
    document.querySelectorAll('input[name="modal-scan-mode"]').forEach(radio => {
        radio.addEventListener('change', () => {
            const part = modalRunPart.value;
            if (part && modalRun.classList.contains('active')) {
                loadRunModalImagePreview(part, radio.value);
            }
        });
    });

    modalRunClose.addEventListener('click', () => modalRun.classList.remove('active'));
    modalRunCancel.addEventListener('click', () => modalRun.classList.remove('active'));

    modalRunStart.addEventListener('click', async () => {
        const part = modalRunPart.value;
        const selectedRadio = document.querySelector('input[name="modal-scan-mode"]:checked');
        const scanMode = selectedRadio ? selectedRadio.value : 'auto';
        const submit = modalSubmitToggle.checked;

        modalRunStart.disabled = true;
        modalRunStart.innerHTML = `<span class="spinner"></span> <span>Sedang Berjalan...</span>`;
        modalRunCancel.textContent = 'Tutup Jendela';
        runOutputBox.style.display = 'block';
        if (runSpinner) runSpinner.style.display = 'inline-block';

        let initText = `[*] Memulai otomasi checksheet untuk part: ${part}...\n[*] Mode Scan: ${scanMode} | Auto-Submit: ${submit}\n[*] Membuka browser Chrome dan login ke FactoryHub...\n`;
        if (!submit) {
            initText += `[*] Jendela browser akan terbuka di layar Anda untuk ditinjau.\n[*] Form dan titik inspeksi akan diisi secara otomatis.\n[*] Silakan periksa dan klik 'Update Template' / 'Save Template' di browser Anda.\n[*] Sistem akan otomatis mendeteksi saat Anda mengklik submit di browser...\n`;
        }
        runOutputPre.textContent = initText;

        try {
            const res = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    part: part,
                    scan_mode: scanMode,
                    submit: submit,
                    headless: false
                })
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Terjadi kesalahan saat otomasi');

            const result = data.result || {};
            const status = result.status || 'prepared';

            if (runSpinner) runSpinner.style.display = 'none';

            if (status === 'submitted') {
                runOutputPre.textContent += `\n[✓] SUKSES: Form checksheet telah disubmit dan tersimpan di FactoryHub!\n[✓] Folder dokumen otomatis dipindahkan ke 'Done'.\n`;
            } else if (status === 'prepared') {
                runOutputPre.textContent += `\n[✓] Selesai: Form checksheet telah terisi di browser.\n`;
            } else {
                runOutputPre.textContent += `\n[✓] Selesai! Status: ${status}\n`;
            }

            if (result.diff) {
                currentDiffData = { part: part, ...result.diff };
                runOutputPre.textContent += `[*] Ringkasan Diff: ${result.diff.summary}\n`;
                renderDiffTab(currentDiffData);
            }

            // AUTO-MOVE LOGIC & UI CARD TRANSITION
            if (status === 'part_not_registered') {
                runOutputPre.textContent += `[!] Part belum terdaftar di FactoryHub. Folder otomatis dipindahkan ke 'documents/tidak_ada_part/${part}'.\n`;
                showToast(`Part '${part}' belum terdaftar di Master Part. Otomatis dipindahkan ke 'Belum Ada Part'!`, 'error');
                
                // Automatically switch view to 'tidak_ada_part'
                currentFilter = 'tidak_ada_part';
                updateFilterButtons();
            } else {
                showToast(`Part '${part}' selesai diproses dan otomatis dipindahkan ke 'Done'!`, 'success');
                
                // Automatically switch view to 'done'
                currentFilter = 'done';
                updateFilterButtons();
            }

            modalRunCancel.textContent = 'Selesai & Tutup';
            await loadDocuments();
            await loadExcelLogs();
            renderDocGrid(part); // Highlight the newly moved card
        } catch (err) {
            console.error(err);
            if (runSpinner) runSpinner.style.display = 'none';
            runOutputPre.textContent += `\n[!] Error: ${err.message}\n`;
            showToast('Gagal eksekusi: ' + err.message, 'error');
        } finally {
            modalRunStart.disabled = false;
            modalRunStart.innerHTML = `${ICONS.play} <span>Mulai Otomasi</span>`;
        }
    });

    // =========================================================================
    // BATCH SEARCH TAB
    // =========================================================================
    btnQuickBelum.addEventListener('click', () => {
        if (!docsData.belum || docsData.belum.length === 0) {
            showToast('Tidak ada part di daftar Belum', 'info');
            return;
        }
        const parts = docsData.belum.map(d => d.part_number);
        searchInputArea.value = parts.join(', ');
    });

    btnQuickTidakAda.addEventListener('click', () => {
        if (!docsData.tidak_ada_part || docsData.tidak_ada_part.length === 0) {
            showToast('Tidak ada part di daftar Belum Ada Part', 'info');
            return;
        }
        const parts = docsData.tidak_ada_part.map(d => d.part_number);
        searchInputArea.value = parts.join(', ');
    });

    btnExecuteSearch.addEventListener('click', async () => {
        const query = searchInputArea.value.trim();
        if (!query) {
            showToast('Harap masukkan nomor part terlebih dahulu', 'error');
            return;
        }

        btnExecuteSearch.disabled = true;
        btnExecuteSearch.innerHTML = `<span class="spinner"></span> Memeriksa ke FactoryHub...`;

        try {
            const res = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query })
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Gagal mengecek part');

            // Summary banner
            searchSummary.style.display = 'flex';
            statSearchTotal.textContent = data.total;
            statSearchAda.textContent = data.ada_count;
            statSearchTidak.textContent = data.tidak_ada_count;

            currentMissingParts = data.missing_parts || [];
            if (currentMissingParts.length > 0) {
                btnCopyMissing.style.display = 'inline-flex';
            } else {
                btnCopyMissing.style.display = 'none';
            }

            // Render table
            searchTableWrapper.style.display = 'block';
            searchResultsTbody.innerHTML = data.results.map((r, idx) => {
                const statusPill = r.status === 'ADA'
                    ? `<span class="status-pill ada">${ICONS.checkCircle} ADA</span>`
                    : `<span class="status-pill tidak">${ICONS.alertCircle} TIDAK</span>`;

                let details = r.details;
                if (r.similar && r.similar.length > 0) {
                    details += ` <small style="color: var(--accent-amber);">(Mirip: ${r.similar.join(', ')})</small>`;
                }

                return `
                    <tr>
                        <td>${idx + 1}</td>
                        <td><strong style="font-family: var(--font-mono);">${r.part_number}</strong></td>
                        <td>${statusPill}</td>
                        <td><span class="meta-pill">${r.category}</span></td>
                        <td>${r.local_doc || '-'}</td>
                        <td>${details}</td>
                    </tr>
                `;
            }).join('');

            showToast(`Pengecekan selesai: ${data.ada_count} ADA, ${data.tidak_ada_count} TIDAK ADA`, 'info');
            await loadExcelLogs();
        } catch (err) {
            console.error(err);
            showToast('Gagal: ' + err.message, 'error');
        } finally {
            btnExecuteSearch.disabled = false;
            btnExecuteSearch.innerHTML = `${ICONS.zap} <span>Cek ke FactoryHub</span>`;
        }
    });

    btnCopyMissing.addEventListener('click', () => {
        if (currentMissingParts.length === 0) return;
        const text = currentMissingParts.join('\n');
        navigator.clipboard.writeText(text).then(() => {
            showToast(`${currentMissingParts.length} part berhasil disalin ke clipboard!`, 'success');
        }).catch(() => {
            showToast('Gagal menyalin ke clipboard', 'error');
        });
    });

    // =========================================================================
    // DIFF TAB & FULL COMPARISON TABLE (REQUIREMENT 3 PART B)
    // =========================================================================
    function populateDiffPartSelect() {
        const currentVal = diffPartSelect.value;
        const allParts = [];

        (docsData.belum || []).forEach(p => allParts.push({ part: p.part_number, status: 'Belum', file: p.excel_file }));
        (docsData.tidak_ada_part || []).forEach(p => allParts.push({ part: p.part_number, status: 'Belum Ada', file: p.excel_file }));
        (docsData.done || []).forEach(p => allParts.push({ part: p.part_number, status: 'Done', file: p.excel_file }));

        diffPartSelect.innerHTML = '<option value="">-- Pilih Part Number --</option>' + allParts.map(item => `
            <option value="${item.part}">${item.part} (${item.status})</option>
        `).join('');

        if (currentVal) diffPartSelect.value = currentVal;
    }

    function switchToDiffForPart(part) {
        // Activate Diff Tab
        navBtns.forEach(b => b.classList.remove('active'));
        tabPanes.forEach(p => p.classList.remove('active'));

        const diffNavBtn = document.getElementById('nav-btn-diff');
        const diffTabPane = document.getElementById('tab-diff');
        if (diffNavBtn) diffNavBtn.classList.add('active');
        if (diffTabPane) diffTabPane.classList.add('active');

        populateDiffPartSelect();
        diffPartSelect.value = part;
        triggerDiffCompare(part);
    }

    btnRunDiffCompare.addEventListener('click', () => {
        const selected = diffPartSelect.value;
        if (!selected) {
            showToast('Harap pilih part number terlebih dahulu', 'info');
            return;
        }
        triggerDiffCompare(selected);
    });

    async function triggerDiffCompare(part) {
        diffEmptyState.style.display = 'flex';
        diffEmptyState.innerHTML = `<span class="spinner" style="width: 32px; height: 32px;"></span><h3 style="margin-top: 1rem;">Menganalisis Perbandingan Template...</h3><p>Memeriksa FactoryHub dan checksheet lokal untuk ${part}...</p>`;
        diffContent.style.display = 'none';
        btnRunDiffCompare.disabled = true;

        try {
            const res = await fetch('/api/diff/compare', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ part: part })
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Gagal membandingkan template');

            currentDiffData = { part: part, document_file: data.document_file, ...(data.diff || {}) };
            renderDiffTab(currentDiffData);
            showToast(`Perbandingan template untuk ${part} berhasil dimuat!`, 'success');
        } catch (err) {
            console.error(err);
            diffEmptyState.style.display = 'flex';
            diffEmptyState.innerHTML = `${ICONS.alertCircle}<h3>Gagal Membandingkan</h3><p>${err.message}</p>`;
            showToast('Gagal membandingkan: ' + err.message, 'error');
        } finally {
            btnRunDiffCompare.disabled = false;
        }
    }

    // Diff filter chips
    document.querySelectorAll('.diff-filter-group .btn-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.diff-filter-group .btn-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            currentDiffFilter = chip.getAttribute('data-diff-filter');
            if (currentDiffData) renderDiffTableRows(currentDiffData.comparison_rows || []);
        });
    });

    function renderDiffTab(diff) {
        if (!diff) {
            diffEmptyState.style.display = 'flex';
            diffContent.style.display = 'none';
            diffFilterGroup.style.display = 'none';
            return;
        }

        diffEmptyState.style.display = 'none';
        diffContent.style.display = 'block';
        diffFilterGroup.style.display = 'flex';

        const addedCount = diff.added ? diff.added.length : 0;
        const modCount = diff.modified ? diff.modified.length : 0;
        const remCount = diff.removed ? diff.removed.length : 0;
        const unchCount = diff.unchanged_count || (diff.unchanged ? diff.unchanged.length : 0);
        const totalRows = (diff.comparison_rows || []).length;
        const changedCount = addedCount + modCount + remCount;

        // Update Chip counts
        document.getElementById('chip-count-all').textContent = totalRows;
        document.getElementById('chip-count-changed').textContent = changedCount;
        document.getElementById('chip-count-added').textContent = addedCount;
        document.getElementById('chip-count-modified').textContent = modCount;
        document.getElementById('chip-count-removed').textContent = remCount;

        diffContent.innerHTML = `
            <div class="diff-header-bar">
                <div>
                    <span class="diff-title">Perbandingan Template Part: ${diff.part || ''}</span>
                    <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.2rem;">
                        Dokumen: <code>${diff.document_file || '-'}</code> | Total: <strong>${diff.new_count || 0} titik baru</strong> vs <strong>${diff.old_count || 0} titik template lama</strong>
                    </div>
                </div>
                <div>
                    <span class="diff-summary-tag">${diff.summary || ''}</span>
                </div>
            </div>

            <!-- KPI Cards -->
            <div class="diff-kpi-grid">
                <div class="diff-kpi-card added">
                    <span class="diff-kpi-num">+${addedCount}</span>
                    <span class="diff-kpi-lbl">Titik Ditambah</span>
                </div>
                <div class="diff-kpi-card modified">
                    <span class="diff-kpi-num">~${modCount}</span>
                    <span class="diff-kpi-lbl">Titik Diubah</span>
                </div>
                <div class="diff-kpi-card removed">
                    <span class="diff-kpi-num">-${remCount}</span>
                    <span class="diff-kpi-lbl">Titik Dihapus</span>
                </div>
                <div class="diff-kpi-card unchanged">
                    <span class="diff-kpi-num">=${unchCount}</span>
                    <span class="diff-kpi-lbl">Titik Sama</span>
                </div>
            </div>

            <!-- Full Comparison Table -->
            <div class="diff-table-container">
                <table class="diff-table">
                    <thead>
                        <tr>
                            <th style="width: 110px;">Status</th>
                            <th style="width: 70px;">No Item</th>
                            <th>Nama Item Inspeksi</th>
                            <th>Standard Toleransi (Lama ➔ Baru)</th>
                            <th>Metode (Lama ➔ Baru)</th>
                            <th>Detail Perubahan</th>
                        </tr>
                    </thead>
                    <tbody id="diff-table-tbody">
                        <!-- Injected by renderDiffTableRows -->
                    </tbody>
                </table>
            </div>
        `;

        renderDiffTableRows(diff.comparison_rows || []);
    }

    function renderDiffTableRows(rows) {
        const tbody = document.getElementById('diff-table-tbody');
        if (!tbody) return;

        const filtered = rows.filter(r => {
            if (currentDiffFilter === 'all') return true;
            if (currentDiffFilter === 'changed') return r.status !== 'UNCHANGED';
            if (currentDiffFilter === 'added') return r.status === 'ADDED';
            if (currentDiffFilter === 'modified') return r.status === 'MODIFIED';
            if (currentDiffFilter === 'removed') return r.status === 'REMOVED';
            return true;
        });

        if (filtered.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">Tidak ada baris pada filter '${currentDiffFilter}'.</td></tr>`;
            return;
        }

        tbody.innerHTML = filtered.map(r => {
            let badgeClass = 'unchanged';
            let badgeText = '= SAMA';
            let rowClass = '';

            if (r.status === 'ADDED') {
                badgeClass = 'added';
                badgeText = '+ TAMBAH';
                rowClass = 'row-added';
            } else if (r.status === 'MODIFIED') {
                badgeClass = 'modified';
                badgeText = '~ DIUBAH';
                rowClass = 'row-modified';
            } else if (r.status === 'REMOVED') {
                badgeClass = 'removed';
                badgeText = '- HAPUS';
                rowClass = 'row-removed';
            }

            // Standard display
            let stdDisplay = '';
            if (r.status === 'MODIFIED') {
                stdDisplay = `<span class="diff-val-old">${r.old_standard || '-'}</span> <span class="diff-val-new">➔ ${r.new_standard || '-'}</span>`;
            } else if (r.status === 'ADDED') {
                stdDisplay = `<span class="diff-val-new">${r.new_standard || '-'}</span>`;
            } else if (r.status === 'REMOVED') {
                stdDisplay = `<span class="diff-val-old">${r.old_standard || '-'}</span>`;
            } else {
                stdDisplay = `<code>${r.new_standard || '-'}</code>`;
            }

            // Method display
            let methodDisplay = '';
            if (r.status === 'MODIFIED' && r.old_method !== r.new_method) {
                methodDisplay = `<span class="diff-val-old">${r.old_method || '-'}</span> <span class="diff-val-new">➔ ${r.new_method || '-'}</span>`;
            } else {
                methodDisplay = r.new_method || r.old_method || '-';
            }

            // Change details bullets
            let changesHtml = '-';
            if (r.changes && r.changes.length > 0) {
                changesHtml = r.changes.map(c => `<span class="diff-change-bullet">• ${c}</span>`).join('');
            }

            return `
                <tr class="${rowClass}">
                    <td><span class="diff-status-badge ${badgeClass}">${badgeText}</span></td>
                    <td><strong>${r.item_no || '-'}</strong></td>
                    <td>${r.inspection_item || '-'}</td>
                    <td>${stdDisplay}</td>
                    <td>${methodDisplay}</td>
                    <td>${changesHtml}</td>
                </tr>
            `;
        }).join('');
    }

    // =========================================================================
    // IN-WEB EXCEL LOGBOOK VIEWER (REQUIREMENT 3 PART A)
    // =========================================================================
    subtabExecBtn.addEventListener('click', () => {
        subtabExecBtn.classList.add('active');
        subtabSearchBtn.classList.remove('active');
        subtabExec.style.display = 'block';
        subtabSearch.style.display = 'none';
    });

    subtabSearchBtn.addEventListener('click', () => {
        subtabSearchBtn.classList.add('active');
        subtabExecBtn.classList.remove('active');
        subtabSearch.style.display = 'block';
        subtabExec.style.display = 'none';
    });

    btnRefreshLogs.addEventListener('click', async () => {
        await loadExcelLogs();
        showToast('Data riwayat berhasil diperbarui', 'info');
    });

    execSearchInput.addEventListener('input', () => {
        renderExecutionLogs();
    });

    searchLogFilter.addEventListener('input', () => {
        renderSearchLogs();
    });

    async function loadExcelLogs() {
        try {
            const res = await fetch('/api/logs/excel');
            const data = await res.json();
            excelLogsData = data;

            countLogExec.textContent = (data.execution_history || []).length;
            countLogSearch.textContent = (data.search_history || []).length;

            renderExecutionLogs();
            renderSearchLogs();
        } catch (err) {
            console.error('Error loading excel logs:', err);
        }
    }

    function renderExecutionLogs() {
        const query = execSearchInput.value.trim().toLowerCase();
        const logs = excelLogsData.execution_history || [];

        const filtered = logs.filter(l => {
            if (!query) return true;
            return (
                (l['Part Number'] && l['Part Number'].toLowerCase().includes(query)) ||
                (l['Document File'] && l['Document File'].toLowerCase().includes(query)) ||
                (l['Result Action'] && l['Result Action'].toLowerCase().includes(query)) ||
                (l['Diff Summary'] && l['Diff Summary'].toLowerCase().includes(query))
            );
        });

        if (filtered.length === 0) {
            logsTbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 2rem;">Belum ada riwayat eksekusi checksheet.</td></tr>';
            return;
        }

        logsTbody.innerHTML = filtered.map(l => {
            let statusClass = 'baru';
            const action = l['Result Action'] || '';
            if (action === 'UPDATE') statusClass = 'update';
            else if (action.includes('TIDAK') || action.includes('ERROR')) statusClass = 'tidak';

            return `
                <tr>
                    <td style="white-space: nowrap; font-size: 0.8rem; color: var(--text-muted);">${l['Timestamp'] || '-'}</td>
                    <td><strong style="font-family: var(--font-mono);">${l['Part Number'] || '-'}</strong></td>
                    <td style="font-size: 0.82rem;">${l['Document File'] || '-'}</td>
                    <td><span class="badge-tag ${String(l['Type']).toLowerCase()}">${l['Type'] || '-'}</span></td>
                    <td style="font-size: 0.82rem;">${l['Mode Scan'] || '-'}</td>
                    <td><span class="status-pill ${statusClass}">${action}</span></td>
                    <td><strong>${l['Points Count'] || '-'}</strong></td>
                    <td>${l['Images Count'] || '0'}</td>
                    <td style="font-size: 0.82rem; color: var(--text-secondary);">${l['Diff Summary'] || l['Notes'] || '-'}</td>
                </tr>
            `;
        }).join('');
    }

    function renderSearchLogs() {
        const query = searchLogFilter.value.trim().toLowerCase();
        const logs = excelLogsData.search_history || [];

        const filtered = logs.filter(l => {
            if (!query) return true;
            return (
                (l['Part Number'] && l['Part Number'].toLowerCase().includes(query)) ||
                (l['Search Query'] && l['Search Query'].toLowerCase().includes(query)) ||
                (l['FH Status'] && l['FH Status'].toLowerCase().includes(query)) ||
                (l['Notes'] && l['Notes'].toLowerCase().includes(query))
            );
        });

        if (filtered.length === 0) {
            searchLogsTbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">Belum ada riwayat pencarian part number.</td></tr>';
            return;
        }

        searchLogsTbody.innerHTML = filtered.map(l => {
            const statusClass = l['FH Status'] === 'ADA' ? 'ada' : 'tidak';
            return `
                <tr>
                    <td style="white-space: nowrap; font-size: 0.8rem; color: var(--text-muted);">${l['Timestamp'] || '-'}</td>
                    <td style="font-size: 0.82rem; color: var(--text-secondary);">${l['Search Query'] || '-'}</td>
                    <td><strong style="font-family: var(--font-mono);">${l['Part Number'] || '-'}</strong></td>
                    <td><span class="status-pill ${statusClass}">${l['FH Status'] || '-'}</span></td>
                    <td><span class="meta-pill">${l['Category'] || '-'}</span></td>
                    <td>${l['Local Document'] || '-'}</td>
                    <td style="font-size: 0.82rem;">${l['Notes'] || '-'}</td>
                </tr>
            `;
        }).join('');
    }

    // =========================================================================
    // DETAILS MODAL ACTIONS (COPY POINTS, EXPORT JSON/CSV, FINDER)
    // =========================================================================
    if (btnDetailsCopyPts) {
        btnDetailsCopyPts.addEventListener('click', () => {
            if (!currentDetailsDoc || !currentDetailsDoc.data || !currentDetailsDoc.data.inspection_points || currentDetailsDoc.data.inspection_points.length === 0) {
                showToast('Tidak ada titik inspeksi untuk disalin', 'warning');
                return;
            }
            const pts = currentDetailsDoc.data.inspection_points;
            const header = ["No", "Item Inspeksi", "Standar", "Metode", "Master Data"].join("\t");
            const rows = pts.map(p => [p.item_no || '', p.inspection_item || '', p.standard || '', p.method || '', p.master_data || ''].join("\t"));
            const text = [header, ...rows].join("\n");
            navigator.clipboard.writeText(text).then(() => {
                showToast(`[✓] ${pts.length} titik inspeksi disalin ke clipboard! Siap paste ke Excel.`, 'success');
            }).catch(err => {
                console.error('Clipboard copy error:', err);
                showToast('Gagal menyalin ke clipboard', 'error');
            });
        });
    }

    if (btnDetailsExportJson) {
        btnDetailsExportJson.addEventListener('click', () => {
            if (!currentDetailsDoc) return;
            window.open(`/api/documents/${encodeURIComponent(currentDetailsDoc.status)}/${encodeURIComponent(currentDetailsDoc.folder)}/export?format=json`, '_blank');
        });
    }

    if (btnDetailsExportCsv) {
        btnDetailsExportCsv.addEventListener('click', () => {
            if (!currentDetailsDoc) return;
            window.open(`/api/documents/${encodeURIComponent(currentDetailsDoc.status)}/${encodeURIComponent(currentDetailsDoc.folder)}/export?format=csv`, '_blank');
        });
    }

    if (btnDetailsOpenFinder) {
        btnDetailsOpenFinder.addEventListener('click', () => {
            if (!currentDetailsDoc) return;
            openInFinder(currentDetailsDoc.folder, currentDetailsDoc.status);
        });
    }

    // =========================================================================
    // CREATE FOLDER & AUTOCOMPLETE CONTROLLER
    // =========================================================================
    const createFolderAutocomplete = document.getElementById('create-folder-autocomplete');
    const createFolderSpinner = document.getElementById('create-folder-spinner');
    const catalogSnippetPreview = document.getElementById('catalog-snippet-preview');
    const snippetTagCategory = document.getElementById('snippet-tag-category');
    const snippetTagTemplate = document.getElementById('snippet-tag-template');
    const snippetPartNum = document.getElementById('snippet-part-num');
    const snippetPartName = document.getElementById('snippet-part-name');

    let autocompleteTimer = null;
    let autocompleteResults = [];
    let autocompleteSelectedIdx = -1;

    function openCreateFolderModal() {
        if (!modalCreateFolder) return;
        createFolderName.value = '';
        createFolderStatus.value = ['belum', 'tidak_ada_part', 'done'].includes(currentFilter) ? currentFilter : 'belum';
        if (createFolderAutocomplete) {
            createFolderAutocomplete.style.display = 'none';
            createFolderAutocomplete.innerHTML = '';
        }
        if (catalogSnippetPreview) catalogSnippetPreview.style.display = 'none';
        autocompleteSelectedIdx = -1;
        modalCreateFolder.classList.add('active');
        setTimeout(() => createFolderName.focus(), 80);
    }

    function closeCreateFolderModal() {
        if (modalCreateFolder) modalCreateFolder.classList.remove('active');
        if (createFolderAutocomplete) createFolderAutocomplete.style.display = 'none';
    }

    function selectAutocompleteItem(item) {
        if (!item) return;
        createFolderName.value = item.part_number;
        if (createFolderAutocomplete) createFolderAutocomplete.style.display = 'none';

        if (catalogSnippetPreview) {
            catalogSnippetPreview.style.display = 'block';
            if (snippetTagCategory) snippetTagCategory.textContent = `${item.category} PART`;
            if (snippetTagTemplate) {
                snippetTagTemplate.textContent = item.has_template 
                    ? `✓ Template di FactoryHub (${item.template_info?.items_count || 'Ada'})` 
                    : `- Belum Ada Template di FH`;
                snippetTagTemplate.style.color = item.has_template ? 'var(--accent-green)' : 'var(--text-muted)';
            }
            if (snippetPartNum) snippetPartNum.textContent = item.part_number;
            if (snippetPartName) snippetPartName.textContent = item.part_name || '-';
        }
    }

    if (createFolderName) {
        createFolderName.addEventListener('input', () => {
            const query = createFolderName.value.trim();
            if (catalogSnippetPreview) catalogSnippetPreview.style.display = 'none';
            autocompleteSelectedIdx = -1;

            clearTimeout(autocompleteTimer);
            if (!query || query.length < 2) {
                if (createFolderAutocomplete) {
                    createFolderAutocomplete.style.display = 'none';
                    createFolderAutocomplete.innerHTML = '';
                }
                if (createFolderSpinner) createFolderSpinner.style.display = 'none';
                return;
            }

            if (createFolderSpinner) createFolderSpinner.style.display = 'block';

            autocompleteTimer = setTimeout(async () => {
                try {
                    const res = await fetch(`/api/catalog/search?q=${encodeURIComponent(query)}&limit=8`);
                    const data = await res.json();
                    autocompleteResults = (data && data.results) ? data.results : [];

                    if (autocompleteResults.length === 0) {
                        createFolderAutocomplete.style.display = 'none';
                        return;
                    }

                    createFolderAutocomplete.innerHTML = autocompleteResults.map((item, idx) => {
                        const catClass = item.category === 'NEW PROJECT' ? 'project' : 'regular';
                        const tmplBadge = item.has_template 
                            ? `<span class="tmpl-pill">✓ Template FH</span>` 
                            : `<span style="font-size:0.65rem; color:var(--text-muted);">- Belum Ada Template</span>`;
                        const localBadge = item.has_local 
                            ? `<span class="status-pill ${item.local_status}" style="font-size:0.65rem;">Ada (${item.local_status})</span>`
                            : '';

                        return `
                            <div class="autocomplete-item" data-idx="${idx}">
                                <div class="autocomplete-item-left">
                                    <div class="autocomplete-part-num">${item.part_number}</div>
                                    <div class="autocomplete-part-name">${item.part_name || '-'}</div>
                                </div>
                                <div class="autocomplete-item-right">
                                    <span class="cat-pill ${catClass}">${item.category}</span>
                                    ${tmplBadge}
                                    ${localBadge}
                                </div>
                            </div>
                        `;
                    }).join('');

                    createFolderAutocomplete.style.display = 'block';

                    createFolderAutocomplete.querySelectorAll('.autocomplete-item').forEach(el => {
                        el.addEventListener('click', () => {
                            const idx = parseInt(el.getAttribute('data-idx') || '0', 10);
                            selectAutocompleteItem(autocompleteResults[idx]);
                        });
                    });
                } catch (err) {
                    console.error('Autocomplete error:', err);
                } finally {
                    if (createFolderSpinner) createFolderSpinner.style.display = 'none';
                }
            }, 150);
        });

        createFolderName.addEventListener('keydown', (e) => {
            const items = createFolderAutocomplete ? createFolderAutocomplete.querySelectorAll('.autocomplete-item') : [];
            if (e.key === 'ArrowDown') {
                if (createFolderAutocomplete && createFolderAutocomplete.style.display !== 'none' && items.length > 0) {
                    e.preventDefault();
                    autocompleteSelectedIdx = (autocompleteSelectedIdx + 1) % items.length;
                    items.forEach((it, i) => it.classList.toggle('active', i === autocompleteSelectedIdx));
                    items[autocompleteSelectedIdx].scrollIntoView({ block: 'nearest' });
                }
            } else if (e.key === 'ArrowUp') {
                if (createFolderAutocomplete && createFolderAutocomplete.style.display !== 'none' && items.length > 0) {
                    e.preventDefault();
                    autocompleteSelectedIdx = (autocompleteSelectedIdx - 1 + items.length) % items.length;
                    items.forEach((it, i) => it.classList.toggle('active', i === autocompleteSelectedIdx));
                    items[autocompleteSelectedIdx].scrollIntoView({ block: 'nearest' });
                }
            } else if (e.key === 'Enter') {
                if (createFolderAutocomplete && createFolderAutocomplete.style.display !== 'none' && autocompleteSelectedIdx >= 0 && autocompleteResults[autocompleteSelectedIdx]) {
                    e.preventDefault();
                    selectAutocompleteItem(autocompleteResults[autocompleteSelectedIdx]);
                } else {
                    e.preventDefault();
                    if (createFolderSubmit) createFolderSubmit.click();
                }
            } else if (e.key === 'Escape') {
                if (createFolderAutocomplete && createFolderAutocomplete.style.display !== 'none') {
                    e.stopPropagation();
                    createFolderAutocomplete.style.display = 'none';
                }
            }
        });
    }

    // Hide autocomplete on click outside
    document.addEventListener('click', (e) => {
        if (createFolderAutocomplete && !e.target.closest('#modal-create-folder')) {
            createFolderAutocomplete.style.display = 'none';
        }
    });

    if (btnOpenCreateFolder) btnOpenCreateFolder.addEventListener('click', openCreateFolderModal);
    if (modalCreateFolderClose) modalCreateFolderClose.addEventListener('click', closeCreateFolderModal);
    if (createFolderCancel) createFolderCancel.addEventListener('click', closeCreateFolderModal);
    if (modalCreateFolder) {
        modalCreateFolder.addEventListener('click', (e) => {
            if (e.target === modalCreateFolder) closeCreateFolderModal();
        });
    }

    if (createFolderSubmit) {
        createFolderSubmit.addEventListener('click', async () => {
            const name = createFolderName.value.trim();
            const status = createFolderStatus.value;
            if (!name) {
                showToast('Masukkan nama folder atau part number terlebih dahulu', 'warning');
                createFolderName.focus();
                return;
            }

            createFolderSubmit.disabled = true;
            createFolderSubmit.innerHTML = `<span class="spinner"></span> <span>Membuat...</span>`;

            try {
                const res = await fetch('/api/documents/create-folder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder_name: name, status: status })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Gagal membuat folder');

                closeCreateFolderModal();
                const snippetNotice = data.snippet_path ? ' (Snippet info.json dibuat)' : '';
                showToast(`[✓] Folder '${data.folder_name}' berhasil dibuat di kategori '${data.status}'!${snippetNotice}`, 'success');

                currentFilter = data.status;
                updateFilterButtons();
                await loadDocuments();
                loadCatalogStats();
            } catch (err) {
                console.error('Error creating folder:', err);
                showToast('Gagal membuat folder: ' + err.message, 'error');
            } finally {
                createFolderSubmit.disabled = false;
                createFolderSubmit.innerHTML = `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> <span>Buat Folder</span>`;
            }
        });
    }

    // =========================================================================
    // DUPLICATE PART MODAL & LOGIC (SERVER-TO-SERVER & LOCAL)
    // =========================================================================
    let activeDupTab = 'server'; // 'server' or 'local'

    const dupTabServerBtn = document.getElementById('dup-tab-server-btn');
    const dupTabLocalBtn = document.getElementById('dup-tab-local-btn');
    const dupSectionServer = document.getElementById('dup-section-server');
    const dupSectionLocal = document.getElementById('dup-section-local');
    const modalDuplicateSubmitLabel = document.getElementById('modal-duplicate-submit-label');

    const dupSrvSourcePart = document.getElementById('dup-srv-source-part');
    const dupSrvSrcSpinner = document.getElementById('dup-srv-src-spinner');
    const dupSrvSrcAutocomplete = document.getElementById('dup-srv-src-autocomplete');
    const dupSrvTargetPart = document.getElementById('dup-srv-target-part');
    const dupSrvTgtSpinner = document.getElementById('dup-srv-tgt-spinner');
    const dupSrvTgtAutocomplete = document.getElementById('dup-srv-tgt-autocomplete');
    const dupSrvTargetStatus = document.getElementById('dup-srv-target-status');
    const dupSrvSubmit = document.getElementById('dup-srv-submit');
    const dupSrvLogBox = document.getElementById('dup-srv-log-box');

    function switchDupTab(tab) {
        activeDupTab = tab;
        if (tab === 'server') {
            if (dupTabServerBtn) {
                dupTabServerBtn.style.color = 'var(--accent-blue)';
                dupTabServerBtn.style.borderBottom = '2px solid var(--accent-blue)';
            }
            if (dupTabLocalBtn) {
                dupTabLocalBtn.style.color = 'var(--text-muted)';
                dupTabLocalBtn.style.borderBottom = '2px solid transparent';
            }
            if (dupSectionServer) dupSectionServer.style.display = 'block';
            if (dupSectionLocal) dupSectionLocal.style.display = 'none';
            if (modalDuplicateSubmitLabel) modalDuplicateSubmitLabel.textContent = 'Mulai Duplikasi dari Server';
            setTimeout(() => { if (dupSrvSourcePart) dupSrvSourcePart.focus(); }, 80);
        } else {
            if (dupTabLocalBtn) {
                dupTabLocalBtn.style.color = 'var(--accent-blue)';
                dupTabLocalBtn.style.borderBottom = '2px solid var(--accent-blue)';
            }
            if (dupTabServerBtn) {
                dupTabServerBtn.style.color = 'var(--text-muted)';
                dupTabServerBtn.style.borderBottom = '2px solid transparent';
            }
            if (dupSectionServer) dupSectionServer.style.display = 'none';
            if (dupSectionLocal) dupSectionLocal.style.display = 'block';
            if (modalDuplicateSubmitLabel) modalDuplicateSubmitLabel.textContent = 'Duplikasi Folder Lokal';
            setTimeout(() => { if (dupTargetPart) dupTargetPart.focus(); }, 80);
        }
    }

    if (dupTabServerBtn) dupTabServerBtn.addEventListener('click', () => switchDupTab('server'));
    if (dupTabLocalBtn) dupTabLocalBtn.addEventListener('click', () => switchDupTab('local'));

    function openDuplicateModal(sourceData = null) {
        if (!modalDuplicate) return;

        let srcPart = '';
        let srcStatus = 'belum';
        let srcDoc = '';
        let srcImages = '0';
        let srcName = '';

        if (sourceData) {
            srcPart = sourceData.part || sourceData.folder || '';
            srcStatus = sourceData.status || 'belum';
            srcDoc = sourceData.doc || '';
            srcImages = sourceData.images || '0';
        } else {
            const list = (docsData && (docsData[currentFilter] || docsData.belum || docsData.done)) || [];
            if (list && list.length > 0) {
                const first = list[0];
                srcPart = first.part_number || '';
                srcStatus = first.status || 'belum';
                srcDoc = first.excel_file || '';
                srcImages = first.image_count || '0';
                srcName = first.part_name || '';
            }
        }

        // Server tab inputs
        if (dupSrvSourcePart) dupSrvSourcePart.value = srcPart;
        if (dupSrvTargetPart) dupSrvTargetPart.value = '';
        if (dupSrvTargetStatus) dupSrvTargetStatus.value = 'belum';
        if (dupSrvSubmit) dupSrvSubmit.checked = false;
        if (dupSrvLogBox) {
            dupSrvLogBox.style.display = 'none';
            dupSrvLogBox.textContent = '';
        }
        if (dupSrvSrcAutocomplete) dupSrvSrcAutocomplete.style.display = 'none';
        if (dupSrvTgtAutocomplete) dupSrvTgtAutocomplete.style.display = 'none';

        // Local tab inputs
        if (dupSourcePart) dupSourcePart.value = srcPart;
        if (dupSourceStatus) dupSourceStatus.value = srcStatus;
        if (dupSourcePartDisplay) dupSourcePartDisplay.textContent = srcPart || '(Pilih Part)';
        if (dupSourceStatusBadge) {
            dupSourceStatusBadge.textContent = srcStatus.toUpperCase().replace(/_/g, ' ');
            dupSourceStatusBadge.className = `badge badge-${srcStatus}`;
        }
        if (dupSourceMetaDisplay) {
            const docInfo = srcDoc ? `Dokumen: ${srcDoc}` : 'Tanpa dokumen';
            const imgInfo = `${srcImages} gambar`;
            const nameInfo = srcName ? ` • ${srcName}` : '';
            dupSourceMetaDisplay.textContent = `${docInfo} • ${imgInfo}${nameInfo}`;
        }
        if (dupTargetPart) dupTargetPart.value = '';
        if (dupTargetStatus) dupTargetStatus.value = 'belum';
        if (dupRenameFiles) dupRenameFiles.checked = true;
        if (dupTargetAutocomplete) dupTargetAutocomplete.style.display = 'none';

        switchDupTab('server');
        modalDuplicate.classList.add('active');
        setTimeout(() => {
            if (dupSrvSourcePart && !srcPart) dupSrvSourcePart.focus();
            else if (dupSrvTargetPart) dupSrvTargetPart.focus();
        }, 120);
    }

    function closeDuplicateModal() {
        if (modalDuplicate) modalDuplicate.classList.remove('active');
        if (dupSrvSrcAutocomplete) dupSrvSrcAutocomplete.style.display = 'none';
        if (dupSrvTgtAutocomplete) dupSrvTgtAutocomplete.style.display = 'none';
        if (dupTargetAutocomplete) dupTargetAutocomplete.style.display = 'none';
    }

    // Autocomplete helper for input
    function setupCatalogAutocomplete(inputEl, spinnerEl, dropdownEl, onSelect) {
        if (!inputEl || !dropdownEl) return;

        inputEl.addEventListener('input', () => {
            const query = inputEl.value.trim().toUpperCase();
            inputEl.value = query;
            clearTimeout(inputEl._timer);

            if (!query || query.length < 2) {
                dropdownEl.style.display = 'none';
                dropdownEl.innerHTML = '';
                if (spinnerEl) spinnerEl.style.display = 'none';
                return;
            }

            if (spinnerEl) spinnerEl.style.display = 'block';

            inputEl._timer = setTimeout(async () => {
                try {
                    const res = await fetch(`/api/catalog/search?q=${encodeURIComponent(query)}&limit=8`);
                    const data = await res.json();
                    const results = (data && data.results) ? data.results : [];

                    if (results.length === 0) {
                        dropdownEl.style.display = 'none';
                        return;
                    }

                    dropdownEl.innerHTML = results.map((item, idx) => {
                        const catClass = item.category === 'NEW PROJECT' ? 'project' : 'regular';
                        const tmplBadge = item.has_template 
                            ? `<span class="tmpl-pill">✓ Template FH</span>` 
                            : `<span style="font-size:0.65rem; color:var(--text-muted);">- Belum Ada Template</span>`;
                        const localBadge = item.has_local 
                            ? `<span class="status-pill ${item.local_status}" style="font-size:0.65rem;">Ada (${item.local_status})</span>`
                            : '';

                        return `
                            <div class="autocomplete-item" data-idx="${idx}">
                                <div class="autocomplete-item-left">
                                    <div class="autocomplete-part-num">${item.part_number}</div>
                                    <div class="autocomplete-part-name">${item.part_name || '-'}</div>
                                </div>
                                <div class="autocomplete-item-right">
                                    <span class="cat-pill ${catClass}">${item.category}</span>
                                    ${tmplBadge}
                                    ${localBadge}
                                </div>
                            </div>
                        `;
                    }).join('');

                    dropdownEl.style.display = 'block';

                    dropdownEl.querySelectorAll('.autocomplete-item').forEach(el => {
                        el.addEventListener('click', () => {
                            const idx = parseInt(el.getAttribute('data-idx') || '0', 10);
                            inputEl.value = results[idx].part_number;
                            dropdownEl.style.display = 'none';
                            if (onSelect) onSelect(results[idx]);
                        });
                    });
                } catch (err) {
                    console.error('Autocomplete error:', err);
                } finally {
                    if (spinnerEl) spinnerEl.style.display = 'none';
                }
            }, 150);
        });
    }

    setupCatalogAutocomplete(dupSrvSourcePart, dupSrvSrcSpinner, dupSrvSrcAutocomplete, (item) => {
        if (dupSrvTargetPart) dupSrvTargetPart.focus();
    });

    setupCatalogAutocomplete(dupSrvTargetPart, dupSrvTgtSpinner, dupSrvTgtAutocomplete, (item) => {});

    setupCatalogAutocomplete(dupTargetPart, dupTargetSpinner, dupTargetAutocomplete, (item) => {});

    document.addEventListener('click', (e) => {
        if (dupSrvSrcAutocomplete && !e.target.closest('#dup-srv-source-part')) {
            dupSrvSrcAutocomplete.style.display = 'none';
        }
        if (dupSrvTgtAutocomplete && !e.target.closest('#dup-srv-target-part')) {
            dupSrvTgtAutocomplete.style.display = 'none';
        }
        if (dupTargetAutocomplete && !e.target.closest('#dup-target-part')) {
            dupTargetAutocomplete.style.display = 'none';
        }
    });

    if (btnOpenDuplicate) btnOpenDuplicate.addEventListener('click', () => openDuplicateModal());
    if (btnDetailsDuplicate) {
        btnDetailsDuplicate.addEventListener('click', () => {
            if (!currentDetailsDoc) return;
            const d = currentDetailsDoc.data;
            openDuplicateModal({
                part: currentDetailsDoc.part_number,
                status: currentDetailsDoc.status,
                folder: currentDetailsDoc.folder,
                name: d?.metadata?.part_name || '',
                doc: d?.document_file || '',
                images: d?.images_count || '0'
            });
        });
    }
    if (modalDuplicateClose) modalDuplicateClose.addEventListener('click', closeDuplicateModal);
    if (modalDuplicateCancel) modalDuplicateCancel.addEventListener('click', closeDuplicateModal);
    if (modalDuplicate) {
        modalDuplicate.addEventListener('click', (e) => {
            if (e.target === modalDuplicate) closeDuplicateModal();
        });
    }

    if (modalDuplicateSubmit) {
        modalDuplicateSubmit.addEventListener('click', async () => {
            if (activeDupTab === 'server') {
                // SERVER-TO-SERVER DUPLICATION
                const srcPart = dupSrvSourcePart ? dupSrvSourcePart.value.trim().toUpperCase() : '';
                const tgtPart = dupSrvTargetPart ? dupSrvTargetPart.value.trim().toUpperCase() : '';
                const tgtStatus = dupSrvTargetStatus ? dupSrvTargetStatus.value : 'belum';
                const submit = dupSrvSubmit ? dupSrvSubmit.checked : false;

                if (!srcPart) {
                    showToast('Masukkan nomor part asal di FactoryHub terlebih dahulu', 'warning');
                    if (dupSrvSourcePart) dupSrvSourcePart.focus();
                    return;
                }
                if (!tgtPart) {
                    showToast('Masukkan nomor part target terlebih dahulu', 'warning');
                    if (dupSrvTargetPart) dupSrvTargetPart.focus();
                    return;
                }
                if (srcPart === tgtPart) {
                    showToast('Nomor part tujuan tidak boleh sama dengan part asal', 'warning');
                    if (dupSrvTargetPart) dupSrvTargetPart.focus();
                    return;
                }

                modalDuplicateSubmit.disabled = true;
                modalDuplicateSubmit.innerHTML = `<span class="spinner"></span> <span>Sedang Menduplikasi dari Server...</span>`;

                if (dupSrvLogBox) {
                    dupSrvLogBox.style.display = 'block';
                    dupSrvLogBox.textContent = `[*] Menghubungi FactoryHub...\n[*] Mengambil template part asal: ${srcPart}...\n[*] Mengunduh gambar referensi & membuat backup Excel lokal...\n[*] Menyiapkan form checksheet untuk part target: ${tgtPart}...\n[*] Jendela browser akan terbuka di layar Anda untuk ditinjau.\n`;
                }

                try {
                    const res = await fetch('/api/server-duplicate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            source_part: srcPart,
                            target_part: tgtPart,
                            target_status: tgtStatus,
                            submit: submit,
                            headless: false
                        })
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || 'Gagal menduplikasi dari server');

                    if (dupSrvLogBox) {
                        dupSrvLogBox.textContent += `\n[✓] Sukses! ${data.points_count} titik inspeksi & ${data.images_count} gambar berhasil disalin.\n[✓] Backup Excel: ${data.excel_path}\n`;
                    }

                    showToast(`[✓] Sukses! Part '${tgtPart}' berhasil diduplikasi dari '${srcPart}'!`, 'success');

                    setTimeout(async () => {
                        closeDuplicateModal();
                        currentFilter = tgtStatus;
                        updateFilterButtons();
                        await loadDocuments();
                        loadCatalogStats();
                        loadCatalogTable();

                        setTimeout(() => {
                            const newCard = document.querySelector(`.doc-card[data-part="${tgtPart}"]`);
                            if (newCard) {
                                newCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                newCard.style.boxShadow = '0 0 0 3px var(--accent-blue), 0 8px 24px rgba(59, 130, 246, 0.4)';
                                setTimeout(() => { newCard.style.boxShadow = ''; }, 3500);
                            }
                        }, 400);
                    }, 1200);

                } catch (err) {
                    console.error('Server duplication error:', err);
                    if (dupSrvLogBox) {
                        dupSrvLogBox.textContent += `\n[!] GAGAL: ${err.message}\n`;
                    }
                    showToast('Gagal: ' + err.message, 'error');
                } finally {
                    modalDuplicateSubmit.disabled = false;
                    modalDuplicateSubmit.innerHTML = `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg> <span>Mulai Duplikasi dari Server</span>`;
                }

            } else {
                // LOCAL-TO-LOCAL DUPLICATION
                const srcPart = dupSourcePart ? dupSourcePart.value.trim() : '';
                const tgtPart = dupTargetPart ? dupTargetPart.value.trim().toUpperCase() : '';
                const tgtStatus = dupTargetStatus ? dupTargetStatus.value : 'belum';
                const rename = dupRenameFiles ? dupRenameFiles.checked : true;

                if (!srcPart) {
                    showToast('Part sumber tidak valid', 'warning');
                    return;
                }
                if (!tgtPart) {
                    showToast('Masukkan nomor part target terlebih dahulu', 'warning');
                    if (dupTargetPart) dupTargetPart.focus();
                    return;
                }
                if (srcPart.toUpperCase() === tgtPart) {
                    showToast('Nomor part baru tidak boleh sama dengan part asal', 'warning');
                    if (dupTargetPart) dupTargetPart.focus();
                    return;
                }

                modalDuplicateSubmit.disabled = true;
                modalDuplicateSubmit.innerHTML = `<span class="spinner"></span> <span>Menduplikasi Folder Lokal...</span>`;

                try {
                    const res = await fetch('/api/part/duplicate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            source_part: srcPart,
                            target_part: tgtPart,
                            target_status: tgtStatus,
                            rename_files: rename
                        })
                    });
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || 'Gagal menduplikasi part');

                    closeDuplicateModal();
                    showToast(`[✓] ${data.message || `Part '${tgtPart}' berhasil diduplikasi!`}`, 'success');

                    currentFilter = tgtStatus;
                    updateFilterButtons();
                    await loadDocuments();
                    loadCatalogStats();
                    loadCatalogTable();

                    setTimeout(() => {
                        const newCard = document.querySelector(`.doc-card[data-part="${tgtPart}"]`);
                        if (newCard) {
                            newCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            newCard.style.boxShadow = '0 0 0 3px var(--accent-blue), 0 8px 24px rgba(59, 130, 246, 0.4)';
                            setTimeout(() => { newCard.style.boxShadow = ''; }, 3500);
                        }
                    }, 400);

                } catch (err) {
                    console.error('Error duplicating part:', err);
                    showToast('Gagal: ' + err.message, 'error');
                } finally {
                    modalDuplicateSubmit.disabled = false;
                    modalDuplicateSubmit.innerHTML = `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg> <span>Duplikasi Folder Lokal</span>`;
                }
            }
        });
    }

    async function createFolderFromCatalogDirect(partNumber, targetStatus = 'belum') {
        try {
            showToast(`Membuat folder & snippet untuk '${partNumber}'...`, 'info');
            const res = await fetch('/api/catalog/create-folder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ part_number: partNumber, status: targetStatus })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Gagal membuat folder dari katalog');

            showToast(`[✓] Folder '${data.folder_name}' & snippet info.json berhasil dibuat di documents/${data.status}!`, 'success');
            await loadDocuments();
            loadCatalogStats();
            loadCatalogTable();
        } catch (err) {
            console.error('Error direct catalog folder creation:', err);
            showToast('Gagal membuat folder: ' + err.message, 'error');
        }
    }

    // =========================================================================
    // UPLOAD MODAL & GLOBAL DRAG AND DROP
    // =========================================================================
    let uploadQueueFiles = [];

    function openUploadModal() {
        if (!modalUpload) return;
        uploadStatus.value = ['belum', 'tidak_ada_part', 'done'].includes(currentFilter) ? currentFilter : 'belum';
        modalUpload.classList.add('active');
        renderUploadQueue();
    }

    function closeUploadModal() {
        if (modalUpload) modalUpload.classList.remove('active');
        if (uploadProgressWrap) uploadProgressWrap.style.display = 'none';
        if (uploadProgressBar) uploadProgressBar.style.width = '0%';
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    function renderUploadQueue() {
        if (!uploadFileItemsList || !uploadFilesPreview || !uploadFileCount) return;

        if (uploadQueueFiles.length === 0) {
            uploadFilesPreview.style.display = 'none';
            uploadFileCount.textContent = '0';
            if (modalUploadSubmit) modalUploadSubmit.disabled = true;
            return;
        }

        uploadFilesPreview.style.display = 'block';
        uploadFileCount.textContent = uploadQueueFiles.length;
        if (modalUploadSubmit) modalUploadSubmit.disabled = false;

        // Auto pre-fill custom folder name placeholder if empty
        if (uploadCustomFolder && !uploadCustomFolder.value.trim()) {
            for (const f of uploadQueueFiles) {
                const clean = f.name.replace(/\.[^/.]+$/, '').trim();
                if (/[0-9]{3,}[A-Za-z0-9\-_]{2,}/.test(clean)) {
                    uploadCustomFolder.placeholder = `Otomatis: ${clean}`;
                    break;
                }
            }
        }

        uploadFileItemsList.innerHTML = uploadQueueFiles.map((file, idx) => {
            const ext = file.name.split('.').pop().toLowerCase();
            let typeBadge = 'DOC';
            if (['xlsx', 'xls'].includes(ext)) typeBadge = 'EXCEL';
            else if (ext === 'pdf') typeBadge = 'PDF';
            else if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) typeBadge = 'IMG';

            return `
                <div class="upload-file-item">
                    <div style="display: flex; align-items: center; gap: 0.5rem; overflow: hidden;">
                        <span class="file-type-badge ${ext}">${typeBadge}</span>
                        <span class="upload-file-item-name" title="${file.name}">${file.name}</span>
                        <span class="upload-file-item-size">(${formatBytes(file.size)})</span>
                    </div>
                    <button type="button" class="btn-text btn-remove-file" data-idx="${idx}" style="color: var(--accent-red); font-size: 0.8rem;">Hapus</button>
                </div>
            `;
        }).join('');

        uploadFileItemsList.querySelectorAll('.btn-remove-file').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt(btn.getAttribute('data-idx') || '0', 10);
                uploadQueueFiles.splice(idx, 1);
                renderUploadQueue();
            });
        });
    }

    function addFilesToUploadQueue(files) {
        if (!files || files.length === 0) return;
        const existingNames = new Set(uploadQueueFiles.map(f => f.name));
        for (const file of files) {
            if (!existingNames.has(file.name)) {
                uploadQueueFiles.push(file);
                existingNames.add(file.name);
            }
        }
        openUploadModal();
    }

    if (btnOpenUpload) btnOpenUpload.addEventListener('click', openUploadModal);
    if (modalUploadClose) modalUploadClose.addEventListener('click', closeUploadModal);
    if (modalUploadCancel) modalUploadCancel.addEventListener('click', closeUploadModal);
    if (modalUpload) {
        modalUpload.addEventListener('click', (e) => {
            if (e.target === modalUpload) closeUploadModal();
        });
    }

    if (btnClearUploadFiles) {
        btnClearUploadFiles.addEventListener('click', () => {
            uploadQueueFiles = [];
            renderUploadQueue();
        });
    }

    if (btnBrowseFiles) {
        btnBrowseFiles.addEventListener('click', (e) => {
            e.stopPropagation();
            if (uploadFileInput) uploadFileInput.click();
        });
    }

    if (uploadDropzone) {
        uploadDropzone.addEventListener('click', () => {
            if (uploadFileInput) uploadFileInput.click();
        });
        uploadDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadDropzone.classList.add('dragover');
        });
        uploadDropzone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            uploadDropzone.classList.remove('dragover');
        });
        uploadDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadDropzone.classList.remove('dragover');
            if (e.dataTransfer && e.dataTransfer.files) {
                addFilesToUploadQueue(Array.from(e.dataTransfer.files));
            }
        });
    }

    if (uploadFileInput) {
        uploadFileInput.addEventListener('change', () => {
            if (uploadFileInput.files) {
                addFilesToUploadQueue(Array.from(uploadFileInput.files));
                uploadFileInput.value = '';
            }
        });
    }

    // Global Window Drag & Drop Overlay
    let globalDragCounter = 0;
    window.addEventListener('dragenter', (e) => {
        if (e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files')) {
            e.preventDefault();
            globalDragCounter++;
            if (dragDropOverlay) dragDropOverlay.classList.add('active');
        }
    });

    window.addEventListener('dragleave', (e) => {
        e.preventDefault();
        globalDragCounter--;
        if (globalDragCounter <= 0) {
            globalDragCounter = 0;
            if (dragDropOverlay) dragDropOverlay.classList.remove('active');
        }
    });

    window.addEventListener('dragover', (e) => {
        if (e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files')) {
            e.preventDefault();
        }
    });

    window.addEventListener('drop', (e) => {
        globalDragCounter = 0;
        if (dragDropOverlay) dragDropOverlay.classList.remove('active');
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            e.preventDefault();
            addFilesToUploadQueue(Array.from(e.dataTransfer.files));
        }
    });

    // Upload Submit Handler
    if (modalUploadSubmit) {
        modalUploadSubmit.addEventListener('click', async () => {
            if (uploadQueueFiles.length === 0) {
                showToast('Pilih setidaknya 1 file untuk diunggah', 'warning');
                return;
            }

            modalUploadSubmit.disabled = true;
            modalUploadSubmit.innerHTML = `<span class="spinner"></span> <span>Mengunggah...</span>`;
            if (uploadProgressWrap) uploadProgressWrap.style.display = 'block';
            if (uploadProgressBar) uploadProgressBar.style.width = '35%';
            if (uploadProgressText) uploadProgressText.textContent = `Mengirim ${uploadQueueFiles.length} file ke server...`;

            try {
                const formData = new FormData();
                for (const file of uploadQueueFiles) {
                    formData.append('files', file);
                }
                formData.append('status', uploadStatus ? uploadStatus.value : 'belum');
                if (uploadCustomFolder && uploadCustomFolder.value.trim()) {
                    formData.append('folder_name', uploadCustomFolder.value.trim());
                }

                if (uploadProgressBar) uploadProgressBar.style.width = '70%';
                if (uploadProgressText) uploadProgressText.textContent = 'Membaca cover sheet dokumen & mengekstrak data...';

                const res = await fetch('/api/documents/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Gagal mengunggah file');

                if (uploadProgressBar) uploadProgressBar.style.width = '100%';
                if (uploadProgressText) uploadProgressText.textContent = 'Selesai!';

                setTimeout(async () => {
                    closeUploadModal();
                    uploadQueueFiles = [];
                    renderUploadQueue();

                    const destStatus = data.status || 'belum';
                    showToast(`[✓] Berhasil mengunggah ${data.files_saved} file untuk part '${data.part_number}'!`, 'success');

                    currentFilter = destStatus;
                    updateFilterUI();
                    await loadDocuments();
                }, 400);

            } catch (err) {
                console.error('Upload error:', err);
                if (uploadProgressWrap) uploadProgressWrap.style.display = 'none';
                showToast('Gagal upload: ' + err.message, 'error');
            } finally {
                modalUploadSubmit.disabled = false;
                modalUploadSubmit.innerHTML = `<svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> <span>Mulai Upload</span>`;
            }
        });
    }

    // =========================================================================
    // COMMAND PALETTE (CMD+K) CONTROLLER
    // =========================================================================
    let paletteSelectedIndex = 0;
    let paletteFilteredItems = [];

    function getAllPaletteItems() {
        const systemActions = [
            {
                type: 'action',
                title: 'Buat Folder Part Baru',
                subtitle: 'Buat folder kategori di documents/ tanpa buka Finder',
                icon: ICONS.folder,
                action: () => openCreateFolderModal()
            },
            {
                type: 'action',
                title: 'Upload Dokumen / File',
                subtitle: 'Unggah file .xlsx, .pdf, atau gambar ke checksheet',
                icon: ICONS.download,
                action: () => openUploadModal()
            },
            {
                type: 'action',
                title: 'WebP Image Optimizer',
                subtitle: 'Kompresi dan konversi semua gambar agar ringan & cepat',
                icon: ICONS.zap,
                action: () => openCompressModal()
            },
            {
                type: 'action',
                title: 'Refresh Semua Data',
                subtitle: 'Perbarui status dokumen, metrik, dan riwayat',
                icon: ICONS.refresh,
                action: () => {
                    btnRefreshAll.click();
                    showToast('Semua data diperbarui', 'info');
                }
            },
            {
                type: 'action',
                title: 'Buka Tab Diff Comparison',
                subtitle: 'Bandingkan template FactoryHub vs checksheet lokal',
                icon: ICONS.diff,
                action: () => {
                    const diffNav = document.querySelector('[data-tab="diff"]');
                    if (diffNav) diffNav.click();
                }
            },
            {
                type: 'action',
                title: 'Buka Tab Riwayat Eksekusi & Log',
                subtitle: 'Lihat riwayat pengisian dan pencarian part',
                icon: ICONS.history,
                action: () => {
                    const logsNav = document.querySelector('[data-tab="logs"]');
                    if (logsNav) logsNav.click();
                }
            }
        ];

        const docItems = [];
        ['belum', 'tidak_ada_part', 'done'].forEach(status => {
            const list = docsData[status] || [];
            list.forEach(item => {
                docItems.push({
                    type: 'document',
                    title: item.part_number,
                    subtitle: `${item.part_name || '-'} • Status: ${status} • Doc: ${item.doc_number || '-'}`,
                    status: status,
                    folder: item.folder_name,
                    icon: ICONS.box,
                    action: () => {
                        currentFilter = status;
                        updateFilterUI();
                        openDetailsModal(status, item.folder_name);
                    }
                });
            });
        });

        return [...systemActions, ...docItems];
    }

    let paletteCatalogTimer = null;

    function renderPaletteResults() {
        if (!paletteResults) return;
        if (paletteFilteredItems.length === 0) {
            paletteResults.innerHTML = `
                <div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.88rem;">
                    Tidak ditemukan hasil untuk "<strong>${paletteInput ? paletteInput.value : ''}</strong>"
                </div>
            `;
            return;
        }

        if (paletteSelectedIndex >= paletteFilteredItems.length) {
            paletteSelectedIndex = 0;
        }

        paletteResults.innerHTML = paletteFilteredItems.map((item, idx) => {
            const isSelected = idx === paletteSelectedIndex;
            const badgeHtml = item.type === 'action' 
                ? `<span class="meta-pill" style="font-size: 0.72rem;">AKSI</span>`
                : item.type === 'catalog'
                ? `<span class="cat-pill ${item.status === 'FH Master' ? 'regular' : item.status}" style="font-size: 0.72rem;">${item.status}</span>`
                : `<span class="status-pill ${item.status}" style="font-size: 0.72rem;">${item.status}</span>`;

            const iconColor = item.type === 'action' 
                ? 'var(--accent-blue)' 
                : item.type === 'catalog' 
                ? 'var(--accent-cyan)' 
                : 'var(--accent-green)';

            return `
                <div class="palette-item ${isSelected ? 'active' : ''}" data-idx="${idx}">
                    <div class="palette-item-left">
                        <div class="palette-item-icon" style="color: ${iconColor};">
                            ${item.icon}
                        </div>
                        <div style="overflow: hidden;">
                            <div style="font-size: 0.88rem; font-weight: 600; color: var(--text-primary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
                                ${item.title}
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
                                ${item.subtitle}
                            </div>
                        </div>
                    </div>
                    <div>${badgeHtml}</div>
                </div>
            `;
        }).join('');

        paletteResults.querySelectorAll('.palette-item').forEach(el => {
            el.addEventListener('click', () => {
                const idx = parseInt(el.getAttribute('data-idx') || '0', 10);
                executePaletteItem(idx);
            });
            el.addEventListener('mouseenter', () => {
                paletteSelectedIndex = parseInt(el.getAttribute('data-idx') || '0', 10);
                paletteResults.querySelectorAll('.palette-item').forEach((itemEl, i) => {
                    itemEl.classList.toggle('active', i === paletteSelectedIndex);
                });
            });
        });

        const activeEl = paletteResults.children[paletteSelectedIndex];
        if (activeEl) {
            activeEl.scrollIntoView({ block: 'nearest' });
        }
    }

    function executePaletteItem(index) {
        const item = paletteFilteredItems[index];
        if (!item) return;
        closeCommandPalette();
        item.action();
    }

    function filterPalette() {
        const query = paletteInput ? paletteInput.value.trim().toLowerCase() : '';
        const allItems = getAllPaletteItems();
        if (!query) {
            paletteFilteredItems = allItems.slice(0, 30);
            paletteSelectedIndex = 0;
            renderPaletteResults();
            return;
        }

        const queryNorm = normalizeSearchToken(query);
        const queryTokens = query.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean).map(t => normalizeSearchToken(t));

        let localMatches = allItems.filter(item => {
            const tLower = item.title.toLowerCase();
            const sLower = item.subtitle.toLowerCase();
            if (tLower.includes(query) || sLower.includes(query)) return true;

            const targetNorm = normalizeSearchToken(`${item.title} ${item.subtitle}`);
            if (queryNorm && targetNorm.includes(queryNorm)) return true;
            if (queryTokens.length > 0 && queryTokens.every(tok => targetNorm.includes(tok))) return true;
            return false;
        });

        paletteFilteredItems = localMatches.slice(0, 30);
        paletteSelectedIndex = 0;
        renderPaletteResults();

        // Search catalog asynchronously if query length >= 2
        if (query.length >= 2) {
            clearTimeout(paletteCatalogTimer);
            paletteCatalogTimer = setTimeout(async () => {
                try {
                    const res = await fetch(`/api/catalog/search?q=${encodeURIComponent(query)}&limit=6`);
                    const data = await res.json();
                    if (data && data.results && data.results.length > 0) {
                        const catalogItems = data.results.map(cat => ({
                            type: 'catalog',
                            title: cat.part_number,
                            subtitle: `${cat.part_name || 'Part FactoryHub'} • ${cat.category} ${cat.has_template ? '• Ada Template' : ''}`,
                            status: cat.local_status !== 'belum_ada' ? cat.local_status : 'FH Master',
                            icon: ICONS.catalog || ICONS.box,
                            action: () => {
                                if (cat.local_status !== 'belum_ada' && cat.local_doc) {
                                    openDetailsModal(cat.local_status, cat.local_doc.folder || cat.part_number);
                                } else {
                                    createFolderFromCatalogDirect(cat.part_number);
                                }
                            }
                        }));

                        const existingTitles = new Set(localMatches.map(m => m.title));
                        const uniqueCatalog = catalogItems.filter(ci => !existingTitles.has(ci.title));
                        paletteFilteredItems = [...localMatches, ...uniqueCatalog].slice(0, 30);
                        renderPaletteResults();
                    }
                } catch (e) {
                    console.error('Palette catalog fetch error:', e);
                }
            }, 120);
        }
    }

    function openCommandPalette() {
        if (!modalPalette) return;
        modalPalette.classList.add('active');
        if (paletteInput) {
            paletteInput.value = '';
            setTimeout(() => paletteInput.focus(), 80);
        }
        filterPalette();
    }

    function closeCommandPalette() {
        if (modalPalette) modalPalette.classList.remove('active');
    }

    function toggleCommandPalette() {
        if (!modalPalette) return;
        if (modalPalette.classList.contains('active')) {
            closeCommandPalette();
        } else {
            openCommandPalette();
        }
    }

    if (btnOpenPalette) btnOpenPalette.addEventListener('click', openCommandPalette);

    if (modalPalette) {
        modalPalette.addEventListener('click', (e) => {
            if (e.target === modalPalette) closeCommandPalette();
        });
    }

    if (paletteInput) {
        paletteInput.addEventListener('input', () => filterPalette());
        paletteInput.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (paletteFilteredItems.length > 0) {
                    paletteSelectedIndex = (paletteSelectedIndex + 1) % paletteFilteredItems.length;
                    renderPaletteResults();
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (paletteFilteredItems.length > 0) {
                    paletteSelectedIndex = (paletteSelectedIndex - 1 + paletteFilteredItems.length) % paletteFilteredItems.length;
                    renderPaletteResults();
                }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                executePaletteItem(paletteSelectedIndex);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                closeCommandPalette();
            }
        });
    }

    // Global Keybindings (Cmd+K / Ctrl+K & Escape)
    window.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            toggleCommandPalette();
        } else if (e.key === 'Escape') {
            closeCommandPalette();
            closeCreateFolderModal();
            closeUploadModal();
            document.getElementById('modal-server-check-result')?.classList.remove('active');
        }
    });

    // =========================================================================
    // TOAST NOTIFICATIONS HELPER
    // =========================================================================
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const iconSvg = type === 'success' ? ICONS.checkCircle : type === 'error' ? ICONS.alertCircle : ICONS.info;
        toast.innerHTML = `${iconSvg} <span>${message}</span>`;

        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(12px)';
            toast.style.transition = 'all 0.25s ease';
            setTimeout(() => toast.remove(), 250);
        }, 3500);
    }

    // =========================================================================
    // LIGHTBOX FULLSCREEN VIEWER CONTROLLER (REQUIREMENT 10)
    // =========================================================================
    function openLightbox(images, startIndex = 0, title = 'Pratinjau Gambar Sketsa') {
        if (!images || images.length === 0) return;

        lightboxImages = images.map((item, idx) => {
            if (typeof item === 'string') {
                const fn = item.split('/').pop() || `sketsa_${idx+1}.png`;
                const isFolder = !item.includes('extracted') && !item.includes('sketch_');
                return {
                    url: item,
                    filename: fn,
                    dimensions: '-',
                    size_kb: '-',
                    source: isFolder ? 'folder' : 'extracted',
                    source_label: isFolder ? 'Folder Screenshot' : 'Ekstrak Dokumen'
                };
            }
            return {
                url: item.url,
                filename: item.filename || `sketsa_${idx+1}.png`,
                dimensions: item.dimensions || (item.width ? `${item.width} × ${item.height} px` : '-'),
                size_kb: item.size_kb ? `${item.size_kb} KB` : '-',
                source: item.source || 'folder',
                source_label: item.source_label || (item.source === 'folder' ? 'Folder Screenshot' : 'Ekstrak Dokumen')
            };
        });

        currentLightboxIdx = Math.max(0, Math.min(startIndex, lightboxImages.length - 1));
        lightboxTitle.textContent = title;
        modalLightbox.style.display = 'flex';
        modalLightbox.classList.add('active');
        showLightboxImage(currentLightboxIdx);
    }

    function showLightboxImage(index) {
        if (!lightboxImages || lightboxImages.length === 0) return;
        if (index < 0) index = lightboxImages.length - 1;
        if (index >= lightboxImages.length) index = 0;
        currentLightboxIdx = index;

        const cur = lightboxImages[currentLightboxIdx];
        lightboxImg.src = cur.url;
        lightboxImg.alt = cur.filename;

        // Badge source
        const isFolder = cur.source === 'folder';
        lightboxBadge.className = `preview-source-badge ${isFolder ? 'folder' : 'extracted'}`;
        lightboxBadge.textContent = `${isFolder ? '📁' : '⚙️'} ${cur.source_label}`;

        // Counter & Subinfo
        lightboxCounter.textContent = `${currentLightboxIdx + 1} / ${lightboxImages.length} • ${cur.filename}`;
        lightboxSubinfo.textContent = `Dimensi: ${cur.dimensions} | Ukuran: ${cur.size_kb}`;

        // Reset Zoom & Pan
        resetLightboxZoom();

        // Prev / Next button visibility
        if (lightboxImages.length <= 1) {
            lightboxPrev.style.display = 'none';
            lightboxNext.style.display = 'none';
        } else {
            lightboxPrev.style.display = 'flex';
            lightboxNext.style.display = 'flex';
        }
    }

    function setLightboxZoom(zoomFactor) {
        currentZoom = Math.min(4.0, Math.max(0.25, zoomFactor));
        if (currentZoom <= 1.0) {
            panX = 0;
            panY = 0;
        }
        updateLightboxTransform();
    }

    function resetLightboxZoom() {
        currentZoom = 1.0;
        panX = 0;
        panY = 0;
        updateLightboxTransform();
    }

    function updateLightboxTransform() {
        if (!lightboxImg) return;
        lightboxImg.style.transform = `scale(${currentZoom}) translate(${panX}px, ${panY}px)`;
        lightboxZoomReset.textContent = `${Math.round(currentZoom * 100)}%`;
        if (currentZoom > 1.0) {
            lightboxViewport.style.cursor = 'grab';
        } else {
            lightboxViewport.style.cursor = 'default';
        }
    }

    function closeLightbox() {
        modalLightbox.style.display = 'none';
        modalLightbox.classList.remove('active');
        lightboxImg.src = '';
        resetLightboxZoom();
    }

    lightboxClose.addEventListener('click', closeLightbox);
    modalLightbox.addEventListener('click', (e) => {
        if (e.target === modalLightbox) closeLightbox();
    });

    lightboxPrev.addEventListener('click', (e) => {
        e.stopPropagation();
        showLightboxImage(currentLightboxIdx - 1);
    });

    lightboxNext.addEventListener('click', (e) => {
        e.stopPropagation();
        showLightboxImage(currentLightboxIdx + 1);
    });

    lightboxZoomIn.addEventListener('click', () => setLightboxZoom(currentZoom + 0.25));
    lightboxZoomOut.addEventListener('click', () => setLightboxZoom(currentZoom - 0.25));
    lightboxZoomReset.addEventListener('click', resetLightboxZoom);

    // Pan / Dragging
    lightboxViewport.addEventListener('mousedown', (e) => {
        if (currentZoom <= 1.0) return;
        isPanning = true;
        startPanX = e.clientX - panX * currentZoom;
        startPanY = e.clientY - panY * currentZoom;
        lightboxViewport.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
        if (!isPanning) return;
        panX = (e.clientX - startPanX) / currentZoom;
        panY = (e.clientY - startPanY) / currentZoom;
        lightboxImg.style.transform = `scale(${currentZoom}) translate(${panX}px, ${panY}px)`;
    });

    window.addEventListener('mouseup', () => {
        if (isPanning) {
            isPanning = false;
            lightboxViewport.style.cursor = currentZoom > 1.0 ? 'grab' : 'default';
        }
    });

    // Double click to toggle 100% / 200%
    lightboxViewport.addEventListener('dblclick', (e) => {
        e.preventDefault();
        if (currentZoom === 1.0) {
            setLightboxZoom(2.0);
        } else {
            resetLightboxZoom();
        }
    });

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (modalLightbox && (modalLightbox.style.display === 'flex' || modalLightbox.classList.contains('active'))) {
            if (e.key === 'Escape') closeLightbox();
            else if (e.key === 'ArrowLeft') showLightboxImage(currentLightboxIdx - 1);
            else if (e.key === 'ArrowRight') showLightboxImage(currentLightboxIdx + 1);
            else if (e.key === '+' || e.key === '=') setLightboxZoom(currentZoom + 0.25);
            else if (e.key === '-') setLightboxZoom(currentZoom - 0.25);
            else if (e.key === '0') resetLightboxZoom();
        }
    });

    // =========================================================================
    // WEBP COMPRESSION & OPTIMIZATION CONTROLLER (REQUIREMENT: HEMAT & CEPAT)
    // =========================================================================
    async function loadCompressStats() {
        try {
            if (statNonWebpCount) statNonWebpCount.textContent = '...';
            if (statNonWebpSize) statNonWebpSize.textContent = '... MB';
            if (statWebpCount) statWebpCount.textContent = '...';
            if (statWebpSize) statWebpSize.textContent = '... MB';
            if (statEstSavings) statEstSavings.textContent = '... MB';

            const res = await fetch('/api/tools/image-stats');
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Gagal memuat statistik');

            if (statNonWebpCount) statNonWebpCount.textContent = `${data.non_webp_count} file`;
            if (statNonWebpSize) statNonWebpSize.textContent = `${data.non_webp_mb} MB`;
            if (statWebpCount) statWebpCount.textContent = `${data.webp_count} file`;
            if (statWebpSize) statWebpSize.textContent = `${data.webp_mb} MB`;
            if (statEstSavings) statEstSavings.textContent = `~${data.estimated_savings_mb} MB`;
        } catch (err) {
            console.error('Error loading image stats:', err);
        }
    }

    function openCompressModal() {
        if (!modalCompress) return;
        compressResultBox.style.display = 'none';
        compressProgress.style.display = 'none';
        compressSummaryBanner.style.display = 'none';
        compressFilesListWrap.style.display = 'none';
        btnStartCompress.disabled = false;
        btnStartCompress.innerHTML = `${ICONS.zap} <span>Mulai Konversi ke WebP</span>`;

        modalCompress.style.display = 'flex';
        modalCompress.classList.add('active');
        loadCompressStats();
    }

    function closeCompressModal() {
        if (!modalCompress) return;
        modalCompress.style.display = 'none';
        modalCompress.classList.remove('active');
    }

    if (btnOpenCompress) btnOpenCompress.addEventListener('click', openCompressModal);
    if (modalCompressClose) modalCompressClose.addEventListener('click', closeCompressModal);
    if (modalCompressCancel) modalCompressCancel.addEventListener('click', closeCompressModal);
    if (modalCompress) {
        modalCompress.addEventListener('click', (e) => {
            if (e.target === modalCompress) closeCompressModal();
        });
    }

    if (compressQualityRange && compressQualityDisplay) {
        compressQualityRange.addEventListener('input', () => {
            const val = compressQualityRange.value;
            let desc = 'Standar';
            if (val >= 90) desc = 'Kualitas Tinggi (File Lebih Besar)';
            else if (val >= 80) desc = 'Rekomendasi Optimal (Seimbang & Tajam)';
            else desc = 'Kompresi Maksimum (File Paling Ringan)';
            compressQualityDisplay.textContent = `${val}% (${desc})`;
        });
    }

    if (btnStartCompress) {
        btnStartCompress.addEventListener('click', async () => {
            const target = compressTargetSelect ? compressTargetSelect.value : 'all';
            const quality = compressQualityRange ? parseInt(compressQualityRange.value, 10) : 82;
            const deleteOriginal = compressDeleteToggle ? compressDeleteToggle.checked : true;
            const maxDim = (compressResizeToggle && compressResizeToggle.checked) ? 1920 : 0;

            btnStartCompress.disabled = true;
            btnStartCompress.innerHTML = `<span class="spinner"></span> <span>Sedang Mengonversi...</span>`;

            compressResultBox.style.display = 'block';
            compressProgress.style.display = 'block';
            compressSummaryBanner.style.display = 'none';
            compressFilesListWrap.style.display = 'none';

            try {
                const res = await fetch('/api/tools/compress-webp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        target: target,
                        quality: quality,
                        max_dimension: maxDim,
                        delete_original: deleteOriginal
                    })
                });

                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Terjadi kesalahan saat kompresi');

                compressProgress.style.display = 'none';
                compressSummaryBanner.style.display = 'block';
                compressSummaryBanner.className = 'alert-box success';
                compressSummaryTitle.textContent = `[✓] Konversi Selesai: ${data.total_converted} File Berhasil Dikonversi ke WebP!`;
                compressSummaryDetails.innerHTML = `
                    Ukuran Semula: <strong>${data.original_size_mb} MB</strong> ➔ Ukuran Baru: <strong>${data.compressed_size_mb} MB</strong><br>
                    Total Ruang Terhemat: <strong style="color: #34d399;">${data.saved_size_mb} MB (${data.saved_percent}%)</strong>
                `;

                if (data.converted_files && data.converted_files.length > 0) {
                    compressFilesListWrap.style.display = 'block';
                    compressFilesTbody.innerHTML = data.converted_files.slice(0, 80).map(f => {
                        const fn = f.original_path.split('/').pop();
                        return `
                            <tr>
                                <td style="font-size: 0.8rem;" title="${f.original_path}"><code>${fn}</code></td>
                                <td style="font-size: 0.8rem; color: var(--text-muted);">${f.old_size_kb} KB</td>
                                <td style="font-size: 0.8rem; font-weight: 600; color: #34d399;">${f.new_size_kb} KB</td>
                                <td><span class="status-pill update" style="font-size: 0.72rem;">-${f.saved_percent}%</span></td>
                            </tr>
                        `;
                    }).join('');
                }

                // Reload stats and main document grid
                await loadCompressStats();
                await loadDocuments();
                showToast(`Berhasil mengompresi ${data.total_converted} gambar ke WebP (Hemat ${data.saved_percent}%)!`, 'success');
            } catch (err) {
                console.error('Compression error:', err);
                compressProgress.style.display = 'none';
                compressSummaryBanner.style.display = 'block';
                compressSummaryBanner.className = 'alert-box error';
                compressSummaryTitle.textContent = '[!] Gagal Mengonversi Gambar';
                compressSummaryDetails.textContent = err.message;
                showToast('Gagal kompresi: ' + err.message, 'error');
            } finally {
                btnStartCompress.disabled = false;
                btnStartCompress.innerHTML = `${ICONS.zap} <span>Mulai Konversi ke WebP</span>`;
            }
        });
    }

    // =========================================================================
    // KATALOG MASTER & GAP RADAR CONTROLLER
    // =========================================================================
    let catSearchQuery = '';
    let catCategoryFilter = 'ALL';
    let catGapOnly = false;
    let catSearchTimer = null;

    const catStatTotal = document.getElementById('cat-stat-total');
    const catStatLocal = document.getElementById('cat-stat-local');
    const catStatGap = document.getElementById('cat-stat-gap');
    const catStatTemplates = document.getElementById('cat-stat-templates');
    const badgeCatalogCount = document.getElementById('badge-catalog-count');
    const catCountAll = document.getElementById('cat-count-all');
    const catCountReg = document.getElementById('cat-count-reg');
    const catCountProj = document.getElementById('cat-count-proj');
    const catLastSyncTime = document.getElementById('cat-last-sync-time');

    const catSearchInput = document.getElementById('cat-search-input');
    const catCategoryFilters = document.getElementById('cat-category-filters');
    const btnToggleGapOnly = document.getElementById('btn-toggle-gap-only');
    const btnToggleGapLabel = document.getElementById('btn-toggle-gap-label');
    const btnSyncCatalog = document.getElementById('btn-sync-catalog');
    const catalogTableBody = document.getElementById('catalog-table-body');
    const catalogEmptyState = document.getElementById('catalog-empty-state');

    async function loadCatalogStats() {
        try {
            const res = await fetch('/api/catalog/stats');
            const data = await res.json();
            if (!data) return;

            if (catStatTotal) catStatTotal.textContent = (data.total_parts || 0).toLocaleString();
            if (catStatLocal) catStatLocal.textContent = (data.parts_with_local_doc || 0).toLocaleString();
            if (catStatGap) catStatGap.textContent = (data.gap_count || 0).toLocaleString();
            if (catStatTemplates) catStatTemplates.textContent = (data.total_templates || 0).toLocaleString();
            if (badgeCatalogCount) badgeCatalogCount.textContent = (data.total_parts || 0).toLocaleString();

            if (catCountAll) catCountAll.textContent = (data.total_parts || 0).toLocaleString();
            if (catCountReg) catCountReg.textContent = (data.total_regular || 0).toLocaleString();
            if (catCountProj) catCountProj.textContent = (data.total_project || 0).toLocaleString();

            if (catLastSyncTime && data.synced_at) {
                const d = new Date(data.synced_at);
                const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                catLastSyncTime.textContent = `Disinkronkan: ${timeStr}`;
            }
        } catch (err) {
            console.error('Error loading catalog stats:', err);
        }
    }

    async function loadCatalogTable() {
        if (!catalogTableBody) return;
        catalogTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem;"><span class="spinner"></span> Memuat data katalog...</td></tr>`;

        try {
            const url = `/api/catalog/search?q=${encodeURIComponent(catSearchQuery)}&category=${catCategoryFilter}&limit=120&gap_only=${catGapOnly}`;
            const res = await fetch(url);
            const data = await res.json();
            const results = (data && data.results) ? data.results : [];

            if (results.length === 0) {
                catalogTableBody.innerHTML = '';
                if (catalogEmptyState) catalogEmptyState.style.display = 'block';
                return;
            }

            if (catalogEmptyState) catalogEmptyState.style.display = 'none';

            catalogTableBody.innerHTML = results.map((r, idx) => {
                const catClass = r.category === 'NEW PROJECT' ? 'project' : 'regular';
                const hasLocal = r.has_local;
                const localStatus = r.local_status || 'belum_ada';
                const localLabel = localStatus === 'done' ? 'Done' : localStatus === 'belum' ? 'Belum Dikerjakan' : localStatus === 'tidak_ada_part' ? 'Belum Ada Part' : 'Belum Dibuat';

                const tmplInfo = r.has_template 
                    ? `<span class="tmpl-pill">✓ ${r.template_info?.items_count || 'Ada Template'}</span> <span style="font-size:0.7rem; color:var(--text-muted);">${r.template_info?.status || ''}</span>`
                    : `<span style="color:var(--text-muted); font-size:0.75rem;">- Belum Ada</span>`;

                const actionHtml = hasLocal
                    ? `<button class="btn btn-outline btn-xs btn-open-local" data-status="${localStatus}" data-folder="${r.local_doc?.folder || r.part_number}">Buka Detail</button>`
                    : `<button class="btn btn-primary btn-xs btn-create-catalog" data-part="${r.part_number}">+ Buat Folder</button>`;

                return `
                    <tr>
                        <td style="color: var(--text-muted); font-size: 0.8rem;">${idx + 1}</td>
                        <td>
                            <div class="part-number-cell">
                                <span>${r.part_number}</span>
                                <button class="btn-copy-part" title="Salin Part Number" data-part="${r.part_number}">
                                    ${ICONS.copy}
                                </button>
                            </div>
                        </td>
                        <td><span class="cat-pill ${catClass}">${r.category}</span></td>
                        <td style="font-size: 0.82rem; color: var(--text-secondary); max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            ${r.part_name || '-'}
                        </td>
                        <td>${tmplInfo}</td>
                        <td>
                            <span class="local-status-badge ${localStatus}">
                                ${localLabel}
                            </span>
                        </td>
                        <td style="text-align: right;">${actionHtml}</td>
                    </tr>
                `;
            }).join('');

            // Wire actions
            catalogTableBody.querySelectorAll('.btn-copy-part').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const p = btn.getAttribute('data-part');
                    if (p) {
                        navigator.clipboard.writeText(p).then(() => showToast(`Part '${p}' disalin ke clipboard`, 'info'));
                    }
                });
            });

            catalogTableBody.querySelectorAll('.btn-open-local').forEach(btn => {
                btn.addEventListener('click', () => {
                    const st = btn.getAttribute('data-status');
                    const fol = btn.getAttribute('data-folder');
                    openDetailsModal(st, fol);
                });
            });

            catalogTableBody.querySelectorAll('.btn-create-catalog').forEach(btn => {
                btn.addEventListener('click', () => {
                    const p = btn.getAttribute('data-part');
                    createFolderFromCatalogDirect(p);
                });
            });

        } catch (err) {
            console.error('Error rendering catalog table:', err);
            catalogTableBody.innerHTML = `<tr><td colspan="7" style="color: var(--accent-rose); text-align: center; padding: 2rem;">Gagal memuat data katalog: ${err.message}</td></tr>`;
        }
    }

    function loadCatalogTab() {
        loadCatalogStats();
        loadCatalogTable();
    }

    if (catSearchInput) {
        catSearchInput.addEventListener('input', () => {
            clearTimeout(catSearchTimer);
            catSearchTimer = setTimeout(() => {
                catSearchQuery = catSearchInput.value.trim();
                loadCatalogTable();
            }, 180);
        });
    }

    if (catCategoryFilters) {
        catCategoryFilters.querySelectorAll('.segment-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                catCategoryFilters.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                catCategoryFilter = btn.getAttribute('data-cat') || 'ALL';
                loadCatalogTable();
            });
        });
    }

    if (btnToggleGapOnly) {
        btnToggleGapOnly.addEventListener('click', () => {
            catGapOnly = !catGapOnly;
            btnToggleGapOnly.classList.toggle('active', catGapOnly);
            if (btnToggleGapLabel) {
                btnToggleGapLabel.textContent = catGapOnly ? '✓ Filter Gap Aktif' : 'Filter Gap (Belum Ada)';
            }
            loadCatalogTable();
        });
    }

    if (btnSyncCatalog) {
        btnSyncCatalog.addEventListener('click', async () => {
            const syncIcon = document.getElementById('sync-icon');
            if (syncIcon) syncIcon.style.animation = 'spin 1s linear infinite';
            btnSyncCatalog.disabled = true;
            showToast('Sinkronisasi portal FactoryHub dimulai di background...', 'info');

            try {
                const res = await fetch('/api/catalog/sync', { method: 'POST' });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Gagal memulai sinkronisasi');

                setTimeout(async () => {
                    await loadCatalogStats();
                    await loadCatalogTable();
                    if (syncIcon) syncIcon.style.animation = '';
                    btnSyncCatalog.disabled = false;
                    showToast('[✓] Sinkronisasi Katalog FactoryHub selesai!', 'success');
                }, 12000);
            } catch (err) {
                if (syncIcon) syncIcon.style.animation = '';
                btnSyncCatalog.disabled = false;
                showToast('Gagal sinkronisasi: ' + err.message, 'error');
            }
        });
    }

    // Initial Load
    loadDocuments();
    loadExcelLogs();
    loadCatalogStats();
});
