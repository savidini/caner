FROM mcr.microsoft.com/playwright:v1.61.1-noble
WORKDIR /checks
RUN npm install --no-save --no-audit --no-fund @playwright/test@1.61.1 @axe-core/playwright@4.11.1
COPY tests/browser/ ./
CMD ["npx", "playwright", "test"]
