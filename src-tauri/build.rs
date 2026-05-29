fn main() {
    tauri_build::build();

    #[cfg(windows)]
    {
        use embed_manifest::{embed_manifest, new_manifest};
        embed_manifest(new_manifest("FormulaSnap"))
            .expect("unable to embed windows manifest for tests");
    }
}
