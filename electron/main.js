const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("node:child_process");
const http = require("node:http");
const path = require("node:path");

const SERVER_HOST = "127.0.0.1";
const SERVER_PORT = 5000;
const SERVER_URL = `http://${SERVER_HOST}:${SERVER_PORT}`;

let mainWindow = null;
let backendProcess = null;
let quitting = false;

function resolveBackendDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend");
  }
  return path.resolve(__dirname, "..");
}

function getPythonCommand() {
  const override = process.env.UPSCALED_PYTHON;
  if (override && override.trim()) {
    return { command: override.trim(), argsPrefix: [] };
  }

  if (process.platform === "win32") {
    return { command: "py", argsPrefix: ["-3"] };
  }

  return { command: "python3", argsPrefix: [] };
}

function waitForServerReady({ timeoutMs }) {
  const startedAt = Date.now();

  return new Promise((resolve, reject) => {
    const tick = () => {
      if (quitting) return reject(new Error("App is quitting"));

      const elapsed = Date.now() - startedAt;
      if (elapsed > timeoutMs) {
        return reject(new Error(`Server did not become ready within ${timeoutMs}ms`));
      }

      const req = http.request(
        SERVER_URL,
        { method: "GET", timeout: 1500 },
        (res) => {
          res.resume();
          resolve();
        }
      );

      req.on("timeout", () => {
        req.destroy(new Error("timeout"));
      });
      req.on("error", () => {
        setTimeout(tick, 250);
      });
      req.end();
    };

    tick();
  });
}

function startBackend() {
  const backendDir = resolveBackendDir();
  const backendEntry = path.join(backendDir, "app.py");
  const dataDir = path.join(app.getPath("userData"), "upscaled-data");

  const { command, argsPrefix } = getPythonCommand();
  const child = spawn(command, [...argsPrefix, backendEntry], {
    cwd: backendDir,
    stdio: "ignore",
    env: {
      ...process.env,
      UPSCALED_HOST: SERVER_HOST,
      UPSCALED_PORT: String(SERVER_PORT),
      UPSCALED_DATA_DIR: dataDir,
      FLASK_DEBUG: "0"
    }
  });

  child.on("exit", (code) => {
    if (!quitting && code !== 0) {
      dialog.showErrorBox(
        "Upscaled backend stopped",
        `The Python server exited unexpectedly (code: ${code ?? "unknown"}).\n\nIf Python isn't installed, install it and try again.\n\nYou can also set UPSCALED_PYTHON to your python executable path.`
      );
      app.quit();
    }
  });

  backendProcess = child;
}

function stopBackend() {
  if (!backendProcess) return;

  try {
    backendProcess.kill();
  } catch {
  } finally {
    backendProcess = null;
  }
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 760,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(SERVER_URL)) return { action: "allow" };
    shell.openExternal(url);
    return { action: "deny" };
  });

  await mainWindow.loadURL(SERVER_URL);
  mainWindow.show();
}

async function boot() {
  startBackend();

  try {
    await waitForServerReady({ timeoutMs: 60_000 });
  } catch (err) {
    dialog.showErrorBox(
      "Failed to start Upscaled",
      `Could not reach the local server at ${SERVER_URL}.\n\n${String(err?.message || err)}\n\nMake sure Python dependencies are installed (requirements.txt).`
    );
    app.quit();
    return;
  }

  await createWindow();
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.on("ready", boot);

  app.on("before-quit", () => {
    quitting = true;
    stopBackend();
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
      app.quit();
    }
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      boot();
    }
  });
}
