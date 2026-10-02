document.addEventListener('DOMContentLoaded', function() {
    const preferences = {
        get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
        set(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* Optional storage. */ } }
    };
    const darkModeToggle = document.getElementById('darkModeToggle');
    const html = document.documentElement;
    const darkModeIcon = darkModeToggle ? darkModeToggle.querySelector('i') : null;
    const systemThemeQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    function getThemePreference() {
        const savedPreference = preferences.get('themePreference');
        if (savedPreference === 'light' || savedPreference === 'dark' || savedPreference === 'system') {
            return savedPreference;
        }

        const legacyDarkMode = preferences.get('darkMode');
        if (legacyDarkMode === 'enabled') {
            return 'dark';
        }
        if (legacyDarkMode === 'disabled') {
            return 'light';
        }
        return 'system';
    }

    function shouldUseDarkTheme(preference) {
        return preference === 'dark' || (
            preference === 'system' &&
            systemThemeQuery &&
            systemThemeQuery.matches
        );
    }

    function applyTheme(preference) {
        const useDarkTheme = shouldUseDarkTheme(preference);
        if (useDarkTheme) {
            html.setAttribute('data-theme', 'dark');
        } else {
            html.removeAttribute('data-theme');
        }

        if (darkModeIcon) {
            darkModeIcon.classList.toggle('fa-sun', useDarkTheme);
            darkModeIcon.classList.toggle('fa-moon', !useDarkTheme);
        }
        if (darkModeToggle) {
            darkModeToggle.setAttribute('aria-pressed', useDarkTheme.toString());
        }
        return useDarkTheme;
    }

    let themePreference = getThemePreference();
    preferences.set('themePreference', themePreference);
    applyTheme(themePreference);

    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', function() {
            const isDarkTheme = html.getAttribute('data-theme') === 'dark';
            themePreference = isDarkTheme ? 'light' : 'dark';
            preferences.set('themePreference', themePreference);
            preferences.set('darkMode', themePreference === 'dark' ? 'enabled' : 'disabled');
            applyTheme(themePreference);
            if (typeof applyExpertModeStyles === 'function') {
                applyExpertModeStyles();
            }
        });
    }

    if (systemThemeQuery) {
        systemThemeQuery.addEventListener('change', function() {
            if (themePreference === 'system') {
                applyTheme('system');
                if (typeof applyExpertModeStyles === 'function') {
                    applyExpertModeStyles();
                }
            }
        });
    }

    const languageOptions = document.querySelectorAll('.language-option[data-lang]');
    languageOptions.forEach(option => {
        option.addEventListener('click', function() {
            const targetLang = option.dataset.lang;
            if (!targetLang || option.classList.contains('active')) {
                return;
            }

            const url = new URL(window.location);
            url.searchParams.set('lang', targetLang);
            window.location.href = url.toString();
        });
    });

    const mobilePriceSelectors = document.querySelectorAll('.mobile-price-selector');
    mobilePriceSelectors.forEach(selector => {
        const buttons = selector.querySelectorAll('.mobile-price-selector-button');
        const mobileMenu = selector.closest('.mobile-meal-cards');

        function selectPriceType(priceType) {
            buttons.forEach(button => {
                const isActive = button.dataset.priceType === priceType;
                button.classList.toggle('active', isActive);
                button.setAttribute('aria-pressed', isActive.toString());
            });

            if (!mobileMenu) {
                return;
            }

            mobileMenu.querySelectorAll('.mobile-user-info-row[data-price-type]').forEach(row => {
                row.classList.toggle('d-none', row.dataset.priceType !== priceType);
            });
        }

        buttons.forEach(button => {
            button.addEventListener('click', function() {
                const priceType = button.dataset.priceType || 'student';
                selectPriceType(priceType);
                preferences.set('priceType', priceType);
                const url = new URL(window.location);
                url.searchParams.set('price', priceType);
                window.history.replaceState(null, '', url);

            });
        });

        const requestedPrice = new URLSearchParams(window.location.search).get('price') || preferences.get('priceType');
        selectPriceType(['student', 'employee', 'guest'].includes(requestedPrice) ? requestedPrice : 'student');
    });
    
    // The server renders initial totals and today's vote; no startup API requests.
    const pendingVotes = new Set();
    function voteControlsFor(mealId) {
        return document.querySelectorAll(`.vote-controls[data-meal-id="${mealId}"]`);
    }

    function initMealVoting() {
        document.querySelectorAll('.vote-controls').forEach(controls => {
            controls.querySelectorAll('.vote-btn').forEach(button => {
                button.addEventListener('click', () => submitVote(
                    controls.dataset.mealId, button.classList.contains('upvote-btn') ? 'up' : 'down'
                ));
            });
        });
    }

    async function submitVote(mealId, voteType) {
        if (pendingVotes.has(mealId)) return;
        pendingVotes.add(mealId);
        const controls = voteControlsFor(mealId);
        controls.forEach(control => {
            control.querySelectorAll('button').forEach(button => { button.disabled = true; });
            control.parentElement.querySelector('.meal-feedback').textContent = '';
        });
        try {
            const response = await fetch('/api/vote', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ meal_id: mealId, vote_type: voteType })
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            controls.forEach(control => {
                ['up', 'down'].forEach(kind => {
                    control.querySelector(`.${kind}vote-count`).textContent = data.votes[kind];
                    const button = control.querySelector(`.${kind}vote-btn`);
                    button.classList.toggle('active', kind === voteType);
                    button.setAttribute('aria-pressed', String(kind === voteType));
                });
                const status = control.parentElement.querySelector('.meal-feedback');
                status.classList.remove('is-error');
                status.classList.add('visually-hidden');
                status.textContent = getCommentText('vote_saved', 'Vote saved.');
            });
        } catch (_) {
            controls.forEach(control => {
                const status = control.parentElement.querySelector('.meal-feedback');
                status.classList.remove('visually-hidden');
                status.classList.add('is-error');
                status.textContent = getCommentText('vote_failed', 'Vote not saved. Please try again.');
            });
        } finally {
            pendingVotes.delete(mealId);
            controls.forEach(control => control.querySelectorAll('button').forEach(button => { button.disabled = false; }));
        }
    }

    function getCommentLanguage() {
        if (typeof currentLanguage !== 'undefined' && currentLanguage) {
            return currentLanguage;
        }
        return document.documentElement.lang || 'de';
    }

    function getCommentText(key, fallback) {
        if (typeof uiText !== 'undefined' && uiText && uiText[key]) {
            return uiText[key];
        }
        return fallback;
    }

    function updateCommentCounts(mealId, count) {
        document.querySelectorAll(`.comment-toggle-btn[data-meal-id="${mealId}"] .comment-count`).forEach(countEl => {
            countEl.textContent = count;
        });
    }

    const commentModalElement = document.getElementById('commentPopupModal');
    const commentModal = commentModalElement ? new bootstrap.Modal(commentModalElement) : null;
    const commentModalTitle = commentModalElement ? commentModalElement.querySelector('#commentPopupModalLabel') : null;
    const commentForm = commentModalElement ? commentModalElement.querySelector('#commentPopupForm') : null;
    const commentList = commentModalElement ? commentModalElement.querySelector('#commentPopupList') : null;
    const commentLoadMoreBtn = commentModalElement ? commentModalElement.querySelector('#commentPopupLoadMore') : null;
    const mealImageModalElement = document.getElementById('mealImagePopupModal');
    const mealImageModal = mealImageModalElement ? new bootstrap.Modal(mealImageModalElement) : null;
    const mealImageModalTitle = mealImageModalElement ? mealImageModalElement.querySelector('#mealImagePopupModalLabel') : null;
    const mealImageModalBody = mealImageModalElement ? mealImageModalElement.querySelector('#mealImagePopupBody') : null;
    const mealImageDataCache = new Map();
    let imageGeneration = 0;
    let imageTrigger = null;
    let commentGeneration = 0;
    let commentTrigger = null;
    let commentRequest = null;
    const commentStatus = document.getElementById('commentStatus');
    function setCommentStatus(key, isError = false) {
        commentStatus.textContent = key ? getCommentText(key, key) : '';
        commentStatus.classList.toggle('is-error', isError);
    }
    mealImageModalElement?.addEventListener('hidden.bs.modal', () => {
        imageGeneration++;
        imageTrigger?.focus();
    });
    commentModalElement?.addEventListener('hidden.bs.modal', () => {
        commentGeneration++;
        commentRequest?.abort();
        commentTrigger?.focus();
    });

    function setMealImageStatus(message, isError) {
        if (!mealImageModalBody) {
            return;
        }
        mealImageModalBody.replaceChildren();
        const status = document.createElement('div');
        status.className = isError ? 'meal-image-status text-danger' : 'meal-image-status text-muted';
        status.textContent = message;
        mealImageModalBody.appendChild(status);
    }

    function setMealImageLoading() {
        if (!mealImageModalBody) {
            return;
        }
        mealImageModalBody.replaceChildren();
        const status = document.createElement('div');
        status.className = 'meal-image-status text-muted';
        const spinner = document.createElement('i');
        spinner.className = 'fas fa-spinner fa-spin';
        spinner.setAttribute('aria-hidden', 'true');
        status.appendChild(spinner);
        status.appendChild(document.createTextNode(` ${getCommentText('meal_image_loading', 'Loading image...')}`));
        mealImageModalBody.appendChild(status);
    }

    function renderMealImage(imageUrl, mealTitle) {
        if (!mealImageModalBody) {
            return;
        }
        mealImageModalBody.replaceChildren();
        const image = document.createElement('img');
        image.className = 'meal-image-preview';
        image.src = imageUrl;
        image.alt = mealTitle;
        image.addEventListener('error', () => {
            if (mealImageModalBody.contains(image)) {
                setMealImageStatus(getCommentText('meal_image_unavailable', 'No image available.'), true);
            }
        }, { once: true });
        mealImageModalBody.appendChild(image);
    }

    function getMealImageParams(trigger) {
        return new URLSearchParams({
            meal_id: trigger.dataset.mealId || '',
            mensa: trigger.dataset.mensa || '',
            date: trigger.dataset.date || '',
            lang: getCommentLanguage()
        });
    }

    function getMealImageCacheKey(trigger) {
        return JSON.stringify([
            trigger.dataset.mealId || '',
            trigger.dataset.mensa || '',
            trigger.dataset.date || '',
            getCommentLanguage()
        ]);
    }

    function fetchMealImageData(trigger) {
        const cacheKey = getMealImageCacheKey(trigger);
        if (mealImageDataCache.has(cacheKey)) {
            return mealImageDataCache.get(cacheKey);
        }

        const params = getMealImageParams(trigger);
        const imageDataPromise = fetch(`/api/meal_image?${params.toString()}`)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errorData => {
                        throw new Error(errorData.error || `HTTP error ${response.status}`);
                    });
                }
                return response.json();
            }).catch(error => {
                mealImageDataCache.delete(cacheKey);
                throw error;
            });

        mealImageDataCache.set(cacheKey, imageDataPromise);
        return imageDataPromise;
    }

    function openMealImagePopup(toggle) {
        if (!mealImageModal || !mealImageModalElement || !mealImageModalTitle || !mealImageModalBody) {
            console.error('Meal image modal elements not found');
            return;
        }

        const generation = ++imageGeneration;
        imageTrigger = toggle;
        const mealTitle = toggle.dataset.mealTitle || getCommentText('meal_image', 'Meal image');
        mealImageModalTitle.textContent = mealTitle;
        if (toggle.dataset.imageUrl) {
            renderMealImage(toggle.dataset.imageUrl, mealTitle);
            mealImageModal.show();
            return;
        }

        setMealImageLoading();
        mealImageModal.show();

        fetchMealImageData(toggle)
            .then(data => {
                if (generation !== imageGeneration) return;
                if (data.found && data.image_url) {
                    renderMealImage(data.image_url, mealTitle);
                    return;
                }
                setMealImageStatus(data.message || getCommentText('meal_image_unavailable', 'No image available.'), false);
            })
            .catch(error => {
                if (generation !== imageGeneration) return;
                console.error('Error loading meal image:', error);
                const template = getCommentText('meal_image_lookup_failed', 'The image could not be loaded: {error}');
                setMealImageStatus(template.replace('{error}', error.message), true);
            });
    }

    function hideMealThumbnail(thumbnail) {
        thumbnail.classList.remove('is-loading', 'is-loaded', 'is-unavailable');
        thumbnail.hidden = true;
        thumbnail.removeAttribute('data-image-url');
        thumbnail.removeAttribute('data-thumbnail-url');
        thumbnail.replaceChildren();
        thumbnail.parentElement.querySelector('.meal-thumbnail-slot').hidden = false;
    }

    function renderMealThumbnail(thumbnail, thumbnailUrl, imageUrl) {
        thumbnail.classList.remove('is-loading', 'is-unavailable');
        thumbnail.classList.add('is-loaded');
        thumbnail.dataset.imageUrl = imageUrl;
        thumbnail.dataset.thumbnailUrl = thumbnailUrl;

        const image = document.createElement('img');
        image.className = thumbnail.classList.contains('mobile-meal-thumbnail')
            ? 'mobile-meal-thumbnail-img'
            : 'meal-image-thumbnail-img';
        image.src = thumbnailUrl;
        image.alt = thumbnail.dataset.mealTitle || getCommentText('meal_image', 'Meal image');
        image.decoding = 'async';
        image.loading = 'lazy';
        image.addEventListener('error', function() {
            hideMealThumbnail(thumbnail);
        }, { once: true });

        thumbnail.replaceChildren(image);
        thumbnail.hidden = false;
        thumbnail.parentElement.querySelector('.meal-thumbnail-slot').hidden = true;
    }

    function loadMealThumbnail(thumbnail) {
        if (thumbnail.dataset.thumbnailLoaded === 'true') {
            return;
        }
        thumbnail.dataset.thumbnailLoaded = 'true';
        thumbnail.classList.add('is-loading');
        thumbnail.hidden = true;

        return fetchMealImageData(thumbnail)
            .then(data => {
                const thumbnailUrl = data.thumbnail_url || data.image_url;
                if (data.found && thumbnailUrl && data.image_url) {
                    renderMealThumbnail(thumbnail, thumbnailUrl, data.image_url);
                    return;
                }
                hideMealThumbnail(thumbnail);
            })
            .catch(error => {
                console.error('Error loading meal thumbnail:', error);
                hideMealThumbnail(thumbnail);
            });
    }

    function createCommentElement(comment) {
        const item = document.createElement('article');
        item.className = `comment-item comment-item-${comment.rating}`;

        const meta = document.createElement('div');
        meta.className = 'comment-meta';

        const rating = document.createElement('span');
        rating.className = 'comment-rating-label';
        const ratingIcon = document.createElement('i');
        ratingIcon.className = comment.rating === 'good' ? 'fas fa-thumbs-up' : 'fas fa-thumbs-down';
        ratingIcon.setAttribute('aria-hidden', 'true');
        rating.appendChild(ratingIcon);
        rating.appendChild(document.createTextNode(
            comment.rating === 'good'
                ? getCommentText('comment_good', 'Good')
                : getCommentText('comment_bad', 'Bad')
        ));

        const author = document.createElement('span');
        author.className = 'comment-author';
        author.textContent = comment.author_name || getCommentText('anonymous', 'Anonymous');

        const time = document.createElement('time');
        time.className = 'comment-time';
        if (comment.created_at) {
            const createdAt = new Date(comment.created_at);
            if (!Number.isNaN(createdAt.getTime())) {
                time.dateTime = comment.created_at;
                time.textContent = createdAt.toLocaleString(getCommentLanguage());
            }
        }

        meta.appendChild(rating);
        meta.appendChild(author);
        if (time.textContent) {
            meta.appendChild(time);
        }
        item.appendChild(meta);

        if (comment.has_text && comment.text) {
            const text = document.createElement('p');
            text.className = 'comment-text';
            text.textContent = comment.text;
            item.appendChild(text);
        }

        if (comment.translation_failed && comment.has_text) {
            const notice = document.createElement('small');
            notice.className = 'comment-translation-warning';
            notice.textContent = getCommentText('translation_unavailable', 'Translation unavailable');
            item.appendChild(notice);
        }

        return item;
    }

    function renderCommentList(comments, append) {
        if (!commentList) {
            return;
        }
        if (!append) {
            commentList.replaceChildren();
        }

        if (!comments.length && !append) {
            const empty = document.createElement('p');
            empty.className = 'comment-empty';
            empty.textContent = getCommentText('no_comments', 'No comments yet.');
            commentList.appendChild(empty);
            return;
        }

        const existingEmpty = commentList.querySelector('.comment-empty');
        if (existingEmpty) {
            existingEmpty.remove();
        }
        comments.forEach(comment => {
            commentList.appendChild(createCommentElement(comment));
        });
    }

    function loadComments(append) {
        if (!commentModalElement) {
            return;
        }
        const mealId = commentModalElement.dataset.mealId;
        if (!mealId) {
            return;
        }
        commentRequest?.abort();
        const controller = new AbortController();
        commentRequest = controller;
        setCommentStatus('comments_loading');
        const offset = append ? Number.parseInt(commentModalElement.dataset.loadedCount || '0', 10) : 0;
        const params = new URLSearchParams({
            limit: '5',
            offset: offset.toString(),
            lang: getCommentLanguage()
        });

        if (commentLoadMoreBtn) {
            commentLoadMoreBtn.disabled = true;
        }

        fetch(`/api/comments/${mealId}?${params.toString()}`, { signal: controller.signal })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (commentRequest !== controller) return;
                setCommentStatus('');
                renderCommentList(data.comments || [], append);
                const loadedCount = append
                    ? offset + (data.comments || []).length
                    : (data.comments || []).length;
                commentModalElement.dataset.loadedCount = loadedCount.toString();
                updateCommentCounts(mealId, data.count || 0);
                if (commentLoadMoreBtn) {
                    commentLoadMoreBtn.classList.toggle('d-none', !data.has_more);
                    commentLoadMoreBtn.textContent = getCommentText('load_more_comments', 'Load more comments');
                    delete commentLoadMoreBtn.dataset.retry;
                }
            })
            .catch(error => {
                if (error.name === 'AbortError' || commentRequest !== controller) return;
                setCommentStatus('comments_failed', true);
                commentLoadMoreBtn.dataset.retry = append ? 'append' : 'reload';
                commentLoadMoreBtn.textContent = getCommentText('retry', 'Try again');
                commentLoadMoreBtn.classList.remove('d-none');
            })
            .finally(() => {
                if (commentLoadMoreBtn && commentRequest === controller) {
                    commentLoadMoreBtn.disabled = false;
                }
            });
    }

    function setCommentRating(scope, rating) {
        if (!scope) {
            return;
        }
        scope.querySelectorAll('.comment-rating-btn').forEach(button => {
            const isActive = button.dataset.rating === rating;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-pressed', isActive.toString());
        });
    }

    function resetCommentForm() {
        if (!commentForm) {
            return;
        }
        const nameInput = commentForm.querySelector('.comment-name-input');
        const textInput = commentForm.querySelector('.comment-text-input');
        if (nameInput) {
            nameInput.value = '';
        }
        if (textInput) {
            textInput.value = '';
        }
        setCommentRating(commentForm, 'good');
    }

    function openCommentPopup(toggle) {
        if (!commentModal || !commentModalElement || !commentModalTitle || !commentList) {
            console.error('Comment modal elements not found');
            return;
        }
        const mealId = toggle.dataset.mealId || '';
        if (!mealId) {
            return;
        }
        const mealTitle = toggle.dataset.mealTitle || getCommentText('comments', 'Comments');
        commentGeneration++;
        commentTrigger = toggle;
        commentModalElement.dataset.mealId = mealId;
        commentModalElement.dataset.loadedCount = '0';
        commentModalTitle.textContent = mealTitle;
        commentList.replaceChildren();
        if (commentLoadMoreBtn) {
            commentLoadMoreBtn.classList.add('d-none');
        }
        resetCommentForm();
        loadComments(false);
        commentModal.show();
    }

    function initMealComments() {
        if (commentForm) {
            setCommentRating(commentForm, 'good');

            commentForm.querySelectorAll('.comment-rating-btn').forEach(button => {
                button.addEventListener('click', function() {
                    setCommentRating(commentForm, button.dataset.rating || 'good');
                });
            });

            commentForm.addEventListener('submit', function(event) {
                event.preventDefault();
                if (!commentModalElement || !commentModalElement.dataset.mealId) {
                    return;
                }
                const generation = commentGeneration;
                const submitBtn = commentForm.querySelector('.comment-submit-btn');
                const activeRating = commentForm.querySelector('.comment-rating-btn.active');
                const nameInput = commentForm.querySelector('.comment-name-input');
                const textInput = commentForm.querySelector('.comment-text-input');
                const payload = {
                    meal_id: commentModalElement.dataset.mealId,
                    rating: activeRating ? activeRating.dataset.rating : 'good',
                    author_name: nameInput ? nameInput.value.trim() : '',
                    text: textInput ? textInput.value.trim() : '',
                    lang: getCommentLanguage()
                };

                setCommentStatus('');
                if (submitBtn) {
                    if (submitBtn.disabled) return;
                    submitBtn.disabled = true;
                }

                fetch('/api/comments', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(errorData => {
                            throw new Error(errorData.error || `HTTP error ${response.status}`);
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    updateCommentCounts(payload.meal_id, data.count || 0);
                    if (generation !== commentGeneration) return;
                    resetCommentForm();
                    loadComments(false);
                })
                .catch(error => {
                    if (generation === commentGeneration) setCommentStatus('comment_failed', true);
                })
                .finally(() => {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                    }
                });
            });
        }

        if (commentLoadMoreBtn) {
            commentLoadMoreBtn.addEventListener('click', function() {
                loadComments(commentLoadMoreBtn.dataset.retry !== 'reload');
            });
        }

        document.querySelectorAll('.comment-toggle-btn').forEach(toggle => {
            toggle.addEventListener('click', function() {
                openCommentPopup(toggle);
            });
        });
    }

    function initMealImages() {
        const queue = [];
        let active = 0;
        const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                observer.unobserve(entry.target);
                queue.push(entry.target.querySelector('.meal-image-thumbnail-toggle'));
            });
            drain();
        }, { rootMargin: '160px' }) : null;

        function drain() {
            while (active < 3 && queue.length) {
                const thumbnail = queue.shift();
                const container = thumbnail.parentElement;
                if (observer && !container.getClientRects().length) {
                    observer.observe(container);
                    continue;
                }
                active++;
                Promise.resolve(loadMealThumbnail(thumbnail)).finally(() => { active--; drain(); });
            }
        }
        document.querySelectorAll('.meal-image-thumbnail-toggle').forEach(toggle => {
            toggle.addEventListener('click', () => openMealImagePopup(toggle));
            if (observer) observer.observe(toggle.parentElement);
            else queue.push(toggle);
        });
        drain();
    }

    // Initialize meal voting and comments after their DOM helpers are ready.
    initMealVoting();
    initMealComments();
    initMealImages();
    

    // Expert Mode Toggle
    const expertModeToggleIcon = document.getElementById('expertModeToggleIcon');
    const expertModeCols = document.querySelectorAll('.expert-mode-col');
    
    // Check URL parameter for expert mode - URL is the source of truth
    const urlParams = new URLSearchParams(window.location.search);
    const expertModeFromUrl = urlParams.get('expert') === 'true';

    // Set expertModeEnabled based on URL parameter (backend controls the state)
    // When URL has ?expert=true, enable expert mode
    // Otherwise, expert mode is OFF by default
    let expertModeEnabled = expertModeFromUrl;
    
    // Sync localStorage with the URL state to maintain consistency
    preferences.set('expertModeEnabled', expertModeEnabled.toString());

    // Helper functions for color interpolation
    function hexToRgb(hex) {
        let r = 0, g = 0, b = 0;
        if (hex.length === 4) { // #RGB
            r = parseInt(hex[1] + hex[1], 16);
            g = parseInt(hex[2] + hex[2], 16);
            b = parseInt(hex[3] + hex[3], 16);
        } else if (hex.length === 7) { // #RRGGBB
            r = parseInt(hex.substring(1, 3), 16);
            g = parseInt(hex.substring(3, 5), 16);
            b = parseInt(hex.substring(5, 7), 16);
        }
        return { r, g, b };
    }

    function rgbToHex(r, g, b) {
        return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).padStart(6, '0');
    }

    function interpolateColor(colorStartHex, colorEndHex, factor) {
        // Clamp factor to [0, 1]
        const t = Math.max(0, Math.min(1, factor));

        const rgbStart = hexToRgb(colorStartHex);
        const rgbEnd = hexToRgb(colorEndHex);

        const r = Math.round(rgbStart.r + t * (rgbEnd.r - rgbStart.r));
        const g = Math.round(rgbStart.g + t * (rgbEnd.g - rgbStart.g));
        const b = Math.round(rgbStart.b + t * (rgbEnd.b - rgbStart.b));

        return rgbToHex(r, g, b);
    }

    function applyExpertModeStyles() {
        const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
        let colorNegative, colorPositive, colorCenter;

        if (isDarkMode) {
            colorNegative = '#ff5555'; // Dark mode Downvote Red
            colorCenter = '#FFB86C';   // Dark mode Center Yellow/Orange
            colorPositive = '#50fa7b'; // Dark mode Upvote Green
        } else {
            colorNegative = '#b42336'; // Light mode Downvote Red
            colorCenter = '#775500';   // Light mode Center Yellow
            colorPositive = '#176b3a'; // Light mode Upvote Green
        }

        expertModeCols.forEach(col => {
            col.classList.toggle('d-none', !expertModeEnabled);
            if (col.tagName === 'TH' || col.tagName === 'TD') {
                col.style.display = expertModeEnabled ? 'table-cell' : 'none';
            } else if (col.classList.contains('mobile-expert-info-row')) {
                col.style.display = expertModeEnabled ? 'grid' : 'none';
            } else { // For mobile view elements (divs behaving as rows/items)
                col.style.display = expertModeEnabled ? 'flex' : 'none';
            }
        });
        if (expertModeToggleIcon) {
            expertModeToggleIcon.style.opacity = '1';
            expertModeToggleIcon.classList.toggle('active', expertModeEnabled);
            expertModeToggleIcon.setAttribute('aria-pressed', expertModeEnabled.toString());
        }

        const canerElements = document.querySelectorAll('.caner-symbols');
        const rkrElements = document.querySelectorAll('strong.rkr-value');
        const mpsElements = document.querySelectorAll('strong.mps-value');

        if (expertModeEnabled) {
            canerElements.forEach(el => {
                const canerValueText = el.dataset.canerValue;
                if (canerValueText === undefined) return;

                const canerValue = parseFloat(canerValueText);
                if (!isNaN(canerValue)) {
                    const scaleMaxCaner = 600; // Max value for pure positive color
                    let finalColor;
                    const visualMidPointCaner = scaleMaxCaner / 2; // Midpoint for color transition

                    if (canerValue <= 0) {
                        finalColor = colorNegative;
                    } else if (canerValue >= scaleMaxCaner) {
                        finalColor = colorPositive;
                    } else if (canerValue <= visualMidPointCaner) {
                        // Interpolate from colorNegative (at 0) to colorCenter (at visualMidPointCaner)
                        const factor = canerValue / visualMidPointCaner;
                        finalColor = interpolateColor(colorNegative, colorCenter, factor);
                    } else {
                        // Interpolate from colorCenter (at visualMidPointCaner) to colorPositive (at scaleMaxCaner)
                        const factor = (canerValue - visualMidPointCaner) / (scaleMaxCaner - visualMidPointCaner);
                        finalColor = interpolateColor(colorCenter, colorPositive, factor);
                    }
                    el.style.color = finalColor;
                }
            });

            // Reorder spans for expert mode: caner-value first for desktop, caner-symbol first for mobile
            canerElements.forEach(el => {
                const canerValueSpan = el.querySelector('.caner-value');
                const canerSymbolSpan = el.querySelector('.caner-symbol');
                if (canerValueSpan && canerSymbolSpan) {
                    if (el.parentElement.classList.contains('mobile-layout')) {
                        // For mobile expert, caner-symbol first, then caner-value
                        el.insertBefore(canerSymbolSpan, canerValueSpan);
                    } else {
                        // For desktop expert, caner-value first
                        el.insertBefore(canerValueSpan, canerSymbolSpan);
                    }
                }
            });

            rkrElements.forEach(el => {
                const textValue = el.textContent.replace(',', '.').replace(/[^\d.-]/g, '');
                const rkrValue = parseFloat(textValue);

                if (!isNaN(rkrValue)) {
                    const scaleMaxRkr = 20; // Max value for pure positive color
                    let finalColor;
                    const visualMidPointRkr = scaleMaxRkr / 2; // Midpoint for color transition

                    if (rkrValue <= 0) {
                        finalColor = colorNegative;
                    } else if (rkrValue >= scaleMaxRkr) {
                        finalColor = colorPositive;
                    } else if (rkrValue <= visualMidPointRkr) {
                        // Interpolate from colorNegative (at 0) to colorCenter (at visualMidPointRkr)
                        const factor = rkrValue / visualMidPointRkr;
                        finalColor = interpolateColor(colorNegative, colorCenter, factor);
                    } else {
                        // Interpolate from colorCenter (at visualMidPointRkr) to colorPositive (at scaleMaxRkr)
                        const factor = (rkrValue - visualMidPointRkr) / (scaleMaxRkr - visualMidPointRkr);
                        finalColor = interpolateColor(colorCenter, colorPositive, factor);
                    }
                    el.style.color = finalColor;
                }
            });

            mpsElements.forEach(el => {
                const textValue = el.textContent.replace(',', '.').replace(/[^\d.-]/g, '');
                const mpsValue = parseFloat(textValue);

                if (!isNaN(mpsValue)) {
                    const scaleMaxMps = 100; // Max value for pure positive color (0-100 scale)
                    let finalColor;
                    const visualMidPointMps = scaleMaxMps / 2; // Midpoint for color transition

                    if (mpsValue <= 0) {
                        finalColor = colorNegative;
                    } else if (mpsValue >= scaleMaxMps) {
                        finalColor = colorPositive;
                    } else if (mpsValue <= visualMidPointMps) {
                        // Interpolate from colorNegative (at 0) to colorCenter (at visualMidPointMps)
                        const factor = mpsValue / visualMidPointMps;
                        finalColor = interpolateColor(colorNegative, colorCenter, factor);
                    } else {
                        // Interpolate from colorCenter (at visualMidPointMps) to colorPositive (at scaleMaxMps)
                        const factor = (mpsValue - visualMidPointMps) / (scaleMaxMps - visualMidPointMps);
                        finalColor = interpolateColor(colorCenter, colorPositive, factor);
                    }
                    el.style.color = finalColor;
                }
            });

        } else { // Expert mode disabled
            canerElements.forEach(el => {
                el.style.color = ''; // Reset color
            });
            rkrElements.forEach(el => {
                el.style.color = ''; // Reset color
            });
            mpsElements.forEach(el => {
                el.style.color = ''; // Reset color
            });

            // Reorder spans for non-expert mode: caner-symbol first, then caner-value
            canerElements.forEach(el => {
                const canerValueSpan = el.querySelector('.caner-value');
                const canerSymbolSpan = el.querySelector('.caner-symbol');
                if (canerValueSpan && canerSymbolSpan) {
                    el.insertBefore(canerSymbolSpan, canerValueSpan);
                }
            });
        }
    }

    if (expertModeToggleIcon) {
        applyExpertModeStyles(); // Apply initial state on load

        expertModeToggleIcon.addEventListener('click', function() {
            expertModeEnabled = !expertModeEnabled; // Toggle the state
            preferences.set('expertModeEnabled', expertModeEnabled.toString());
            applyExpertModeStyles();

            // Keep the menu and focus in place while updating the shareable URL.
            const url = new URL(window.location);
            if (expertModeEnabled) {
                url.searchParams.set('expert', 'true');
            } else {
                url.searchParams.delete('expert');
            }
            window.history.replaceState(null, '', url);
        });
    }

});
