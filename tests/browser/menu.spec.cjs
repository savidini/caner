const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.route('**/api/meal_image?**', route => route.fulfill({ json: { found: false } }));
});

async function openMenu(page, language = 'en', expert = false) {
  await page.goto(`/?lang=${language}${expert ? '&expert=true' : ''}`);
  await expect(page.getByRole('heading', { name: 'Mensa Garbsen', exact: true })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

async function checkAccessibility(page, testInfo) {
  const result = await new AxeBuilder({ page }).analyze();
  const violations = result.violations.filter(issue => ['serious', 'critical'].includes(issue.impact));
  await testInfo.attach('accessibility', { body: JSON.stringify(violations, null, 2), contentType: 'application/json' });
  expect(violations.map(issue => ({ id: issue.id, targets: issue.nodes.slice(0, 3).map(node => node.target) }))).toEqual([]);
}

for (const [name, width, theme, language = 'en', expert = false] of [
  ['desktop', 1440, 'light'], ['mobile', 390, 'light'], ['narrow', 320, 'light'],
  ['tablet', 820, 'light'], ['dark', 390, 'dark'],
  ['expert-desktop', 1440, 'dark', 'de', true], ['expert-mobile', 320, 'light', 'de', true],
]) {
  test(`${name}: layout, accessibility and startup request budget`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ colorScheme: theme });
    const requests = [];
    const errors = [];
    page.on('request', request => requests.push(new URL(request.url()).pathname));
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      window.menuLayoutShift = 0;
      if (PerformanceObserver.supportedEntryTypes.includes('layout-shift')) {
        new PerformanceObserver(list => list.getEntries().forEach(entry => {
          if (!entry.hadRecentInput) window.menuLayoutShift += entry.value;
        })).observe({ type: 'layout-shift', buffered: true });
      }
    });
    await openMenu(page, language, expert);
    await expect(page.getByRole('combobox', { name: language === 'de' ? 'Datum auswählen' : 'Select date' })).toHaveCount(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(requests.filter(path => /^\/api\/(votes|comments)\//.test(path))).toHaveLength(0);
    expect(requests.filter(path => path === '/api/meal_image').length).toBeLessThan(12);
    expect(await page.evaluate(() => window.menuLayoutShift)).toBeLessThan(0.05);
    expect(errors).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: false });
    await checkAccessibility(page, testInfo);
    await testInfo.attach('startup-requests', { body: JSON.stringify(requests), contentType: 'application/json' });
  });
}

test('mobile controls, saved price, instant expert mode and navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openMenu(page);
  await page.getByRole('button', { name: 'Guests', exact: true }).click();
  await expect(page).toHaveURL(/price=guest/);
  const firstCard = page.locator('.mobile-meal-card').first();
  await expect(firstCard.locator('.mobile-price-info-row:visible .price')).toHaveText('5,60 €');
  const navigations = [];
  page.on('request', req => { if (req.isNavigationRequest()) navigations.push(req.url()); });
  await page.getByRole('button', { name: 'Expert Mode', exact: true }).click();
  await expect(firstCard.locator('.mobile-expert-info-row')).toBeVisible();
  await expect(page).toHaveURL(/expert=true/);
  expect(navigations).toHaveLength(0);
  const dateSelect = page.getByRole('combobox', { name: 'Select date' });
  const original = await dateSelect.inputValue();
  await page.getByRole('button', { name: 'Next day', exact: true }).click();
  await expect(dateSelect).not.toHaveValue(original);
  await expect(page.getByRole('button', { name: 'Next day', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Guests', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.goBack();
  await expect(dateSelect).toHaveValue(original);
  await page.getByRole('combobox', { name: 'Choose canteen' }).selectOption('Hauptmensa');
  await expect(page.getByRole('heading', { name: 'Hauptmensa', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Deutsch', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'de');
  await expect(page.getByRole('combobox', { name: 'Datum auswählen' })).toBeVisible();
});

test('votes recover after failure, serialize clicks and update both layouts', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openMenu(page);
  const card = page.locator('.mobile-meal-card').first();
  const button = card.getByRole('button', { name: 'Upvote', exact: true });
  await page.route('**/api/vote', route => route.fulfill({ status: 503, json: { error: 'offline' } }), { times: 1 });
  await button.click();
  await expect(card.getByRole('status')).toContainText('Vote not saved');
  let submissions = 0;
  await page.route('**/api/vote', async route => {
    submissions++;
    await new Promise(resolve => setTimeout(resolve, 100));
    await route.continue();
  });
  await button.evaluate(el => { el.click(); el.click(); });
  await expect(button).toHaveAttribute('aria-pressed', 'true');
  expect(submissions).toBe(1);
  const mealId = await card.locator('.vote-controls').getAttribute('data-meal-id');
  const counts = await page.locator(`.vote-controls[data-meal-id="${mealId}"] .upvote-count`).allTextContents();
  expect(counts[0]).toBe(counts[1]);
  await page.reload();
  await expect(button).toHaveAttribute('aria-pressed', 'true');
});

test('comments show retry, preserve drafts and restore focus', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openMenu(page);
  const trigger = page.locator('.mobile-meal-card').first().getByRole('button', { name: 'Show comments' });
  await page.route('**/api/comments/*?*', route => route.fulfill({ status: 503, json: {} }), { times: 1 });
  await trigger.click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('status')).toContainText('Comments could not be loaded');
  await dialog.getByRole('button', { name: 'Try again' }).click();
  await expect(dialog.locator('.comment-item').first()).toBeVisible();
  const draft = '<img src=x onerror=alert(1)> My lunch';
  await dialog.getByLabel('Name (optional)').fill('Menu tester');
  await dialog.getByLabel('Comment (optional)').fill(draft);
  await page.route('**/api/comments', route => route.fulfill({ status: 503, json: {} }), { times: 1 });
  await dialog.getByRole('button', { name: 'Comment', exact: true }).click();
  await expect(dialog.getByRole('status')).toContainText('Comment not saved');
  await expect(dialog.getByLabel('Comment (optional)')).toHaveValue(draft);
  await dialog.getByRole('button', { name: 'Comment', exact: true }).click();
  await expect(dialog.locator('.comment-text').first()).toHaveText(draft);
  await expect(dialog.locator('.comment-text img')).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: 'Comment', exact: true })).toBeFocused();
  await page.screenshot({ path: testInfo.outputPath('comments.png') });
  await checkAccessibility(page, testInfo);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
});

