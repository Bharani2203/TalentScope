import { spawn } from 'node:child_process';
import { connect } from 'node:net';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const host = '127.0.0.1';
const port = 3000;
const serveCli = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../node_modules/serve/build/main.js',
);

const probe = connect({ host, port });
probe.once('connect', () => {
  probe.destroy();
  console.error(`Frontend port ${port} is already in use. Stop its existing process before running npm start.`);
  process.exitCode = 1;
});
probe.once('error', (error) => {
  if (error.code === 'ECONNREFUSED' || error.code === 'EHOSTUNREACH') {
    startServe();
    return;
  }
  console.error(`Unable to check frontend port ${port}: ${error.message}`);
  process.exitCode = 1;
});

function startServe() {
  const child = spawn(process.execPath, [serveCli, '.', '-l', String(port)], {
    cwd: process.cwd(),
    stdio: ['inherit', 'pipe', 'inherit'],
  });
  let output = '';
  let fallbackStopped = false;

  child.stdout.on('data', (chunk) => {
    const text = chunk.toString();
    process.stdout.write(text);
    output = (output + text).slice(-2048);

    const localUrl = output.match(/Local:\s+https?:\/\/[^\s:]+:(\d+)/i);
    if (localUrl && Number(localUrl[1]) !== port && !fallbackStopped) {
      fallbackStopped = true;
      console.error(`serve selected port ${localUrl[1]} instead of required port ${port}; stopping it.`);
      child.kill();
      process.exitCode = 1;
    }
  });

  child.on('error', (error) => {
    console.error(`Unable to start frontend server: ${error.message}`);
    process.exitCode = 1;
  });
  child.on('exit', (code, signal) => {
    if (signal && !fallbackStopped) process.kill(process.pid, signal);
    else if (!fallbackStopped) process.exitCode = code ?? 1;
  });
}
