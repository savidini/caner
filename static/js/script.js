document.addEventListener('DOMContentLoaded', function() {
    const darkModeToggle = document.getElementById('darkModeToggle');
    const html = document.documentElement;
    const darkModeIcon = darkModeToggle ? darkModeToggle.querySelector('i') : null;
    const systemThemeQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

    function getThemePreference() {
        if (new URLSearchParams(window.location.search).get('theme') === 'dark') {
            return 'dark';
        }

        const savedPreference = localStorage.getItem('themePreference');
        if (savedPreference === 'light' || savedPreference === 'dark' || savedPreference === 'system') {
            return savedPreference;
        }

        const legacyDarkMode = localStorage.getItem('darkMode');
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
    localStorage.setItem('themePreference', themePreference);
    applyTheme(themePreference);

    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', function() {
            const isDarkTheme = html.getAttribute('data-theme') === 'dark';
            themePreference = isDarkTheme ? 'light' : 'dark';
            localStorage.setItem('themePreference', themePreference);
            localStorage.setItem('darkMode', themePreference === 'dark' ? 'enabled' : 'disabled');
            applyTheme(themePreference);
            if (typeof applyExpertModeStyles === 'function') {
                applyExpertModeStyles();
            }
        });
    }

    if (systemThemeQuery) {
        systemThemeQuery.addEventListener('change', function() {
            if (getThemePreference() === 'system') {
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
                selectPriceType(button.dataset.priceType || 'student');
            });
        });

        selectPriceType('student');
    });
    
    // Meal voting functionality
    function initMealVoting() {
        // Find all vote controls in the document
        const voteControls = document.querySelectorAll('.vote-controls');

        // For each vote control section
        voteControls.forEach(controls => {
            const mealId = controls.dataset.mealId;
            const upvoteBtn = controls.querySelector('.upvote-btn');
            const downvoteBtn = controls.querySelector('.downvote-btn');
            const upvoteCount = controls.querySelector('.upvote-count');
            const downvoteCount = controls.querySelector('.downvote-count');

            // Skip if any element is missing
            if (!mealId || !upvoteBtn || !downvoteBtn || !upvoteCount || !downvoteCount) {
                console.error('Missing elements in vote controls');
                return;
            }

            // Load initial vote counts from the server
            loadVoteCounts(mealId, upvoteCount, downvoteCount, upvoteBtn, downvoteBtn);

            // Add event listeners for vote buttons
            upvoteBtn.addEventListener('click', function() {
                submitVote(mealId, 'up', upvoteCount, downvoteCount, upvoteBtn, downvoteBtn);
            });

            downvoteBtn.addEventListener('click', function() {
                submitVote(mealId, 'down', upvoteCount, downvoteCount, upvoteBtn, downvoteBtn);
            });
        });
    }

    // Load vote counts from the server
    function loadVoteCounts(mealId, upvoteCount, downvoteCount, upvoteBtn, downvoteBtn) {
        fetch(`/api/votes/${mealId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                // Update vote counts
                upvoteCount.textContent = data.votes.up;
                downvoteCount.textContent = data.votes.down;

                // If the user has already voted, highlight the button
                if (data.has_voted) {
                    // Check user's stored votes in local storage
                    const storedVote = localStorage.getItem(`meal_vote_${mealId}`);
                    if (storedVote === 'up') {
                        upvoteBtn.classList.add('active');
                    } else if (storedVote === 'down') {
                        downvoteBtn.classList.add('active');
                    }
                }
            })
            .catch(error => {
                console.error('Error loading vote counts:', error);
            });
    }

    // Submit a vote to the server
    function submitVote(mealId, voteType, upvoteCount, downvoteCount, upvoteBtn, downvoteBtn) {
        // Create request payload
        const payload = {
            meal_id: mealId,
            vote_type: voteType
        };

        // Send the vote to the server
        fetch('/api/vote', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Update vote counts
            upvoteCount.textContent = data.votes.up;
            downvoteCount.textContent = data.votes.down;

            // Update active state of vote buttons
            upvoteBtn.classList.toggle('active', voteType === 'up');
            downvoteBtn.classList.toggle('active', voteType === 'down');

            // Store the vote in local storage to remember which button was clicked
            localStorage.setItem(`meal_vote_${mealId}`, voteType);
        })
        .catch(error => {
            console.error('Error submitting vote:', error);
        });
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
        image.loading = 'lazy';
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
            });

        mealImageDataCache.set(cacheKey, imageDataPromise);
        return imageDataPromise;
    }

    function openMealImagePopup(toggle) {
        if (!mealImageModal || !mealImageModalElement || !mealImageModalTitle || !mealImageModalBody) {
            console.error('Meal image modal elements not found');
            return;
        }

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
                if (data.found && data.image_url) {
                    renderMealImage(data.image_url, mealTitle);
                    return;
                }
                setMealImageStatus(data.message || getCommentText('meal_image_unavailable', 'No image available.'), false);
            })
            .catch(error => {
                console.error('Error loading meal image:', error);
                const template = getCommentText('meal_image_lookup_failed', 'The image could not be loaded: {error}');
                setMealImageStatus(template.replace('{error}', error.message), true);
            });
    }

    function setMealThumbnailLayout(thumbnail, hasThumbnail) {
        const mobileCardMain = thumbnail.closest('.mobile-meal-card-main');
        if (mobileCardMain) {
            mobileCardMain.classList.toggle('has-meal-thumbnail', hasThumbnail);
        }

        const desktopMeal = thumbnail.closest('.meal-table-meal');
        if (desktopMeal) {
            desktopMeal.classList.toggle('has-meal-thumbnail', hasThumbnail);
        }
    }

    function hideMealThumbnail(thumbnail) {
        thumbnail.classList.remove('is-loading', 'is-loaded', 'is-unavailable');
        thumbnail.hidden = true;
        thumbnail.removeAttribute('data-image-url');
        thumbnail.removeAttribute('data-thumbnail-url');
        thumbnail.replaceChildren();
        setMealThumbnailLayout(thumbnail, false);
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
        setMealThumbnailLayout(thumbnail, true);
    }

    function loadMealThumbnail(thumbnail) {
        if (thumbnail.dataset.thumbnailLoaded === 'true') {
            return;
        }
        thumbnail.dataset.thumbnailLoaded = 'true';
        thumbnail.classList.add('is-loading');
        thumbnail.hidden = true;

        fetchMealImageData(thumbnail)
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

    function loadCommentCount(mealId) {
        const params = new URLSearchParams({
            limit: '1',
            offset: '0',
            lang: getCommentLanguage()
        });

        fetch(`/api/comments/${mealId}?${params.toString()}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                updateCommentCounts(mealId, data.count || 0);
            })
            .catch(error => {
                console.error('Error loading comment count:', error);
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
        const offset = append ? Number.parseInt(commentModalElement.dataset.loadedCount || '0', 10) : 0;
        const params = new URLSearchParams({
            limit: '5',
            offset: offset.toString(),
            lang: getCommentLanguage()
        });

        if (commentLoadMoreBtn) {
            commentLoadMoreBtn.disabled = true;
        }

        fetch(`/api/comments/${mealId}?${params.toString()}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                renderCommentList(data.comments || [], append);
                const loadedCount = append
                    ? offset + (data.comments || []).length
                    : (data.comments || []).length;
                commentModalElement.dataset.loadedCount = loadedCount.toString();
                updateCommentCounts(mealId, data.count || 0);
                if (commentLoadMoreBtn) {
                    commentLoadMoreBtn.classList.toggle('d-none', !data.has_more);
                }
            })
            .catch(error => {
                console.error('Error loading comments:', error);
            })
            .finally(() => {
                if (commentLoadMoreBtn) {
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

                if (submitBtn) {
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
                    resetCommentForm();
                    updateCommentCounts(commentModalElement.dataset.mealId, data.count || 0);
                    loadComments(false);
                })
                .catch(error => {
                    console.error('Error submitting comment:', error);
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
                loadComments(true);
            });
        }

        const countedMealIds = new Set();
        document.querySelectorAll('.comment-toggle-btn').forEach(toggle => {
            if (toggle.dataset.mealId && !countedMealIds.has(toggle.dataset.mealId)) {
                countedMealIds.add(toggle.dataset.mealId);
                loadCommentCount(toggle.dataset.mealId);
            }

            toggle.addEventListener('click', function() {
                openCommentPopup(toggle);
            });
        });
    }

    function initMealImages() {
        const imageToggles = document.querySelectorAll('.meal-image-thumbnail-toggle');
        if (!imageToggles.length) {
            return;
        }

        imageToggles.forEach(toggle => {
            toggle.addEventListener('click', function() {
                openMealImagePopup(toggle);
            });
            loadMealThumbnail(toggle);
        });
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
    localStorage.setItem('expertModeEnabled', expertModeEnabled.toString());

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
            colorNegative = '#dc3545'; // Light mode Downvote Red
            colorCenter = '#ffcc00';   // Light mode Center Yellow
            colorPositive = '#28a745'; // Light mode Upvote Green
        }

        expertModeCols.forEach(col => {
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
            localStorage.setItem('expertModeEnabled', expertModeEnabled.toString());
            applyExpertModeStyles();

            // Reload the page with the expert parameter to apply the change
            const url = new URL(window.location);
            if (expertModeEnabled) {
                url.searchParams.set('expert', 'true');
            } else {
                url.searchParams.delete('expert');
            }
            window.location.href = url.toString();
        });
    }

});
