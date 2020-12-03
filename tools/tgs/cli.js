const fs = require('fs');
const path = require('path');
const {ArgumentParser} = require('argparse');

const {createBrowser, convertFile} = require('./index.js');

const convertFiles = async function (filePaths, outPath, browser, options) {
  for (const filePath of filePaths) {
    console.log(`Converting ${filePath}...`);
    try {
      await convertFile(filePath, {output: outPath, browser, ...options});
    } catch (e) {
      console.error(e);
    }
  }
};

const main = async function () {
  const parser = new ArgumentParser({
    description: 'Animated stickers for Telegram (*.tgs) converter',
  });
  parser.addArgument('--height', {help: 'Output image height. Default: auto', type: Number});
  parser.addArgument('--width', {help: 'Output image width. Default: auto', type: Number});
  parser.addArgument('--out_path',  {help: 'Output image path and format' });
  parser.addArgument('paths', {help: 'Paths to .tgs files to convert', nargs: '+'});
  const args = parser.parseArgs();

  const paths = args.paths;
  const out_path = args.out_path;
  for (let i = 0; i < paths.length; ++i) {
    let filePath = paths[i];
    if (fs.lstatSync(filePath).isDirectory()) {
      for (const subFilePath of fs.readdirSync(filePath)) {
        if (path.extname(subFilePath) === '.tgs') {
          paths.push(path.join(filePath, subFilePath));
        }
      }
      paths.splice(i--, 1);
    }
  }

  const browser = await createBrowser({
    chromiumPath: '/user/bin/chromium-browser',
    useSandbox: JSON.parse(process.env['USE_SANDBOX'] || 'true'),
  });
  await convertFiles(paths, out_path, browser, {width: args.width, height: args.height});
  await browser.close();
};

main();
