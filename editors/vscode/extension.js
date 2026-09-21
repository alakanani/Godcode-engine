// God Code VS Code extension — run and check .god files from the editor.
// Requires the God Code interpreter: pip install -e <path-to-Godcode-engine>
const vscode = require('vscode');
const { exec } = require('child_process');

function findGodCode() {
  // Try the `godcode` CLI first, fall back to `python3 -m godcode`.
  return new Promise((resolve) => {
    exec('godcode --help', (err) => {
      if (!err) return resolve('godcode');
      exec('python3 -m godcode --help', (err2) => {
        resolve(err2 ? null : 'python3 -m godcode');
      });
    });
  });
}

async function runGodCode(checkOnly) {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'godcode') {
    vscode.window.showWarningMessage('Open a God Code (.god) file first.');
    return;
  }
  await editor.document.save();
  const bin = await findGodCode();
  if (!bin) {
    vscode.window.showErrorMessage(
      'God Code interpreter not found. Install it with: pip install -e <path-to-Godcode-engine>'
    );
    return;
  }
  const file = editor.document.fileName;
  const cmd = checkOnly ? `${bin} check "${file}"` : `${bin} run "${file}"`;
  const out = vscode.window.createOutputChannel('God Code');
  out.show(true);
  out.appendLine(`$ ${cmd}`);
  exec(cmd, { timeout: 60000 }, (err, stdout, stderr) => {
    if (stdout) out.append(stdout);
    if (stderr) out.append(stderr);
    if (err) out.appendLine(`[exited with code ${err.code}]`);
    else out.appendLine('[ASCEND] Complete. 🕊');
  });
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand('godcode.runFile', () => runGodCode(false)),
    vscode.commands.registerCommand('godcode.checkFile', () => runGodCode(true))
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
