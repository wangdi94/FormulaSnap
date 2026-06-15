use std::sync::mpsc;
use std::thread;
use std::time::Duration;

use image::DynamicImage;
use xcap::Monitor;

const CAPTURE_TIMEOUT: Duration = Duration::from_secs(10);

fn get_primary_monitor() -> Result<Monitor, Box<dyn std::error::Error>> {
    let mut monitors = Monitor::all()?;
    // 先找主显示器，没找到则取第一个（只调用一次 Monitor::all()）
    if let Some(idx) = monitors.iter().position(|m| {
        m.is_primary().unwrap_or_else(|e| {
            log::warn!("检查显示器主屏状态失败，视为非主屏: {}", e);
            false
        })
    }) {
        Ok(monitors.swap_remove(idx))
    } else {
        monitors
            .into_iter()
            .next()
            .ok_or_else(|| "No monitor found".into())
    }
}

fn encode_png(image: &DynamicImage) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let rgba = image.to_rgba8();
    let width = rgba.width();
    let height = rgba.height();
    let data = rgba.into_raw();

    let mut buf = std::io::Cursor::new(Vec::new());
    {
        let mut encoder = png::Encoder::new(&mut buf, width, height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        encoder.set_compression(png::Compression::Fast);
        let mut writer = encoder.write_header()?;
        writer.write_image_data(&data)?;
    } // writer & encoder dropped here, releasing the borrow on buf
    Ok(buf.into_inner())
}

/// Capture the entire primary monitor screen.
/// Returns PNG-encoded bytes.
/// Uses a 10-second timeout to prevent indefinite hangs from xcap platform APIs.
pub fn capture_screen() -> Result<Vec<u8>, String> {
    let (tx, rx) = mpsc::channel();

    // 注意：超时后此线程会被孤立（orphaned）。这是可接受的权衡：
    // xcap 平台 API（Windows: DXGI, macOS: AVFoundation, Linux: X11/PipeWire）
    // 在显示器不可用或边缘情况下可能无限挂起，孤立线程最终会被操作系统回收。
    thread::spawn(move || {
        let result = (|| -> Result<Vec<u8>, Box<dyn std::error::Error>> {
            let monitor = get_primary_monitor()?;
            let image = monitor.capture_image()?;
            let dynamic = DynamicImage::ImageRgba8(image);
            encode_png(&dynamic)
        })();
        let _ = tx.send(result.map_err(|e| e.to_string()));
    });

    match rx.recv_timeout(CAPTURE_TIMEOUT) {
        Ok(result) => result,
        Err(mpsc::RecvTimeoutError::Timeout) => {
            log::error!("截图全屏超时（{}秒）", CAPTURE_TIMEOUT.as_secs());
            Err("Screenshot capture timed out".to_string())
        }
        Err(mpsc::RecvTimeoutError::Disconnected) => {
            Err("Screenshot capture thread panicked".to_string())
        }
    }
}

/// Capture a specific rectangular region from the primary monitor.
/// (x, y) is the top-left corner; width/height define the region size.
/// Returns PNG-encoded bytes.
/// Uses a 10-second timeout to prevent indefinite hangs from xcap platform APIs.
pub fn capture_region(x: u32, y: u32, width: u32, height: u32) -> Result<Vec<u8>, String> {
    let (tx, rx) = mpsc::channel();

    // 注意：超时后此线程会被孤立（orphaned）。这是可接受的权衡：
    // xcap 平台 API（Windows: DXGI, macOS: AVFoundation, Linux: X11/PipeWire）
    // 在显示器不可用或边缘情况下可能无限挂起，孤立线程最终会被操作系统回收。
    thread::spawn(move || {
        let result = (|| -> Result<Vec<u8>, Box<dyn std::error::Error>> {
            let monitor = get_primary_monitor()?;
            let full_image = monitor.capture_image()?;

            // Clamp region to image bounds
            let img_w = full_image.width();
            let img_h = full_image.height();
            let w = width.min(img_w.saturating_sub(x));
            let h = height.min(img_h.saturating_sub(y));

            let cropped = image::imageops::crop_imm(&full_image, x, y, w, h).to_image();
            let cropped_dynamic = DynamicImage::ImageRgba8(cropped);

            encode_png(&cropped_dynamic)
        })();
        let _ = tx.send(result.map_err(|e| e.to_string()));
    });

    match rx.recv_timeout(CAPTURE_TIMEOUT) {
        Ok(result) => result,
        Err(mpsc::RecvTimeoutError::Timeout) => {
            log::error!(
                "截图区域超时（{}秒）: x={}, y={}, w={}, h={}",
                CAPTURE_TIMEOUT.as_secs(),
                x,
                y,
                width,
                height
            );
            Err("Screenshot capture timed out".to_string())
        }
        Err(mpsc::RecvTimeoutError::Disconnected) => {
            Err("Screenshot capture thread panicked".to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encode_png_roundtrip() {
        let img = DynamicImage::new_rgba8(10, 10);
        let result = encode_png(&img);
        assert!(result.is_ok());
        let bytes = result.unwrap();
        assert!(!bytes.is_empty());
        // PNG signature: first 8 bytes
        assert_eq!(&bytes[..8], b"\x89PNG\r\n\x1a\n");
    }

    #[test]
    fn test_capture_screen_returns_result() {
        // 验证函数签名返回 Result<Vec<u8>, String>
        fn assert_return_type(_f: fn() -> Result<Vec<u8>, String>) {}
        assert_return_type(capture_screen);
    }

    #[test]
    fn test_capture_region_returns_result() {
        fn assert_return_type(_f: fn(u32, u32, u32, u32) -> Result<Vec<u8>, String>) {}
        assert_return_type(capture_region);
    }
}
