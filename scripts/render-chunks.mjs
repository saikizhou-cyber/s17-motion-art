// Chunked final render. A single long render can stall the headless browser (in the case study it
// froze near frame 725 on a WebGL-heavy scene), so render frame ranges separately, then join.
//
//   node render-chunks.mjs 0-359 360-719 720-899 900-1078   -> out/seg_<from>.mp4 (video only, --muted)
//   node render-chunks.mjs --join                           -> concat out/seg_*.mp4 + audio -> out/pv.mp4
//
// Run from the Remotion project root. Environment:
//   PV_COMP   composition id            (default PV)
//   PV_SCALE  1.5 renders 1920x1080 from a 1280x720 composition; every layer is re-rasterised, not upscaled
//   PV_CONC   render concurrency        (default 3; use 2 if a chunk dies with `write EOF`)
//   PV_AUDIO  audio file muxed on --join (default public/audio/bgm.wav)
//   PV_LUFS   e.g. -14: master the music to that loudness on --join (two-pass loudnorm, true peak -1 dBTP)
//
// All ranges are checked before the first render starts. --join counts the frames of every segment and
// refuses to join unless each one runs straight into the next (a stalled or stale segment would otherwise
// be concatenated silently). Segments are silent, so swapping the music later never needs a re-render:
// just --join again with another PV_AUDIO. The output is cut to the video's own duration.
import {execFileSync, execSync, spawnSync} from 'node:child_process';
import {existsSync, readdirSync, rmSync, writeFileSync} from 'node:fs';

const USAGE = 'usage: node render-chunks.mjs <from-to> [...]  |  node render-chunks.mjs --join';
const fail = (msg) => {
	console.error(msg);
	process.exit(1);
};

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '-h' || args[0] === '--help') {
	(args.length === 0 ? console.error : console.log)(USAGE);
	process.exit(args.length === 0 ? 1 : 0);
}
if (args[0] === '--join') {
	if (!existsSync('out')) fail('./out not found: run from the Remotion project root, after rendering the chunks');
	const segs = readdirSync('out')
		.filter((f) => /^seg_\d+\.mp4$/.test(f))
		.sort((a, b) => parseInt(a.slice(4)) - parseInt(b.slice(4)));
	if (segs.length === 0) fail('no out/seg_*.mp4 to join');
	const start = segs.map((s) => parseInt(s.slice(4)));
	const frames = segs.map((s) => {
		try {
			// csv output can carry a trailing empty field ("360,") on real renders: keep the first field only
			const out = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', `out/${s}`], {stdio: ['ignore', 'pipe', 'ignore']}).toString();
			return Number(out.trim().split(/[,\s]/)[0]);
		} catch {
			return NaN;
		}
	});
	const gaps = [];
	segs.forEach((s, i) => {
		if (!(frames[i] > 0)) return gaps.push(`${s}: unreadable or empty`);
		const end = start[i] + frames[i];
		if (i + 1 < segs.length && end !== start[i + 1]) {
			const d = start[i + 1] - end;
			gaps.push(`${s}: ${frames[i]} frames = ${start[i]}-${end - 1}, but ${segs[i + 1]} starts at ${start[i + 1]} (${d > 0 ? `${d} frames missing` : `${-d} frames overlap`})`);
		}
	});
	if (gaps.length) fail(`segments are not contiguous, nothing joined:\n  ${gaps.join('\n  ')}\nre-render the broken range, or delete stale out/seg_*.mp4`);
	if (start[0] !== 0) console.warn(`warning: the first segment starts at frame ${start[0]}, not 0: the audio will not line up`);
	writeFileSync('out/seg_list.txt', segs.map((s) => `file '${s}'`).join('\n'));
	execSync('ffmpeg -hide_banner -v error -y -f concat -safe 0 -i out/seg_list.txt -c copy out/pv_video.mp4', {stdio: 'inherit'});
	const audio = process.env.PV_AUDIO ?? 'public/audio/bgm.wav';
	const dur = execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', 'out/pv_video.mp4']).toString().trim();
	if (existsSync(audio)) {
		// PV_LUFS=-14 masters the music to that integrated loudness (two-pass EBU R128, true peak -1 dBTP):
		// platforms turn loud uploads down and quiet ones up, so a known level keeps the hits where you mixed them
		const af = [];
		if (process.env.PV_LUFS) {
			const I = Number(process.env.PV_LUFS);
			if (!(I < 0)) fail(`PV_LUFS must be negative LUFS, e.g. -14 (got ${process.env.PV_LUFS})`);
			const probe = spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', audio, '-t', dur, '-af', `loudnorm=I=${I}:TP=-1:LRA=11:print_format=json`, '-f', 'null', '-'], {encoding: 'utf8'});
			const m = /\{[^{}]*"input_i"[^{}]*\}/.exec(probe.stderr || '');
			if (!m) fail(`loudness measurement failed on ${audio}`);
			const j = JSON.parse(m[0]);
			af.push('-af', `loudnorm=I=${I}:TP=-1:LRA=11:measured_I=${j.input_i}:measured_TP=${j.input_tp}:measured_LRA=${j.input_lra}:measured_thresh=${j.input_thresh}:offset=${j.target_offset}:linear=true`, '-ar', '48000');
			console.log(`loudness ${j.input_i} LUFS -> ${I} LUFS`);
		}
		execFileSync('ffmpeg', ['-hide_banner', '-v', 'error', '-y', '-i', 'out/pv_video.mp4', '-i', audio, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', ...af, '-c:a', 'aac', '-b:a', '256k', '-t', dur, '-movflags', '+faststart', 'out/pv.mp4'], {stdio: 'inherit'});
	} else {
		console.warn(`audio ${audio} not found: writing a silent out/pv.mp4`);
		execFileSync('ffmpeg', ['-hide_banner', '-v', 'error', '-y', '-i', 'out/pv_video.mp4', '-c', 'copy', '-movflags', '+faststart', 'out/pv.mp4'], {stdio: 'inherit'});
	}
	rmSync('out/pv_video.mp4');
	console.log(`Done: out/pv.mp4 (${segs.length} segments, ${dur} s)`);
} else {
	// validate every range before the first (slow) render starts
	const froms = new Set();
	for (const r of args) {
		const m = /^(\d+)-(\d+)$/.exec(r);
		if (!m) fail(`bad range ${r} (expected from-to, e.g. 0-359)`);
		if (Number(m[1]) > Number(m[2])) fail(`bad range ${r}: from is after to`);
		if (froms.has(Number(m[1]))) fail(`bad range ${r}: another range already starts at ${m[1]} (both would write out/seg_${m[1]}.mp4)`);
		froms.add(Number(m[1]));
	}
	const comp = process.env.PV_COMP ?? 'PV';
	for (const r of args) {
		const from = r.split('-')[0];
		const scale = process.env.PV_SCALE ? ` --scale=${process.env.PV_SCALE}` : '';
		execSync(`npx remotion render ${comp} out/seg_${from}.mp4 --codec=h264 --crf=16 --muted --frames=${r} --concurrency=${process.env.PV_CONC ?? 3} --timeout=240000${scale}`, {stdio: 'inherit'});
	}
}
