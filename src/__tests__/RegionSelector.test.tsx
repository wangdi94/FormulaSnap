import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import RegionSelector from '../components/RegionSelector';

// 1x1 transparent PNG for Image to load
const FAKE_BASE64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQABNjN9GQAAAABJREFTCjkJAAA=';

describe('RegionSelector', () => {
  let addSpy: ReturnType<typeof vi.spyOn>;
  let removeSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    addSpy = vi.spyOn(window, 'addEventListener');
    removeSpy = vi.spyOn(window, 'removeEventListener');

    // jsdom doesn't implement canvas getContext; stub it
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
      drawImage: vi.fn(),
      clearRect: vi.fn(),
      fillRect: vi.fn(),
      strokeRect: vi.fn(),
      setLineDash: vi.fn(),
      fillStyle: '',
      strokeStyle: '',
      lineWidth: 0,
    })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
  });

  afterEach(() => {
    addSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it('registers mousedown / keydown / resize on mount', () => {
    render(<RegionSelector screenshotBase64={FAKE_BASE64} onSelected={vi.fn()} onCancel={vi.fn()} />);
    const addedTypes = addSpy.mock.calls.map((c: unknown[]) => c[0]);
    expect(addedTypes).toContain('mousedown');
    expect(addedTypes).toContain('keydown');
    expect(addedTypes).toContain('resize');
  });

  it('cleans up mousedown / keydown / resize on unmount', () => {
    const { unmount } = render(<RegionSelector screenshotBase64={FAKE_BASE64} onSelected={vi.fn()} onCancel={vi.fn()} />);
    unmount();
    const removedTypes = removeSpy.mock.calls.map((c: unknown[]) => c[0]);
    expect(removedTypes).toContain('mousedown');
    expect(removedTypes).toContain('keydown');
    expect(removedTypes).toContain('resize');
  });

  it('test_region_selector_cleanup_on_unmount — removes dynamic mousemove/mouseup when unmounted during drag', () => {
    const { unmount } = render(
      <RegionSelector screenshotBase64={FAKE_BASE64} onSelected={vi.fn()} onCancel={vi.fn()} />,
    );

    // Clear pre-existing calls from mount
    addSpy.mockClear();
    removeSpy.mockClear();

    // Start a drag by dispatching mousedown
    fireEvent.mouseDown(window, { clientX: 100, clientY: 100 });

    // At this point handleMouseDown should have added mousemove + mouseup
    const addedAfterMousedown = addSpy.mock.calls.map((c: unknown[]) => c[0]);
    expect(addedAfterMousedown).toContain('mousemove');
    expect(addedAfterMousedown).toContain('mouseup');

    // Unmount WITHOUT firing mouseup — this is the leak scenario
    unmount();

    // The cleanup should remove the dynamic mousemove and mouseup listeners
    const removedAfterUnmount = removeSpy.mock.calls.map((c: unknown[]) => c[0]);
    expect(removedAfterUnmount).toContain('mousemove');
    expect(removedAfterUnmount).toContain('mouseup');
  });
});
