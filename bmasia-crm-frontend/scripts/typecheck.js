#!/usr/bin/env node
/*
 * Type-check the project's own sources (tsconfig.json, no emit).
 *
 * Plain `tsc --noEmit` is not usable here: react-scripts 5 pins TypeScript 4.x,
 * which cannot parse some declaration files shipped by @mui/x-* 8.x (TypeScript
 * 5 syntax), and tsc skips all semantic checks once any file has a syntax
 * error. This runs the same compiler on the same config, but reports
 * diagnostics only for files outside node_modules, as the CRA build does.
 */
const path = require('path');
const ts = require('typescript');

const root = path.resolve(__dirname, '..');
const configPath = path.join(root, 'tsconfig.json');

const host = {
  ...ts.sys,
  onUnRecoverableConfigFileDiagnostic: (diagnostic) => {
    throw new Error(ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'));
  },
};
const config = ts.getParsedCommandLineOfConfigFile(configPath, {}, host);
const program = ts.createProgram(config.fileNames, config.options);

const diagnostics = [...config.errors, ...program.getOptionsDiagnostics()];
for (const sourceFile of program.getSourceFiles()) {
  // TypeScript normalises file names to forward slashes on every platform.
  if (sourceFile.fileName.includes('/node_modules/')) {
    continue;
  }
  diagnostics.push(
    ...program.getSyntacticDiagnostics(sourceFile),
    ...program.getSemanticDiagnostics(sourceFile),
  );
}

const formatHost = {
  getCanonicalFileName: (fileName) => fileName,
  getCurrentDirectory: () => root,
  getNewLine: () => '\n',
};
if (diagnostics.length > 0) {
  process.stderr.write(ts.formatDiagnostics(diagnostics, formatHost));
  process.stderr.write(`\nType check failed: ${diagnostics.length} error(s).\n`);
  process.exit(1);
}
console.log(`Type check passed (TypeScript ${ts.version}, ${config.fileNames.length} files).`);
