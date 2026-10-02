const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const isWin = process.platform === 'win32';
const venvPy = isWin 
  ? path.join(__dirname, '.venv', 'Scripts', 'python.exe')
  : path.join(__dirname, '.venv', 'bin', 'python');

const pythonExe = fs.existsSync(venvPy) ? venvPy : (isWin ? 'python' : 'python3');

const userArgs = process.argv.slice(2);
const targetArgs = userArgs.length > 0 ? userArgs : ['run_server.py'];

const child = spawn(pythonExe, targetArgs, { stdio: 'inherit' });
child.on('exit', (code) => process.exit(code || 0));
