/**
 * Copy scenario and rubric JSON files from service to portal's public directory
 * This ensures portal has access to scenarios and rubrics during local dev and build
 */
import { copyFileSync, mkdirSync, readdirSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ── Scenarios ────────────────────────────────────────────────────────
const scenarioSourceDir = join(__dirname, '../../service/email_agent/scenarios');
const scenarioTargetDir = join(__dirname, '../public/scenarios');

mkdirSync(scenarioTargetDir, { recursive: true });

const scenarioFiles = readdirSync(scenarioSourceDir).filter(file => file.endsWith('.json'));
scenarioFiles.forEach(file => {
  copyFileSync(join(scenarioSourceDir, file), join(scenarioTargetDir, file));
  console.log(`✓ Copied scenario: ${file}`);
});

const manifest = JSON.stringify(scenarioFiles);
writeFileSync(join(scenarioTargetDir, 'manifest.json'), manifest);
console.log(`✓ Created manifest.json with ${scenarioFiles.length} scenarios`);

// ── Rubrics ──────────────────────────────────────────────────────────
const rubricSourceDir = join(__dirname, '../../service/email_agent/rubrics');
const rubricTargetDir = join(__dirname, '../public/rubrics');

mkdirSync(rubricTargetDir, { recursive: true });

const rubricFiles = readdirSync(rubricSourceDir).filter(file => file.endsWith('.json'));
rubricFiles.forEach(file => {
  copyFileSync(join(rubricSourceDir, file), join(rubricTargetDir, file));
  console.log(`✓ Copied rubric: ${file}`);
});