test('image lookups are lazy, bounded and deduplicated after resizing', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let concurrent = 0;
  let maximum = 0;
  const lookups = [];
  await page.route('**/api/meal_image?**', async route => {
    lookups.push(new URL(route.request().url()).searchParams.get('meal_id'));
    maximum = Math.max(maximum, ++concurrent);
    await new Promise(resolve => setTimeout(resolve, 80));
    await route.fulfill({ json: { found: true, thumbnail_url: '/static/img/caner.png', image_url: '/static/img/caner.png' } });
    concurrent--;
  });
  await openMenu(page);
  const image = page.locator('.mobile-meal-card').first().getByRole('button', { name: 'Show meal image' });
  await expect(image).toBeVisible();
  await image.click();
  await expect(page.getByRole('dialog').locator('img')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(image).toBeFocused();
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.locator('.meal-table .meal-image-thumbnail-toggle').first()).toBeVisible();
  expect(maximum).toBeLessThanOrEqual(3);
  expect(lookups.length).toBeLessThan(30);
  expect(new Set(lookups).size).toBe(lookups.length);
});

test('empty menus and denied storage retain working controls', async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => { throw new DOMException('denied', 'SecurityError'); };
    Storage.prototype.setItem = () => { throw new DOMException('denied', 'SecurityError'); };
  });
  await openMenu(page);
  await page.getByRole('button', { name: 'Toggle light and dark mode' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('combobox', { name: 'Choose canteen' }).selectOption('Contine');
  await expect(page.locator('.no-meals-warning')).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Select date' })).toBeVisible();
  await page.getByRole('button', { name: 'Request recommendation for Contine' }).click();
  await expect(page.getByRole('button', { name: 'Get recommendation' })).toBeDisabled();
});

test('keyboard nutrition popover and safe recommendation errors', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openMenu(page);
  const nutrition = page.locator('.mobile-meal-card').first().getByRole('button', { name: 'Nutrition' });
  await nutrition.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.popover')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('.popover')).toHaveCount(0);
  await page.getByRole('button', { name: 'Request recommendation for Mensa Garbsen' }).click();
  await page.route('**/api/get_recommendation', route => route.fulfill({ status: 503, json: { error: '<img src=x onerror=alert(1)>' } }));
  await page.getByRole('button', { name: 'Get recommendation' }).click();
  await expect(page.locator('.recommendation-result')).toContainText('<img src=x onerror=alert(1)>');
  await expect(page.locator('.recommendation-result img')).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
});

test('late comments cannot replace a newly opened meal', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openMenu(page);
  const triggers = page.locator('.mobile-meal-card').getByRole('button', { name: 'Show comments' });
  let release;
  let started;
  const requestStarted = new Promise(resolve => { started = resolve; });
  const delay = new Promise(resolve => { release = resolve; });
  await page.route('**/api/comments/1?**', async route => {
    started();
    await delay;
    await route.fulfill({ json: { comments: [{ rating: 'good', text: 'Stale response', has_text: true }], count: 1 } }).catch(() => {});
  });
  await triggers.nth(0).click();
  await requestStarted;
  await expect(page.getByRole('dialog')).toBeFocused();
  const cancelled = page.waitForEvent('requestfailed', request => new URL(request.url()).pathname === '/api/comments/1');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
  await triggers.nth(1).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading')).toContainText('Pasta');
  await expect(dialog.locator('.comment-item').first()).toBeVisible();
  release();
  await cancelled;
  await expect(dialog).not.toContainText('Stale response');
});

test('closing a recommendation cancels it and preserves the next dialog', async ({ page }) => {
  await openMenu(page);
  let release;
  let started;
  const requestStarted = new Promise(resolve => { started = resolve; });
  const delay = new Promise(resolve => { release = resolve; });
  await page.route('**/api/get_recommendation', async route => {
    started();
    await delay;
    await route.fulfill({ json: { recommendation: 'Stale recommendation' } }).catch(() => {});
  });
  const trigger = page.getByRole('button', { name: 'Request recommendation for Mensa Garbsen' });
  await trigger.click();
  await page.getByRole('button', { name: 'Get recommendation' }).click();
  await requestStarted;
  // Close via its control while the submit button is pending.
  await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
  await trigger.click();
  release();
  await expect(page.locator('.recommendation-result')).toContainText('Choose a person');
  await expect(page.locator('.recommendation-result')).not.toContainText('Stale recommendation');
  await expect(page.getByRole('button', { name: 'Get recommendation' })).toBeEnabled();
});
