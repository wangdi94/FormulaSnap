import '@testing-library/jest-dom';

// Default test locale to zh-CN so i18n tests match the original Chinese UI
Object.defineProperty(navigator, 'language', {
  value: 'zh-CN',
  configurable: true,
});
