use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tracing::{debug, info};

use crate::types::KeyInfo;

/// API key manager with environment variable and file-based storage.
///
/// Key priority: environment variable (`{SERVICE}_{KEY_NAME}`) > file (`~/.formulasnap/keys.json`).
/// Thread-safe via internal `Mutex`.
pub struct KeyManager {
    /// In-memory key store: service -> key_name -> value
    keys: Mutex<HashMap<String, HashMap<String, String>>>,
    /// Path to the keys.json file
    file_path: PathBuf,
}

/// JSON file format for key storage.
#[derive(Debug, Serialize, Deserialize, Default)]
struct KeysFile(HashMap<String, HashMap<String, String>>);

impl KeyManager {
    /// Create a new `KeyManager`, loading existing keys from `~/.formulasnap/keys.json`.
    pub fn new() -> Self {
        let file_path = Self::keys_file_path();
        let keys = Self::load_from_file(&file_path);

        info!(
            "KeyManager 初始化完成，加载了 {} 个服务的密钥",
            keys.len()
        );

        Self {
            keys: Mutex::new(keys),
            file_path,
        }
    }

    /// Get the path to `~/.formulasnap/keys.json`.
    fn keys_file_path() -> PathBuf {
        let home = dirs::home_dir().expect("无法获取用户主目录");
        home.join(".formulasnap").join("keys.json")
    }

    /// Load keys from the JSON file, returning empty map on any error.
    fn load_from_file(path: &PathBuf) -> HashMap<String, HashMap<String, String>> {
        if !path.exists() {
            debug!("密钥文件不存在: {:?}", path);
            return HashMap::new();
        }

        match fs::read_to_string(path) {
            Ok(content) => match serde_json::from_str::<KeysFile>(&content) {
                Ok(keys_file) => {
                    debug!("从文件加载了 {} 个服务的密钥", keys_file.0.len());
                    keys_file.0
                }
                Err(e) => {
                    tracing::warn!("解析密钥文件失败: {}, 返回空密钥", e);
                    HashMap::new()
                }
            },
            Err(e) => {
                tracing::warn!("读取密钥文件失败: {}, 返回空密钥", e);
                HashMap::new()
            }
        }
    }

    /// Save keys to the JSON file with 0o600 permissions.
    fn save_to_file(&self) -> Result<(), String> {
        let keys = self.keys.lock().map_err(|e| format!("获取锁失败: {}", e))?;
        let keys_file = KeysFile(keys.clone());

        // Ensure parent directory exists
        if let Some(parent) = self.file_path.parent() {
            fs::create_dir_all(parent)
                .map_err(|e| format!("创建目录 {:?} 失败: {}", parent, e))?;
        }

        let json = serde_json::to_string_pretty(&keys_file)
            .map_err(|e| format!("序列化密钥失败: {}", e))?;

        fs::write(&self.file_path, json)
            .map_err(|e| format!("写入密钥文件失败: {}", e))?;

        // Set file permissions to 0o600 (owner read/write only)
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let perms = fs::Permissions::from_mode(0o600);
            fs::set_permissions(&self.file_path, perms)
                .map_err(|e| format!("设置文件权限失败: {}", e))?;
        }

