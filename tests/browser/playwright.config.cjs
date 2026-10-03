const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: '.',
  timeout: 30000,
  workers: 1,
  retries: 0,
  maxFailures: 8,
  reporter: [['list']],
  use: { baseURL: 'http://caner-preview:30823', trace: 'retain-on-failure' },
  projects: ['chromium', 'firefox', 'webkit'].map(browserName => ({ name: browserName, use: { browserName } })),
});
