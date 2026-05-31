/**
 * 应用自动更新模块
 *
 * 封装 Tauri updater 插件，提供更新检查和安装功能。
 */

import { check } from '@tauri-apps/plugin-updater';
import { relaunch } from '@tauri-apps/plugin-process';

// ---------------------------------------------------------------------------
// 类型定义
// ---------------------------------------------------------------------------

/** 更新信息 */
export interface UpdateInfo {
  version: string;
  date?: string;
  body?: string;
  currentVersion: string;
}

/** 下载进度事件 */
export type ProgressEvent =
  | { type: 'started'; contentLength?: number }
  | { type: 'progress'; downloaded: number; contentLength?: number }
  | { type: 'finished' };

/** 进度回调函数 */
export type ProgressCallback = (event: ProgressEvent) => void;

// ---------------------------------------------------------------------------
// 公开 API
// ---------------------------------------------------------------------------

/**
 * 检查是否有可用更新
 *
 * @returns 更新信息，如果没有更新则返回 null
 */
export async function checkForUpdates(): Promise<UpdateInfo | null> {
  try {
    const update = await check();

    if (!update) {
      return null;
    }

    return {
      version: update.version,
      date: update.date,
      body: update.body,
      currentVersion: update.currentVersion,
    };
  } catch (err) {
    console.warn('Failed to check for updates:', err);
    return null;
  }
}

/**
 * 下载并安装更新，完成后重启应用
 *
 * @param onProgress - 下载进度回调（可选）
 */
export async function downloadAndInstall(
  onProgress?: ProgressCallback,
): Promise<void> {
  const update = await check();

  if (!update) {
    throw new Error('没有可用的更新');
  }

  let downloadedBytes = 0;

  await update.downloadAndInstall((event) => {
    switch (event.event) {
      case 'Started':
        onProgress?.({
          type: 'started',
          contentLength: event.data.contentLength,
        });
        break;
      case 'Progress':
        downloadedBytes += event.data.chunkLength;
        onProgress?.({
          type: 'progress',
          downloaded: downloadedBytes,
        });
        break;
      case 'Finished':
        onProgress?.({ type: 'finished' });
        break;
    }
  });

  // 安装完成后重启应用
  await relaunch();
}
