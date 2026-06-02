use image::DynamicImage;
use xcap::Monitor;

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
        monitors.into_iter().next().ok_or_else(|| "No monitor found".into())
    }
}

/// Capture the entire primary monitor screen.
/// Returns PNG-encoded bytes.
pub fn capture_screen() -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let monitor = get_primary_monitor()?;

    let image = monitor.capture_image()?;
    let dynamic = DynamicImage::ImageRgba8(image);
    encode_png(&dynamic)
}

/// Capture a specific rectangular region from the primary monitor.
/// (x, y) is the top-left corner; width/height define the region size.
/// Returns PNG-encoded bytes.
pub fn capture_region(
    x: u32,
    y: u32,
    width: u32,
    height: u32,
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
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
