const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const isWin = process.platform === 'win32';
const venvPy = isWin 
  ? path.join(__dirname, '.venv', 'Scripts', 'python.exe')
  : path.join(__dirname, '.venv', 'bin', 'python');

const pythonExe = fs.existsSync(venvPy) ? venvPy : (isWin ? 'python' : 'python3');

const child = spawn(pythonExe, ['run_server.py'], { stdio: 'inherit' });
child.on('exit', (code) => process.exit(code || 0));
