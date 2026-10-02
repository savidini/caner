document.addEventListener('DOMContentLoaded', function () {
  const recommendationModalElement = document.getElementById('recommendationPopupModal');
  const recommendationModal = recommendationModalElement ? new bootstrap.Modal(recommendationModalElement) : null;
  const recommendationModalTitle = recommendationModalElement ? recommendationModalElement.querySelector('#recommendationPopupModalLabel') : null;
  const recommendationModalBody = recommendationModalElement ? recommendationModalElement.querySelector('#recommendationPopupBody') : null;
  const recommendationModalContent = recommendationModalElement ? recommendationModalElement.querySelector('#recommendationPopupContent') : null;
  const recommendationModalOverlay = recommendationModalElement ? recommendationModalElement.querySelector('#recommendationPopupOverlay') : null;
  const recommendationSelect = document.getElementById('recommendationRecommenderSelect');
  const recommendationDropdownLabel = document.getElementById('recommendationRecommenderDropdownLabel');
  const recommendationCustomInput = document.getElementById('recommendationCustomRecommender');
  const requestRecommendationButton = document.getElementById('requestRecommendationButton');
  const recommenderProfiles = {
    Marvin: { backgroundUrl: '/static/img/marvin.jpg' },
    'Gordon Ramsay': { backgroundUrl: '/static/img/gordon-ramsay.jpg' },
    'Rick Sanchez': { backgroundUrl: '/static/img/rick-sanchez.jpg' },
    'Donald Trump': { backgroundUrl: '/static/img/trump.jpg' }
  };
  let currentRecommendationMensa = '';
  let recommendationRequest = null;
  let recommendationTrigger = null;
  recommendationModalElement?.addEventListener('hidden.bs.modal', () => {
    recommendationRequest?.abort();
    recommendationRequest = null;
    recommendationTrigger?.focus();
  });

  function applyLanguageParam(params) {
    if (currentLanguage) {
      params.set('lang', currentLanguage);
    }
  }

  function navigateMenu() {
    const params = new URLSearchParams(window.location.search);
    params.set('mensa', document.getElementById('mensa').value);
    params.set('date', document.getElementById('date').value);
    applyLanguageParam(params);
    window.location.href = `/?${params.toString()}`;
  }
  ['mensa', 'date'].forEach(id => {
    document.getElementById(id)?.addEventListener('change', navigateMenu);
  });

  function setRecommendationRecommender(value) {
    if (!recommendationSelect) {
      return;
    }
    recommendationSelect.value = value;
    document.querySelectorAll('.recommendation-recommender-item').forEach(item => {
      const isActive = item.dataset.value === value;
      item.classList.toggle('active', isActive);
      if (isActive) {
        item.setAttribute('aria-current', 'true');
      } else {
        item.removeAttribute('aria-current');
      }
    });
    const activeItem = [...document.querySelectorAll('.recommendation-recommender-item')].find(item => item.dataset.value === value);
    if (recommendationDropdownLabel && activeItem) {
      recommendationDropdownLabel.textContent = activeItem.textContent.trim();
    }
    const isCustom = value === '__custom__';
    if (recommendationCustomInput) {
      recommendationCustomInput.classList.toggle('d-none', !isCustom);
      if (isCustom) {
        recommendationCustomInput.focus();
      }
    }
    const profile = recommenderProfiles[value];
    setRecommendationBackground(profile ? profile.backgroundUrl : '');
  }

  function setRecommendationBackground(backgroundUrl, isError = false) {
    if (!recommendationModalContent || !recommendationModalOverlay) {
      return;
    }
    recommendationModalContent.style.backgroundImage = backgroundUrl ? `url('${backgroundUrl}')` : 'none';
    recommendationModalOverlay.classList.toggle('is-error', isError);
  }

  function escapeHtml(value) {
    const element = document.createElement('span');
    element.textContent = value;
    return element.innerHTML;
  }

  function setRecommendationResult(message, isError = false) {
    if (!recommendationModalBody) {
      return;
    }
    recommendationModalBody.classList.toggle('is-error', isError);
    recommendationModalBody.innerHTML = message;
  }

  function openRecommendationPopup(mensaName) {
    if (!recommendationModal || !recommendationModalTitle || !recommendationModalBody || !recommendationModalContent || !recommendationModalOverlay) {
      console.error("Popup modal elements not found");
      return;
    }
    currentRecommendationMensa = mensaName;
    recommendationModalTitle.textContent = (uiText.recommendation_for || 'Empfehlung für {mensa}').replace('{mensa}', mensaName);
    setRecommendationRecommender('Marvin');
    if (recommendationCustomInput) {
      recommendationCustomInput.value = '';
    }
    setRecommendationResult(`<p class="text-muted mb-0">${uiText.recommendation_intro}</p>`);
    if (requestRecommendationButton) {
      requestRecommendationButton.disabled = getMealsFromMensaSection(mensaName).length === 0;
    }
    if (requestRecommendationButton && requestRecommendationButton.disabled) {
      setRecommendationResult(`<p class="text-danger mb-0">${uiText.recommendation_no_meals}</p>`, true);
    }
    recommendationModal.show();
  }

  function getMealsFromMensaSection(mensaName) {
    const meals = new Set();
    if (typeof mealData !== 'undefined' && mealData && mealData[mensaName]) {
      mealData[mensaName].forEach(name => meals.add(name));
      return Array.from(meals);
    }

    document.querySelectorAll('.mensa-section').forEach(section => {
      if (section.dataset.mensa === mensaName) {
        section.querySelectorAll('.meal-table tbody tr').forEach(row => {
          const mealDescElement = row.querySelector('.meal-name-text');
          if (mealDescElement) meals.add(mealDescElement.textContent.trim());
        });
        section.querySelectorAll('.mobile-meal-card .mobile-meal-description').forEach(card => {
          const strongDesc = card.querySelector('.meal-name-text');
          if (strongDesc) meals.add(strongDesc.textContent.trim());
        });
      }
    });
    return Array.from(meals);
  }

  function getSelectedRecommender() {
    if (!recommendationSelect) {
      return '';
    }
    if (recommendationSelect.value === '__custom__') {
      return recommendationCustomInput ? recommendationCustomInput.value.trim() : '';
    }
    return recommendationSelect.value;
  }

  document.querySelectorAll('.recommendation-recommender-item').forEach(item => {
    item.addEventListener('click', function () {
      setRecommendationRecommender(item.dataset.value || '');
    });
  });

  document.querySelectorAll('.recommendation-trigger').forEach(trigger => {
    trigger.addEventListener('click', function () {
      recommendationTrigger = trigger;
      openRecommendationPopup(trigger.dataset.mensa || '');
    });
  });

  if (requestRecommendationButton) {
    requestRecommendationButton.addEventListener('click', function () {
      const recommender = getSelectedRecommender();
      const meals = getMealsFromMensaSection(currentRecommendationMensa);
      const profile = recommenderProfiles[recommender];

      if (!recommender) {
        setRecommendationResult(`<p class="text-danger mb-0">${uiText.recommendation_missing_person}</p>`, true);
        return;
      }
      if (meals.length === 0) {
        setRecommendationResult(`<p class="text-danger mb-0">${uiText.recommendation_no_meals}</p>`, true);
        return;
      }

      setRecommendationBackground(profile ? profile.backgroundUrl : '');
      setRecommendationResult(`<p class="mb-0"><i class="fas fa-spinner fa-spin" aria-hidden="true"></i> ${uiText.recommendation_loading}</p>`);
      requestRecommendationButton.disabled = true;
      recommendationRequest?.abort();
      const controller = new AbortController();
      recommendationRequest = controller;

      fetch('/api/get_recommendation', {
        method: 'POST',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          meals: meals,
          mensa: currentRecommendationMensa,
          recommender: recommender,
          lang: currentLanguage
        })
      })
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => { throw new Error(err.error || `HTTP error ${response.status}`); });
        }
        return response.json();
      })
      .then(data => {
        if (recommendationRequest !== controller) return;
        if (data.recommendation) {
          setRecommendationResult(`<div class="recommendation-text">${data.recommendation}</div>`);
        } else {
          throw new Error(data.error || uiText.recommendation_unknown_error);
        }
      })
      .catch(error => {
        if (error.name === 'AbortError' || recommendationRequest !== controller) return;
        console.error('Error asking for recommendation:', error);
        const errorTemplate = uiText.recommendation_failed || 'Die Empfehlung konnte nicht erstellt werden: {error}';
        setRecommendationResult(`<p class="text-danger mb-0">${escapeHtml(errorTemplate.replace('{error}', error.message))}</p>`, true);
      })
      .finally(() => {
        if (recommendationRequest === controller) {
          requestRecommendationButton.disabled = false;
          if (document.activeElement === document.body) requestRecommendationButton.focus();
        }
      });
    });
  }

  new bootstrap.Tooltip(document.body, { selector: '[data-bs-toggle="tooltip"]', container: 'body' });
  let activePopover = null;
  document.querySelectorAll('.nutrient-info-trigger').forEach(trigger => {
    const popover = new bootstrap.Popover(trigger, { container: 'body' });
    trigger.addEventListener('show.bs.popover', () => {
      if (activePopover && activePopover !== popover) activePopover.hide();
      activePopover = popover;
      trigger.setAttribute('aria-expanded', 'true');
    });
    trigger.addEventListener('hide.bs.popover', () => trigger.setAttribute('aria-expanded', 'false'));
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') activePopover?.hide();
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.nutrient-info-trigger, .popover')) activePopover?.hide();
  });

  const mensaSelectForArrows = document.getElementById('mensa');
  const datePickerInputForArrows = document.getElementById('date');

  function adjacentMenuDate(direction) {
    const selected = datePickerInputForArrows.value.split('.').reverse().join('');
    const dates = direction < 0 ? [...availableMenuDates].reverse() : availableMenuDates;
    return dates.find(value => {
      const comparable = value.split('.').reverse().join('');
      return direction < 0 ? comparable < selected : comparable > selected;
    });
  }

  document.querySelectorAll('.date-nav-arrow').forEach(button => {
    button.addEventListener('click', function(event) {
      event.preventDefault();
      if (this.disabled) {
        return;
      }
      if (!datePickerInputForArrows || !mensaSelectForArrows) {
        console.error("Date input or Mensa select not found for arrow navigation.");
        return;
      }
      const direction = this.dataset.direction === 'prev' ? -1 : 1;
      const currentSelectedMensa = mensaSelectForArrows.value;
      const currentSelectedDate = datePickerInputForArrows.value;
      const newDate = adjacentMenuDate(direction);
      if (newDate && newDate !== currentSelectedDate) {
        const params = new URLSearchParams(window.location.search);
        params.set('date', newDate);
        params.set('mensa', currentSelectedMensa);
        applyLanguageParam(params);
        window.location.href = `${window.location.pathname}?${params.toString()}`;
      }
    });
  });

  function updateMensaTitleArrowStates() {
    if (!datePickerInputForArrows) return;
    const onFirst = !adjacentMenuDate(-1);
    const onLast = !adjacentMenuDate(1);

    document.querySelectorAll('.date-nav-arrow[data-direction="prev"]').forEach(btn => {
      btn.disabled = onFirst;
      btn.setAttribute('aria-disabled', onFirst ? 'true' : 'false');
    });
    document.querySelectorAll('.date-nav-arrow[data-direction="next"]').forEach(btn => {
      btn.disabled = onLast;
      btn.setAttribute('aria-disabled', onLast ? 'true' : 'false');
    });
  }

  updateMensaTitleArrowStates();

});
