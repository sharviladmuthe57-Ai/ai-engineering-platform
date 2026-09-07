import sharp from 'sharp';
import { mkdirSync } from 'node:fs';

const inputs = process.argv.slice(2);
if (inputs.length !== 3) throw new Error('Supply the three reference image paths, in model/coordinate/building order.');
mkdirSync('public/vision', { recursive: true });
for (let i = 0; i < inputs.length; i++) {
  const result = await sharp(inputs[i]).resize({ width: 1600, withoutEnlargement: true })
    .webp({ quality: 90 }).toFile(`public/vision/reference-${i + 1}.webp`);
  console.log(`Reference ${i + 1}: ${result.width} × ${result.height}, ${result.size} bytes`);
}
