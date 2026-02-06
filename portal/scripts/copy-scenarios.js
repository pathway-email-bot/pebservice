/**
 * Copy scenario JSON files from service to portal's public directory
 * This ensures portal has access to scenarios during local dev and build
 */
import { copyFileSync, mkdirSync, readdirSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sourceDir = join(__dirname, '../../service/email_agent/scenarios');
const targetDir = join(__dirname, '../public/scenarios');

// Create target directory if it doesn't exist
mkdirSync(targetDir, { recursive: true });

// Get all JSON files
const files = readdirSync(sourceDir).filter(file => file.endsWith('.json'));

// Copy each file
files.forEach(file => {
  const source = join(sourceDir, file);
  const target = join(targetDir, file);
  copyFileSync(source, target);
  console.log(`✓ Copied ${file}`);
});

// Create manifest.json
const manifest = JSON.stringify(files);
writeFileSync(join(targetDir, 'manifest.json'), manifest);
console.log(`✓ Created manifest.json with ${files.length} scenarios`);
