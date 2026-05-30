import { request } from "@playwright/test";
import { ChildProcess, execSync, spawn } from "child_process";

type StartServerOptions = {
  port: number;
  env?: Record<string, string>;
};

export type NeonServer = {
  baseURL: string;
  stop: () => Promise<void>;
};

function buildServerEnv(opts: StartServerOptions): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env };
  env.API_ADDR = `:${opts.port}`;
  env.TEMPORAL_AUTO_DEV = "1";
  delete env.PAYMENT_NEVER_FAIL;
  delete env.PAYMENT_ALWAYS_FAIL;
  delete env.PAYMENT_FAIL_UNTIL;
  delete env.PAYMENT_VALIDATION_DELAY;
  for (const [key, value] of Object.entries(opts.env ?? {})) {
    env[key] = value;
  }
  if (!env.HOLD_DURATION) {
    env.HOLD_DURATION = "2m";
  }
  return env;
}

export async function startNeonServer(opts: StartServerOptions): Promise<NeonServer> {
  await freePort(opts.port);
  const baseURL = `http://127.0.0.1:${opts.port}`;
  const goCmd = process.platform === "win32" ? "go.exe" : "go";
  const child = spawn(goCmd, ["run", "./cmd/api"], {
    cwd: process.cwd(),
    env: buildServerEnv(opts),
    stdio: "pipe",
    shell: false,
  });

  await waitForServerReady(baseURL, child);

  return {
    baseURL,
    stop: async () => {
      await stopChild(child);
    },
  };
}

async function freePort(port: number): Promise<void> {
  if (process.platform === "win32") {
    try {
      const out = execSync(`netstat -ano | findstr ":${port}" | findstr LISTENING`, {
        encoding: "utf8",
      });
      const pids = new Set<string>();
      for (const line of out.split("\n")) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && pid !== "0") {
          pids.add(pid);
        }
      }
      for (const pid of pids) {
        try {
          execSync(`taskkill /PID ${pid} /F`);
        } catch {
          // process may have already exited
        }
      }
      if (pids.size > 0) {
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
    } catch {
      // port already free
    }
    return;
  }

  try {
    execSync(`fuser -k ${port}/tcp`, { stdio: "ignore" });
    await new Promise((resolve) => setTimeout(resolve, 500));
  } catch {
    // port already free
  }
}

async function waitForServerReady(baseURL: string, child: ChildProcess): Promise<void> {
  const client = await request.newContext();
  const deadline = Date.now() + 60000;
  let lastError = "";

  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      lastError = `process exited with code ${child.exitCode}`;
      break;
    }
    try {
      const response = await client.get(`${baseURL}/api/v1/flights`);
      if (response.ok()) {
        if (child.exitCode !== null) {
          lastError = `process exited with code ${child.exitCode}`;
          break;
        }
        await client.dispose();
        return;
      }
      lastError = `status=${response.status()}`;
    } catch (err) {
      lastError = String(err);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  await client.dispose();
  throw new Error(
    `Neon server did not become ready at ${baseURL}. ${lastError}. ` +
      "If the port is already in use, stop the old process or use a different port.",
  );
}

async function stopChild(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null) {
    return;
  }

  child.kill("SIGTERM");
  await Promise.race([
    new Promise<void>((resolve) => {
      child.once("exit", () => resolve());
    }),
    new Promise<void>((resolve) => setTimeout(resolve, 5000)),
  ]);

  if (child.exitCode === null) {
    child.kill("SIGKILL");
  }
}
