# 学习记录

## Task 4: Tauri 签名密钥生成

### 公钥内容（用于 tauri.conf.json 配置）
```
dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDY1OTFCNkUzRTkzNkEwOUEKUldTYW9EYnA0N2FSWmFJb3lrK01IVXJCL0RMVU1rUXZlYUZMWFg1blZrdlQ1ZGJHSUdkaWtFUDcK
```

### 私钥文件路径
```
~/.tauri/openmathpix.key
```

### 注意事项
1. 使用 `CI=true` 环境变量跳过密码交互
2. Tauri CLI 2.11.2 使用 minisign 格式（不是 age 格式）
3. 公钥自动保存到 `~/.tauri/openmathpix.key.pub`
4. 私钥不能提交到版本控制
5. 私钥不能硬编码到代码中

## Task 5: Tauri Updater 配置

### 配置内容
1. `bundle.createUpdaterArtifacts: true` - 启用更新产物生成
2. `plugins.updater` 配置：
   - `pubkey`: minisign 公钥（Task 4 生成）
   - `endpoints`: GitHub Releases JSON URL
   - `windows.installMode: "passive"` - 静默安装，仅显示进度

### 注意事项
1. Updater endpoint 使用 `latest.json` 格式，GitHub Actions 需生成此文件
2. 公钥必须与签名使用的私钥匹配
3. Tauri v2 updater 配置在顶层 `plugins` 对象中
