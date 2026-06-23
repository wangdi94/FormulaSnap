import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Section } from '../components/settings/Section';

describe('Section', () => {
  it('渲染标题', () => {
    render(<Section title="测试标题" description="描述"><p>内容</p></Section>);
    expect(screen.getByText('测试标题')).toBeInTheDocument();
  });

  it('渲染描述文本', () => {
    render(<Section title="标题" description="这是描述"><p>内容</p></Section>);
    expect(screen.getByText('这是描述')).toBeInTheDocument();
  });

  it('渲染 children', () => {
    render(<Section title="标题" description="描述"><p>子元素内容</p></Section>);
    expect(screen.getByText('子元素内容')).toBeInTheDocument();
  });

  it('传入 icon 时渲染图标', () => {
    render(<Section title="标题" description="描述" icon="⚡"><p>内容</p></Section>);
    expect(screen.getByText('⚡')).toBeInTheDocument();
  });

  it('不传 icon 时不渲染图标', () => {
    render(<Section title="标题" description="描述"><p>内容</p></Section>);
    const heading = screen.getByText('标题');
    expect(heading.querySelector('span')).toBeNull();
  });
});
