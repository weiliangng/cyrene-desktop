/* eslint-disable no-shadow */
import { app, ipcMain, globalShortcut, desktopCapturer, protocol, net } from "electron";
import { join, resolve, relative, isAbsolute } from 'path';
import { pathToFileURL } from 'url';
import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { electronApp, optimizer } from "@electron-toolkit/utils";
import { WindowManager } from "./window-manager";
import { MenuManager } from "./menu-manager";

let windowManager: WindowManager;
let menuManager: MenuManager;
let isQuitting = false;

// Keep this private build and its settings separate from the installed official app.
const localRoot = app.isPackaged ? resolve(process.execPath, '..', '..', '..', '..', '..') : resolve(__dirname, '../../..');
const stateDir = join(localRoot, 'tmp', 'cyrene-desktop-state');
mkdirSync(stateDir, { recursive: true });
app.setPath('userData', stateDir);
app.setAppLogsPath(join(stateDir, 'logs'));
protocol.registerSchemesAsPrivileged([{
  scheme: 'cyrene', privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true },
}]);

let lastLayoutJson = '';
function setupIPC(): void {
  ipcMain.handle('cyrene-visibility', (event, visible) => {
    const window = windowManager.getWindow();
    if (!window || event.sender !== window.webContents || typeof visible !== 'boolean') throw new Error('Invalid visibility request');
    if (visible) window.showInactive(); else window.hide();
    return window.isVisible();
  });
  ipcMain.on('cyrene-control-token', (event) => {
    if (event.sender !== windowManager.getWindow()?.webContents) { event.returnValue = null; return; }
    try { event.returnValue = readFileSync(join(localRoot, 'tmp', 'cyrene-control', 'token'), 'utf8').trim(); }
    catch { event.returnValue = null; }
  });
  const layoutFile = join(stateDir, 'pet-layout.json');
  ipcMain.on('cyrene-read-layout', (event) => {
    try { event.returnValue = JSON.parse(readFileSync(layoutFile, 'utf8')); }
    catch { event.returnValue = null; }
  });
  ipcMain.on('cyrene-save-layout', (event, value) => {
    if (event.sender !== windowManager.getWindow()?.webContents) return;
    const matrix = value?.matrix;
    if (value?.version !== 1 || !Array.isArray(matrix) || matrix.length !== 16
      || !matrix.every(Number.isFinite) || matrix[0] <= 0 || matrix[0] > 20
      || matrix[5] <= 0 || matrix[5] > 20 || Math.abs(matrix[12]) > 100
      || Math.abs(matrix[13]) > 100 || matrix[15] !== 1) return;
    const json = JSON.stringify({ version: 1, matrix });
    if (json !== lastLayoutJson) {
      try {
        writeFileSync(layoutFile, json, 'utf8');
        lastLayoutJson = json;
      } catch (error) { console.warn('Could not save pet layout:', error); }
    }
  });
  ipcMain.handle("get-platform", () => process.platform);

  ipcMain.on("set-ignore-mouse-events", (_event, ignore: boolean) => {
    const window = windowManager.getWindow();
    if (window) {
      windowManager.setIgnoreMouseEvents(ignore);
    }
  });

  ipcMain.on("get-current-mode", (event) => {
    event.returnValue = windowManager.getCurrentMode();
  });

  ipcMain.on("pre-mode-changed", (_event, newMode) => {
    if (newMode === 'window' || newMode === 'pet') {
      menuManager.setMode(newMode);
    }
  });

  ipcMain.on("window-minimize", () => {
    windowManager.getWindow()?.minimize();
  });

  ipcMain.on("window-maximize", () => {
    const window = windowManager.getWindow();
    if (window) {
      windowManager.maximizeWindow();
    }
  });

  ipcMain.on("window-close", () => {
    const window = windowManager.getWindow();
    if (window) {
      if (process.platform === "darwin") {
        window.hide();
      } else {
        window.close();
      }
    }
  });

  ipcMain.on(
    "update-component-hover",
    (_event, componentId: string, isHovering: boolean) => {
      windowManager.updateComponentHover(componentId, isHovering);
    },
  );

  ipcMain.handle("get-config-files", () => {
    const configFiles = JSON.parse(localStorage.getItem("configFiles") || "[]");
    menuManager.updateConfigFiles(configFiles);
    return configFiles;
  });

  ipcMain.on("update-config-files", (_event, files) => {
    menuManager.updateConfigFiles(files);
  });

  ipcMain.handle('get-screen-capture', async () => {
    const sources = await desktopCapturer.getSources({ types: ['screen'] });
    return sources[0].id;
  });
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('local.cyrene.desktop');
  const modelRoot = app.isPackaged
    ? join(process.resourcesPath, 'live2d-models')
    : join(localRoot, 'Open-LLM-VTuber', 'live2d-models');
  protocol.handle('cyrene', async (request) => {
    const url = new URL(request.url);
    const target = resolve(modelRoot, `.${decodeURIComponent(url.pathname)}`);
    const pathFromRoot = relative(modelRoot, target);
    if (url.host !== 'assets' || pathFromRoot.startsWith('..') || isAbsolute(pathFromRoot)) {
      return new Response('Not found', { status: 404 });
    }
    const result = await net.fetch(pathToFileURL(target).href);
    return new Response(result.body, {
      status: result.status,
      headers: { 'Content-Type': result.headers.get('content-type') || 'application/octet-stream', 'Access-Control-Allow-Origin': '*' },
    });
  });

  windowManager = new WindowManager();
  menuManager = new MenuManager((mode) => windowManager.setWindowMode(mode));

  const window = windowManager.createWindow({
    titleBarOverlay: {
      color: "#111111",
      symbolColor: "#FFFFFF",
      height: 30,
    },
  });
  menuManager.createTray();
  const log = (message: string) => appendFileSync(join(stateDir, 'renderer.log'), `${new Date().toISOString()} ${message}\n`);
  window.webContents.on('console-message', (_event, level, message) => {
    if (level >= 2 || message.includes('[Cyrene]')) log(message);
  });
  window.webContents.on('render-process-gone', (_event, details) => log(`Renderer exited: ${JSON.stringify(details)}`));
  window.webContents.on('did-fail-load', (_event, code, description) => log(`Load failed ${code}: ${description}`));

  window.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      window.hide();
    }
    return false;
  });

  if (process.env.NODE_ENV === "development") {
    globalShortcut.register("F12", () => {
      const window = windowManager.getWindow();
      if (!window) return;

      if (window.webContents.isDevToolsOpened()) {
        window.webContents.closeDevTools();
      } else {
        window.webContents.openDevTools();
      }
    });
  }

  setupIPC();

  app.on("activate", () => {
    const window = windowManager.getWindow();
    if (window) {
      window.show();
    }
  });

  app.on("browser-window-created", (_, window) => {
    optimizer.watchWindowShortcuts(window);
  });

  app.on('web-contents-created', (_, contents) => {
    contents.session.setPermissionRequestHandler((webContents, permission, callback) => {
      if (permission === 'media') {
        callback(true);
      } else {
        callback(false);
      }
    });
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  isQuitting = true;
  menuManager.destroy();
  globalShortcut.unregisterAll();
});
