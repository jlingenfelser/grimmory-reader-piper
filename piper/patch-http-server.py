from pathlib import Path
import re
import piper.http_server

path = Path(piper.http_server.__file__)
source = path.read_text()
if 'data.get("sentence_silence", args.sentence_silence)' not in source:
    marker = '        syn_config = SynthesisConfig(\n'
    if marker not in source:
        raise SystemExit('Piper HTTP server layout changed: SynthesisConfig marker not found')
    source = source.replace(marker, '        sentence_silence = max(0.0, float(data.get("sentence_silence", args.sentence_silence)))\n' + marker, 1)
pattern = re.compile(r'bytes\(\s*int\(\s*voice\.config\.sample_rate\s*\*\s*args\.sentence_silence\s*\*\s*2\s*\)\s*\)', re.S)
source, count = pattern.subn('bytes(int(voice.config.sample_rate * sentence_silence) * 2)', source, count=1)
if count == 0 and 'voice.config.sample_rate * sentence_silence' not in source:
    raise SystemExit('Piper HTTP server layout changed: silence-byte expression not found')
path.write_text(source)
print(f'Patched {path}')
