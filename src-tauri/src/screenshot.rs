use image::DynamicImage;
use xcap::Monitor;

fn get_primary_monitor() -> Result<Monitor, Box<dyn std::error::Error>> {
    let monitors = Monitor::all()?;
    let monitor = monitors
        .into_iter()
        .find(|m| m.is_primary().unwrap_or(false))
        // 注意：or_else 中需要重新调用 Monitor::all()，因为 monitors 已被 into_iter() 消耗
        .or_else(|| Monitor::all().ok()?.into_iter().next())
        .ok_or("No monitor found")?;
    Ok(monitor)
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
    let mut buf = std::io::Cursor::new(Vec::new());
    image.write_to(&mut buf, image::ImageFormat::Png)?;
    Ok(buf.into_inner())
}
