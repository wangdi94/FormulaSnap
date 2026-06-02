fn main() {
    let attributes = tauri_build::Attributes::new();

    // Disable tauri-build's default manifest embedding (which only targets bins, not tests)
    // and embed our manifest manually so it applies to test binaries too.
    #[cfg(windows)]
    let attributes = {
        add_manifest();
        attributes.windows_attributes(tauri_build::WindowsAttributes::new_without_app_manifest())
    };

    tauri_build::try_build(attributes).expect("failed to run tauri build");
}

#[cfg(windows)]
fn add_manifest() {
    static WINDOWS_MANIFEST_FILE: &str = "windows-app-manifest.xml";

    let manifest = std::env::current_dir()
        .unwrap_or_else(|e| panic!("获取当前目录失败: {e:?}"))
        .join(WINDOWS_MANIFEST_FILE);

    println!("cargo:rerun-if-changed={}", manifest.display());
    // Embed the Windows application manifest into all binaries (including test binaries).
    println!("cargo:rustc-link-arg=/MANIFEST:EMBED");
    println!(
        "cargo:rustc-link-arg=/MANIFESTINPUT:{}",
        manifest
            .to_str()
            .unwrap_or_else(|| panic!("manifest路径包含非UTF-8字符: {manifest:?}"))
    );
}
