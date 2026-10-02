// QA video: reference (left) vs our render (right), for checking cut timing and motion at full speed.
// Local review only: do not publish it (the reference is somebody else's work).
//   node side-by-side.mjs <ref.mp4> [ours=out/pv.mp4] [out=out/side-by-side.mp4]
import {execFileSync} from 'node:child_process';

const [, , ref, ours = 'out/pv.mp4', out = 'out/side-by-side.mp4'] = process.argv;
if (!ref || ref === '-h' || ref === '--help') {
	console.error('usage: node side-by-side.mjs <ref.mp4> [ours=out/pv.mp4] [out=out/side-by-side.mp4]');
	process.exit(1);
}
const filter = [
	'[0:v]scale=960:540,setsar=1[l]',
	'[1:v]scale=960:540,setsar=1[r]',
	'[l][r]hstack=inputs=2,pad=1920:600:0:30:black[v]',
].join(';');
execFileSync(
	'ffmpeg',
	['-hide_banner', '-v', 'error', '-y', '-i', ref, '-i', ours, '-filter_complex', filter, '-map', '[v]', '-map', '1:a?', '-c:v', 'libx264', '-crf', '20', '-preset', 'veryfast', '-c:a', 'aac', '-shortest', out],
	{stdio: 'inherit'},
);
console.log(`Done: ${out}`);