        debug!("密钥已保存到文件: {:?}", self.file_path);
        Ok(())
    }

    /// Get the environment variable name for a service/key combination.
    /// Format: `{SERVICE}_{KEY_NAME}` (e.g., `OPENAI_API_KEY`).
    fn env_var_name(service: &str, key_name: &str) -> String {
        format!(
            "{}_{}",
            service.to_uppercase(),
            key_name.to_uppercase()
        )
    }

    /// Retrieve a key, checking environment variable first, then file storage.
    pub fn get_key(&self, service: &str, key_name: &str) -> Option<String> {
        // 1. Check environment variable
        let env_name = Self::env_var_name(service, key_name);
        if let Ok(value) = std::env::var(&env_name) {
            if !value.is_empty() {
                debug!("从环境变量 {} 获取到密钥", env_name);
                return Some(value);
            }
        }

        // 2. Check file storage
        let keys = self.keys.lock().ok()?;
        keys.get(service)?.get(key_name).cloned()
    }

    /// Store a key in file storage and save to disk.
    pub fn set_key(&self, service: &str, key_name: &str, value: &str) {
        let mut keys = match self.keys.lock() {
            Ok(k) => k,
            Err(e) => {
                tracing::error!("获取锁失败: {}", e);
                return;
            }
        };

        keys.entry(service.to_string())
            .or_default()
            .insert(key_name.to_string(), value.to_string());

        drop(keys);

        if let Err(e) = self.save_to_file() {
            tracing::error!("保存密钥失败: {}", e);
        }
    }

    /// Delete a key from file storage and save to disk.
    pub fn delete_key(&self, service: &str, key_name: &str) {
        let mut keys = match self.keys.lock() {
            Ok(k) => k,
            Err(e) => {
                tracing::error!("获取锁失败: {}", e);
                return;
            }
        };

        if let Some(service_keys) = keys.get_mut(service) {
            service_keys.remove(key_name);
            if service_keys.is_empty() {
                keys.remove(service);
            }
        }

        drop(keys);

        if let Err(e) = self.save_to_file() {
            tracing::error!("保存密钥失败: {}", e);
        }
    }

    /// List all stored keys with their configuration status.
    pub fn list_keys(&self) -> Vec<KeyInfo> {
        let keys = match self.keys.lock() {
            Ok(k) => k,
            Err(e) => {
                tracing::error!("获取锁失败: {}", e);
                return Vec::new();
            }
        };

        let mut result = Vec::new();
        for (service, service_keys) in keys.iter() {
            for (key_name, _) in service_keys {
                result.push(KeyInfo {
                    backend: format!("{}:{}", service, key_name),
                    configured: true,
                });
            }
        }

        result
    }
}

impl Default for KeyManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;
    use tempfile::TempDir;

    /// Helper: create a KeyManager with a custom file path for testing.
    fn create_test_key_manager(temp_dir: &TempDir) -> KeyManager {
        let file_path = temp_dir.path().join("keys.json");
        let keys = HashMap::new();

        KeyManager {
            keys: Mutex::new(keys),
            file_path,
        }
    }

    #[test]
    fn test_env_var_key_priority() {
        // Set a test environment variable
        let test_key = "TEST_SVC_ENV_PRIORITY";
        env::set_var(test_key, "env_value_123");

        let temp_dir = TempDir::new().unwrap();
        let km = create_test_key_manager(&temp_dir);

        // Also store a file key with same name
        km.set_key("test_svc", "env_priority", "file_value");

        // get_key should return env var (higher priority)
        let result = km.get_key("test_svc", "env_priority");
        assert_eq!(result, Some("env_value_123".to_string()));

        // Cleanup
        env::remove_var(test_key);
    }

    #[test]
    fn test_file_key_storage() {
        let temp_dir = TempDir::new().unwrap();
        let km = create_test_key_manager(&temp_dir);

        // Store a key
        km.set_key("openai", "api_key", "sk-abc123");

        // Retrieve it
        let result = km.get_key("openai", "api_key");
        assert_eq!(result, Some("sk-abc123".to_string()));

        // Delete it
        km.delete_key("openai", "api_key");
        let result = km.get_key("openai", "api_key");
        assert_eq!(result, None);
    }

    #[test]
    fn test_env_key_without_file() {
        // Set a test environment variable
        let test_key = "MATHPIX_ENV_ONLY";
        env::set_var(test_key, "mathpix_secret");

        let temp_dir = TempDir::new().unwrap();
        let km = create_test_key_manager(&temp_dir);

        // get_key should find it from env
        let result = km.get_key("mathpix", "env_only");
        assert_eq!(result, Some("mathpix_secret".to_string()));

        // Cleanup
        env::remove_var(test_key);
    }

    #[test]
    fn test_list_keys() {
        let temp_dir = TempDir::new().unwrap();
        let km = create_test_key_manager(&temp_dir);

        km.set_key("openai", "api_key", "sk-abc");
        km.set_key("mathpix", "app_id", "app-123");

        let keys = km.list_keys();
        assert_eq!(keys.len(), 2);
    }

    #[test]
    fn test_file_persistence() {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("keys.json");

        // Write keys with first instance
        {
            let km = KeyManager {
                keys: Mutex::new(HashMap::new()),
                file_path: file_path.clone(),
            };
            km.set_key("gemini", "api_key", "gemini-secret");
        }

        // Read keys with second instance (simulates app restart)
        {
            let km = KeyManager {
                keys: Mutex::new(KeyManager::load_from_file(&file_path)),
                file_path,
            };
            let result = km.get_key("gemini", "api_key");
            assert_eq!(result, Some("gemini-secret".to_string()));
        }
    }
}
