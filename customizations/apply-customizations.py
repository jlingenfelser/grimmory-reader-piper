#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: apply-customizations.py /path/to/grimmory-source")
ROOT = Path(sys.argv[1]).resolve()
FRONTEND = ROOT / "frontend"

def p(rel: str) -> Path:
    f=ROOT/rel
    if not f.exists(): raise SystemExit(f"Required Grimmory v3.4.1 file missing: {f}")
    return f

def replace_once(text, old, new, label):
    if new in text: return text
    if old not in text: raise SystemExit(f"Upstream changed: could not find {label}")
    return text.replace(old,new,1)

def append_once(text, marker, block):
    return text if marker in text else text.rstrip()+"\n\n"+block.strip()+"\n"

# Browser Piper dependency. The CI workflow refreshes pnpm-lock.yaml after this change.
pkgf = p("frontend/package.json")
pkg = json.loads(pkgf.read_text())
pkg.setdefault("dependencies", {})["piper-tts-web"] = "1.1.2"
pkgf.write_text(json.dumps(pkg, indent=2) + chr(10))

# piper-tts-web 1.1.2 does not provide TypeScript declarations.
# Grimmory includes src/**/*.d.ts, so provide a local declaration shim.
piper_types = FRONTEND / "src" / "piper-tts-web.d.ts"
piper_types.write_text("declare module 'piper-tts-web';" + chr(10))

# Browser-local Piper needs its WASM/runtime files copied into Angular's public tree.
# Grimmory's angular.json already copies frontend/public/** into the final application.
dockerfile = ROOT / "Dockerfile"
docker_src = dockerfile.read_text()
asset_marker = "COPY frontend/ ./frontend/\n"
asset_copy = """COPY frontend/ ./frontend/
RUN mkdir -p frontend/public/onnx frontend/public/piper frontend/public/worker && \\
    cp -R frontend/node_modules/piper-tts-web/dist/onnx/. frontend/public/onnx/ && \\
    cp -R frontend/node_modules/piper-tts-web/dist/piper/. frontend/public/piper/ && \\
    cp -R frontend/node_modules/piper-tts-web/dist/worker/. frontend/public/worker/
"""
if "frontend/public/onnx" not in docker_src:
    if asset_marker not in docker_src:
        raise SystemExit("Upstream changed: could not find frontend Docker COPY anchor")
    docker_src = docker_src.replace(asset_marker, asset_copy, 1)
dockerfile.write_text(docker_src)

# Selection popup: Read aloud
f=p("frontend/src/app/features/readers/ebook-reader/shared/selection-popup.component.ts")
s=f.read_text()
s=replace_once(s,
"  type: 'select' | 'annotate' | 'delete' | 'dismiss' | 'preview' | 'search' | 'note' | 'go-to-link';",
"  type: 'select' | 'annotate' | 'delete' | 'dismiss' | 'preview' | 'search' | 'note' | 'go-to-link' | 'read-aloud';",
"selection action union")
if "onReadAloud(): void" not in s:
    anchor="  onNote(): void {\n"
    method="  onReadAloud(): void {\n    this.action.emit({type: 'read-aloud'});\n    this.showAnnotationOptions = false;\n    this.hasPreview = false;\n  }\n\n"
    if anchor not in s: raise SystemExit("Upstream changed: onNote anchor missing")
    s=s.replace(anchor,method+anchor,1)
f.write_text(s)

f=p("frontend/src/app/features/readers/ebook-reader/shared/selection-popup.component.html")
s=f.read_text()
if '(click)="onReadAloud()"' not in s:
    # Match structurally instead of depending on exact upstream whitespace.
    pattern = (
        r'(?P<indent>[ \t]*)<div class="divider"></div>\s*'
        r'(?P=indent)<div class="annotation-container">'
    )
    def _insert_read_aloud(match: re.Match[str]) -> str:
        indent = match.group("indent")
        return (
            f'{indent}<div class="divider"></div>\n'
            f'{indent}<button class="action-btn" (click)="onReadAloud()" title="Read aloud">\n'
            f'{indent}  <app-reader-icon name="play" [size]="16"></app-reader-icon>\n'
            f'{indent}</button>\n\n'
            f'{indent}<div class="divider"></div>\n'
            f'{indent}<div class="annotation-container">'
        )
    s, count = re.subn(pattern, _insert_read_aloud, s, count=1)
    if count != 1:
        raise SystemExit("Upstream changed: could not locate selection annotation container structurally")
f.write_text(s)

# Event service: arm tap-to-start and emit a collapsed CFI range.
f=p("frontend/src/app/features/readers/ebook-reader/core/event.service.ts")
s=f.read_text()
if "| { type: 'tts-anchor-picked'; detail: TextSelection }" not in s:
    s=replace_once(s,
"  | { type: 'text-selected'; detail: TextSelection; popupPosition: PopupPosition }\n",
"  | { type: 'text-selected'; detail: TextSelection; popupPosition: PopupPosition }\n  | { type: 'tts-anchor-picked'; detail: TextSelection }\n",
"ViewEvent text-selected member")
if "private ttsTapAnchorArmed" not in s:
    s=replace_once(s,"  private lastTouchTime = 0;","  private lastTouchTime = 0;\n  private ttsTapAnchorArmed = false;","lastTouchTime")
if "armTtsTapAnchor(): void" not in s:
    s=replace_once(s,
"  emit(event: ViewEvent): void {\n    this.eventSubject.next(event);\n  }",
"  emit(event: ViewEvent): void {\n    this.eventSubject.next(event);\n  }\n\n  armTtsTapAnchor(): void { this.ttsTapAnchorArmed = true; }\n  cancelTtsTapAnchor(): void { this.ttsTapAnchorArmed = false; }",
"emit method")
if "pickTtsAnchorFromPoint" not in s:
    click_anchor="    track(doc, 'click', ((event: MouseEvent) => {\n      // Ignore synthesized mouse events that follow touch events"
    click_new="    track(doc, 'click', ((event: MouseEvent) => {\n      if (this.ttsTapAnchorArmed) {\n        event.preventDefault();\n        event.stopPropagation();\n        this.pickTtsAnchorFromPoint(doc, event.clientX, event.clientY);\n        return;\n      }\n      // Ignore synthesized mouse events that follow touch events"
    s=replace_once(s,click_anchor,click_new,"iframe click handler")
    touch_anchor="    this.lastTouchTime = touchEndTime;\n\n    const selection = doc.defaultView?.getSelection();"
    touch_new="    this.lastTouchTime = touchEndTime;\n\n    if (this.ttsTapAnchorArmed && event.changedTouches.length === 1) {\n      const touch = event.changedTouches[0];\n      event.preventDefault();\n      event.stopPropagation();\n      this.isTextSelectionInProgress = false;\n      this.pickTtsAnchorFromPoint(doc, touch.clientX, touch.clientY);\n      return;\n    }\n\n    const selection = doc.defaultView?.getSelection();"
    s=replace_once(s,touch_anchor,touch_new,"touchend anchor")
    method=r'''  private pickTtsAnchorFromPoint(doc: Document, clientX: number, clientY: number): void {
    const anyDoc = doc as any;
    let range: Range | null = null;
    if (typeof anyDoc.caretRangeFromPoint === 'function') {
      range = anyDoc.caretRangeFromPoint(clientX, clientY) as Range | null;
    } else if (typeof anyDoc.caretPositionFromPoint === 'function') {
      const pos = anyDoc.caretPositionFromPoint(clientX, clientY);
      if (pos?.offsetNode) {
        range = doc.createRange();
        try { range.setStart(pos.offsetNode, pos.offset); range.collapse(true); } catch { range = null; }
      }
    }
    if (!range) return;
    const contents = this.viewCallbacks?.getContents();
    if (!contents?.length) return;
    const content = contents.find(item => item.doc === doc) ?? contents[0];
    const cfi = this.viewCallbacks?.getCFI(content.index, range);
    if (!cfi) return;
    this.ttsTapAnchorArmed = false;
    this.eventSubject.next({type: 'tts-anchor-picked', detail: {text: '', cfi, range, index: content.index}});
  }

'''
    marker="  private handleSelectionEnd(doc: Document): void {\n"
    if marker not in s: raise SystemExit("Upstream changed: handleSelectionEnd missing")
    s=s.replace(marker,method+marker,1)
f.write_text(s)

# View manager: chunk text with CFI anchors and expose tap arming.
f=p("frontend/src/app/features/readers/ebook-reader/core/view-manager.service.ts")
s=f.read_text()
if "sections?: unknown[];" not in s:
    s=replace_once(s,"interface FoliateBook {\n  toc?: FoliateTocItem[];","interface FoliateBook {\n  toc?: FoliateTocItem[];\n  sections?: unknown[];\n  spine?: unknown[];","FoliateBook interface")
methods=r'''  getTtsChunksFromSelectionStart(selection: TextSelection, maxChars = 650): Array<{text: string; cfi: string; index: number}> {
    const sourceRange = selection?.range;
    const doc = sourceRange?.startContainer?.ownerDocument;
    if (!sourceRange || !doc?.body) return [];
    return this.buildTtsChunks(selection.index, doc, sourceRange.startContainer, sourceRange.startOffset, maxChars);
  }

  getTtsChunksFromCurrentSection(maxChars = 650): Array<{text: string; cfi: string; index: number}> {
    const contents = this.getRenderer()?.getContents?.() ?? [];
    if (!contents.length) return [];
    const {index, doc} = contents[0];
    if (!doc?.body) return [];
    return this.buildTtsChunks(index, doc, null, 0, maxChars);
  }

  getSectionCount(): number {
    return this.view?.book?.sections?.length ?? this.view?.book?.spine?.length ?? 0;
  }

  armTtsTapAnchor(): void { this.eventService.armTtsTapAnchor(); }
  cancelTtsTapAnchor(): void { this.eventService.cancelTtsTapAnchor(); }

  private buildTtsChunks(index: number, doc: Document, startContainer: Node | null, startOffset: number, maxChars: number): Array<{text: string; cfi: string; index: number}> {
    const chunks: Array<{text: string; cfi: string; index: number}> = [];
    const pieces: Array<{text: string; node: Text; offset: number}> = [];
    const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
    let waitingForAnchor = !!startContainer;
    let node: Node | null;
    while ((node = walker.nextNode())) {
      if (node.nodeType !== Node.TEXT_NODE) continue;
      const textNode = node as Text;
      const parent = textNode.parentElement;
      if (!parent) continue;
      const tag = parent.tagName.toLowerCase();
      if (['script','style','noscript'].includes(tag)) continue;
      const style = doc.defaultView?.getComputedStyle(parent);
      if (style?.display === 'none' || style?.visibility === 'hidden') continue;
      let nodeStart = 0;
      if (waitingForAnchor) {
        if (textNode === startContainer) { nodeStart = Math.min(startOffset, textNode.data.length); waitingForAnchor = false; }
        else {
          try {
            const r=doc.createRange(); r.selectNodeContents(textNode);
            const anchor=doc.createRange(); anchor.setStart(startContainer!, startOffset); anchor.collapse(true);
            if (anchor.compareBoundaryPoints(Range.START_TO_START,r) >= 0) continue;
            waitingForAnchor=false;
          } catch { continue; }
        }
      }
      const raw=textNode.data.slice(nodeStart); if (!raw.trim()) continue;
      const pattern=/[^.!?]+(?:[.!?]+["'’”)\]]*)?(?:\s+|$)/g;
      let match: RegExpExecArray | null; let found=false;
      while ((match=pattern.exec(raw)) !== null) {
        const leading=match[0].search(/\S/); if (leading<0) continue;
        const spoken=match[0].replace(/\s+/g,' ').trim(); if (!spoken) continue;
        pieces.push({text:spoken,node:textNode,offset:nodeStart+match.index+leading}); found=true;
      }
      if (!found) { const leading=raw.search(/\S/); if (leading>=0) pieces.push({text:raw.replace(/\s+/g,' ').trim(),node:textNode,offset:nodeStart+leading}); }
    }
    let text=''; let anchorNode:Text|null=null; let anchorOffset=0;
    const flush=()=>{ const spoken=text.trim(); if (!spoken || !anchorNode) return; try { const range=doc.createRange(); range.setStart(anchorNode,anchorOffset); range.collapse(true); const cfi=this.view?.getCFI(index,range); if(cfi) chunks.push({text:spoken,cfi,index}); } catch(e){ console.warn('Could not create TTS chunk CFI',e); } text=''; anchorNode=null; anchorOffset=0; };
    for (const piece of pieces) { const next=text.length+(text?1:0)+piece.text.length; if(text && next>maxChars) flush(); if(!anchorNode){anchorNode=piece.node;anchorOffset=piece.offset;} text+=(text?' ':'')+piece.text; if(text.length>=maxChars) flush(); }
    flush(); return chunks;
  }

'''
if "getTtsChunksFromSelectionStart(" not in s:
    marker="  getSelection(): TextSelection | null {\n"
    if marker not in s: raise SystemExit("Upstream changed: getSelection missing")
    s=s.replace(marker,methods+marker,1)
f.write_text(s)

# New per-reader TTS service: signals keep Angular OnPush/zoned or zoneless builds responsive.
tts_service = r'''import {inject, Injectable, signal} from '@angular/core';
import {firstValueFrom} from 'rxjs';
import {ReaderViewManagerService, TextSelection} from './view-manager.service';
import {ReaderSelectionService} from '../features/selection/selection.service';

interface TtsChunk { text: string; cfi: string; index: number; }
interface TtsAudioItem { chunk: TtsChunk; url: string; }

@Injectable()
export class ReaderTtsService {
  private viewManager = inject(ReaderViewManagerService);
  private selectionService = inject(ReaderSelectionService);
  readonly state = signal<'idle'|'loading'|'playing'|'paused'|'error'>('idle');
  readonly isGenerating = signal(false);
  readonly tapToStartArmed = signal(false);
  readonly error = signal('');
  readonly showSettings = signal(false);
  readonly sentenceSilence = signal(0.40);
  readonly chunkChars = signal(650);
  readonly prefetchChunks = signal(1);
  readonly speechSpeed = signal(1.0);
  readonly localMode = signal(false);
  private anchor: TextSelection | null = null;
  private audio: HTMLAudioElement | null = null;
  private objectUrl: string | null = null;
  private abortController: AbortController | null = null;
  private sessionId = 0;
  private sectionIndex = -1;
  private pending: TtsChunk[] = [];
  private queue: TtsAudioItem[] = [];
  private generation: Promise<void> | null = null;
  private browserEngine: any = null;
  private readonly key='grimmoryReaderTtsSettings';
  private readonly legacyKey='bookloreReaderTtsSettings';
  private readonly voice='en_US-libritts_r-medium';
  private readonly speaker=0;

  constructor(){ this.loadSettings(); }
  setAnchor(selection: TextSelection){ this.anchor=selection; }
  toggleSettings(){ this.showSettings.update(v=>!v); }
  updateNumber(name:'sentenceSilence'|'chunkChars'|'prefetchChunks'|'speechSpeed', value:number){
    if(name==='sentenceSilence') this.sentenceSilence.set(Math.min(1.5,Math.max(0,value)));
    if(name==='chunkChars') this.chunkChars.set(Math.round(Math.min(2000,Math.max(250,value))));
    if(name==='prefetchChunks') this.prefetchChunks.set(Math.round(Math.min(3,Math.max(1,value))));
    if(name==='speechSpeed') this.speechSpeed.set(Math.min(1.6,Math.max(.6,value)));
    this.saveSettings();
  }
  toggleLocalMode(){ this.localMode.update(v=>!v); this.saveSettings(); }
  private loadSettings(){
    try { const raw=localStorage.getItem(this.key) ?? localStorage.getItem(this.legacyKey); if(!raw) return; const s=JSON.parse(raw);
      if(Number.isFinite(+s.sentenceSilence)) this.sentenceSilence.set(Math.min(1.5,Math.max(0,+s.sentenceSilence)));
      if(Number.isFinite(+s.chunkChars)) this.chunkChars.set(Math.round(Math.min(2000,Math.max(250,+s.chunkChars))));
      if(Number.isFinite(+s.prefetchChunks)) this.prefetchChunks.set(Math.round(Math.min(3,Math.max(1,+s.prefetchChunks))));
      if(Number.isFinite(+s.speechSpeed)) this.speechSpeed.set(Math.min(1.6,Math.max(.6,+s.speechSpeed)));
      this.localMode.set(Boolean(s.localMode)); this.saveSettings();
    } catch(e){ console.warn('Could not load TTS settings',e); }
  }
  private saveSettings(){ localStorage.setItem(this.key,JSON.stringify({sentenceSilence:this.sentenceSilence(),chunkChars:this.chunkChars(),prefetchChunks:this.prefetchChunks(),speechSpeed:this.speechSpeed(),localMode:this.localMode()})); }

  toggleTapToStart(){
    if(this.tapToStartArmed()){ this.tapToStartArmed.set(false); this.viewManager.cancelTtsTapAnchor(); return; }
    if(this.state()!=='idle' && this.state()!=='error') this.stop();
    this.error.set(''); this.selectionService.handleAction({type:'dismiss'}); this.viewManager.clearSelection(); this.tapToStartArmed.set(true); this.viewManager.armTtsTapAnchor();
  }
  async readAloud(){
    this.stop(); this.error.set('');
    if(!this.anchor?.range){ this.state.set('error'); this.error.set('Select text where you want reading to begin.'); return; }
    const chunks=this.viewManager.getTtsChunksFromSelectionStart(this.anchor,this.chunkChars());
    if(!chunks.length){ this.state.set('error'); this.error.set('No readable text was found after that position.'); return; }
    const sid=this.sessionId; this.sectionIndex=this.anchor.index; this.pending=chunks; this.state.set('loading');
    try { await this.prefetch(sid,1); if(sid===this.sessionId) await this.playNext(sid); }
    catch(e){ if(sid!==this.sessionId) return; this.isGenerating.set(false); this.state.set('error'); this.error.set(e instanceof Error?e.message:'Text-to-speech failed.'); }
  }
  async togglePause(){ if(!this.audio) return; if(this.audio.paused){await this.audio.play();this.state.set('playing');}else{this.audio.pause();this.state.set('paused');} }
  stop(){ this.tapToStartArmed.set(false); this.viewManager.cancelTtsTapAnchor(); this.sessionId+=1; this.abortController?.abort(); this.abortController=null; this.audio?.pause(); this.cleanupAudio(); for(const i of this.queue)URL.revokeObjectURL(i.url); this.queue=[]; this.pending=[]; this.generation=null; this.isGenerating.set(false); this.sectionIndex=-1; this.error.set(''); this.state.set('idle'); }
  destroy(){ this.stop(); this.browserEngine?.destroy?.(); this.browserEngine=null; }
  private async prefetch(sid:number,target=1){ if(sid!==this.sessionId)return; if(this.generation){await this.generation;return;} this.generation=(async()=>{this.isGenerating.set(true);while(sid===this.sessionId&&this.queue.length<target&&this.pending.length){const c=this.pending.shift()!;const item=await this.synthesize(c,sid);if(item&&sid===this.sessionId)this.queue.push(item);else if(item)URL.revokeObjectURL(item.url);}})(); try{await this.generation;}finally{if(sid===this.sessionId){this.generation=null;this.isGenerating.set(false);}} }
  private async synthesize(chunk:TtsChunk,sid:number):Promise<TtsAudioItem|null>{ if(sid!==this.sessionId)return null; if(this.localMode()){const b=await this.synthesizeBrowser(chunk.text,sid);return b&&sid===this.sessionId?{chunk,url:URL.createObjectURL(b)}:null;} const c=new AbortController();this.abortController=c;try{const r=await fetch('/tts/synthesize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:chunk.text,speaker_id:0,sentence_silence:this.sentenceSilence(),length_scale:1/this.speechSpeed()}),signal:c.signal});if(!r.ok)throw new Error(`TTS returned HTTP ${r.status}`);const b=await r.blob();return c.signal.aborted||sid!==this.sessionId?null:{chunk,url:URL.createObjectURL(b)};}finally{if(this.abortController===c)this.abortController=null;} }
  private async getBrowserEngine(){ if(this.browserEngine)return this.browserEngine; const p:any=await import('piper-tts-web'); this.browserEngine=new p.PiperWebEngine(); return this.browserEngine; }
  private splitSentences(text:string){const m=text.match(/[^.!?]+(?:[.!?]+["'’”)\]]*)?(?:\s+|$)/g);return(m??[text]).map(v=>v.replace(/\s+/g,' ').trim()).filter(Boolean);}
  private async synthesizeBrowser(text:string,sid:number):Promise<Blob|null>{const e=await this.getBrowserEngine();if(sid!==this.sessionId)return null;const wavs:Blob[]=[];for(const sentence of this.splitSentences(text)){if(sid!==this.sessionId)return null;const r=await e.generate(sentence,this.voice,this.speaker);if(!(r?.file instanceof Blob))throw new Error('Browser Piper did not return WAV audio.');wavs.push(r.file);}return this.mergeWavs(wavs,this.sentenceSilence());}
  private async mergeWavs(wavs:Blob[],pause:number){if(!wavs.length)throw new Error('Browser Piper generated no audio.');const bs=await Promise.all(wavs.map(w=>w.arrayBuffer()));const vs=bs.map(b=>new DataView(b));const sr=vs[0].getUint32(24,true),ch=vs[0].getUint16(22,true),bits=vs[0].getUint16(34,true);if(ch!==1||bits!==16)throw new Error('Unsupported browser Piper WAV format.');const parts=bs.map(b=>new Int16Array(b.slice(44)));const silence=Math.max(0,Math.round(sr*Math.max(0,pause)));const total=parts.reduce((a,p)=>a+p.length,0)+silence*Math.max(0,parts.length-1);const pcm=new Int16Array(total);let off=0;parts.forEach((part,i)=>{pcm.set(part,off);off+=part.length;if(i<parts.length-1)off+=silence;});const buf=new ArrayBuffer(44+pcm.byteLength),out=new DataView(buf);out.setUint32(0,0x46464952,true);out.setUint32(4,buf.byteLength-8,true);out.setUint32(8,0x45564157,true);out.setUint32(12,0x20746d66,true);out.setUint32(16,16,true);out.setUint16(20,1,true);out.setUint16(22,1,true);out.setUint32(24,sr,true);out.setUint32(28,sr*2,true);out.setUint16(32,2,true);out.setUint16(34,16,true);out.setUint32(36,0x61746164,true);out.setUint32(40,pcm.byteLength,true);new Int16Array(buf,44).set(pcm);return new Blob([buf],{type:'audio/wav'});}
  private async playNext(sid:number){if(sid!==this.sessionId)return;try{if(!this.queue.length&&!this.pending.length){const moved=await this.loadNextSection(sid);if(!moved){this.finish();return;}}if(!this.queue.length){this.state.set('loading');await this.prefetch(sid,1);}const item=this.queue.shift();if(!item||sid!==this.sessionId)return;await firstValueFrom(this.viewManager.goTo(item.chunk.cfi));if(sid!==this.sessionId){URL.revokeObjectURL(item.url);return;}this.cleanupAudio();this.objectUrl=item.url;const a=new Audio(item.url);if(this.localMode()){a.playbackRate=this.speechSpeed();(a as any).preservesPitch=true;}this.audio=a;a.onended=()=>{if(sid!==this.sessionId)return;this.cleanupAudio();void this.playNext(sid);};a.onerror=()=>{if(sid!==this.sessionId)return;this.state.set('error');this.error.set('Generated audio could not be played.');this.cleanupAudio();};await a.play();this.state.set('playing');void this.prefetch(sid,this.prefetchChunks()).catch(console.error);}catch(e){if(sid!==this.sessionId)return;this.state.set('error');this.error.set(e instanceof Error?e.message:'Text-to-speech failed.');this.cleanupAudio();}}
  private async loadNextSection(sid:number){const count=this.viewManager.getSectionCount();let next=this.sectionIndex+1;while(sid===this.sessionId&&next<count){this.state.set('loading');await firstValueFrom(this.viewManager.goToSection(next));await new Promise(r=>setTimeout(r,80));if(sid!==this.sessionId)return false;const chunks=this.viewManager.getTtsChunksFromCurrentSection(this.chunkChars());this.sectionIndex=next;if(chunks.length){this.pending=chunks;return true;}next+=1;}return false;}
  private finish(){this.cleanupAudio();for(const i of this.queue)URL.revokeObjectURL(i.url);this.queue=[];this.pending=[];this.generation=null;this.isGenerating.set(false);this.sectionIndex=-1;this.state.set('idle');}
  private cleanupAudio(){if(this.audio){this.audio.onended=null;this.audio.onerror=null;this.audio=null;}if(this.objectUrl){URL.revokeObjectURL(this.objectUrl);this.objectUrl=null;}}
}
'''
tts_path=ROOT/'frontend/src/app/features/readers/ebook-reader/core/reader-tts.service.ts'
tts_path.write_text(tts_service)

# Reader component wiring
f=p("frontend/src/app/features/readers/ebook-reader/ebook-reader.component.ts")
s=f.read_text()
if "ReaderTtsService" not in s:
    s=replace_once(s,
"import {ViewEvent} from './core/view-manager.service';",
"import {ViewEvent} from './core/view-manager.service';\nimport {ReaderTtsService} from './core/reader-tts.service';",
"ViewEvent import")
    s=replace_once(s,"    ReaderNoteService\n  ],","    ReaderNoteService,\n    ReaderTtsService\n  ],","component providers")
    s=replace_once(s,"  public stateService = inject(ReaderStateService);","  public stateService = inject(ReaderStateService);\n  public tts = inject(ReaderTtsService);","stateService injection")
    s=replace_once(s,"      this.wakeLockService.disable();","      this.tts.destroy();\n      this.wakeLockService.disable();","destroy callback")
    s=replace_once(s,
"          case 'text-selected':\n            this.selectionService.handleTextSelected(event.detail, event.popupPosition);",
"          case 'text-selected':\n            this.tts.setAnchor(event.detail);\n            this.selectionService.handleTextSelected(event.detail, event.popupPosition);",
"text-selected handler")
    s=replace_once(s,
"          case 'toggle-fullscreen':",
"          case 'tts-anchor-picked':\n            this.tts.tapToStartArmed.set(false);\n            this.tts.setAnchor(event.detail);\n            void this.tts.readAloud();\n            break;\n          case 'toggle-fullscreen':",
"toggle-fullscreen switch anchor")
    s=replace_once(s,
"  handleSelectionAction(action: TextSelectionAction): void {\n    if (action.type === 'note') {",
"  handleSelectionAction(action: TextSelectionAction): void {\n    if (action.type === 'read-aloud') {\n      void this.tts.readAloud();\n      this.selectionService.handleAction({type: 'dismiss'});\n    } else if (action.type === 'note') {",
"handleSelectionAction")
f.write_text(s)

# Reader overlay UI
f=p("frontend/src/app/features/readers/ebook-reader/ebook-reader.component.html")
s=f.read_text()
controls=r'''  @if (tts.state() === 'idle' || tts.state() === 'error') {
    <div class="tts-mobile-start-control" [class.tts-header-visible]="headerVisible()" (click)="$event.stopPropagation()">
      <button class="tts-mobile-start-button" type="button" [class.tts-mobile-start-armed]="tts.tapToStartArmed()" (click)="tts.toggleTapToStart()">
        {{ tts.tapToStartArmed() ? 'Tap text…' : '▶ Read from here' }}
      </button>
    </div>
  }
  <div class="tts-settings-toggle" [class.tts-header-visible]="headerVisible()" (click)="$event.stopPropagation()">
    <button class="tts-mini-button" type="button" (click)="tts.toggleSettings()" title="Read-aloud settings">⚙</button>
  </div>
  @if (tts.showSettings()) {
    <div class="tts-settings-panel" [class.tts-header-visible]="headerVisible()" (click)="$event.stopPropagation()">
      <div class="tts-settings-title">Read aloud</div>
      <label>Sentence pause <span>{{ tts.sentenceSilence() }}s</span></label>
      <input type="range" min="0" max="1.5" step="0.05" [value]="tts.sentenceSilence()" (change)="tts.updateNumber('sentenceSilence', +$any($event.target).value)">
      <label>Chunk size <span>{{ tts.chunkChars() }}</span></label>
      <input type="range" min="250" max="2000" step="50" [value]="tts.chunkChars()" (change)="tts.updateNumber('chunkChars', +$any($event.target).value)">
      <label>Queue ahead <span>{{ tts.prefetchChunks() }}</span></label>
      <input type="range" min="1" max="3" step="1" [value]="tts.prefetchChunks()" (change)="tts.updateNumber('prefetchChunks', +$any($event.target).value)">
      <label>Speed <span>{{ tts.speechSpeed() }}×</span></label>
      <input type="range" min="0.6" max="1.6" step="0.05" [value]="tts.speechSpeed()" (change)="tts.updateNumber('speechSpeed', +$any($event.target).value)">
      <label class="tts-toggle-row"><input type="checkbox" [checked]="tts.localMode()" (change)="tts.toggleLocalMode()"> Browser-local Piper</label>
      @if (tts.error()) { <div class="tts-error">{{ tts.error() }}</div> }
    </div>
  }
  @if (tts.state() === 'loading' || tts.state() === 'playing' || tts.state() === 'paused' || tts.isGenerating()) {
    <div class="tts-reader-controls" [class.tts-header-visible]="headerVisible()" (click)="$event.stopPropagation()">
      @if (tts.state() === 'playing' || tts.state() === 'paused') {
        <button class="tts-button tts-button-primary" type="button" (click)="tts.togglePause()">{{ tts.state() === 'paused' ? '▶' : '⏸' }}</button>
      }
      <button class="tts-button" type="button" (click)="tts.stop()">■</button>
      @if (tts.isGenerating() || tts.state() === 'loading') { <div class="tts-loading-spinner"></div> }
    </div>
  }
'''
if "tts-reader-controls" not in s:
    anchor="  <app-reader-navbar\n"
    if anchor not in s: raise SystemExit("Upstream changed: navbar html anchor missing")
    s=s.replace(anchor,controls+"\n"+anchor,1)
f.write_text(s)

f=p("frontend/src/app/features/readers/ebook-reader/ebook-reader.component.scss")
s=f.read_text()
css=r'''/* Grimmory Piper TTS */
.tts-mobile-start-control,.tts-settings-toggle,.tts-reader-controls,.tts-settings-panel{position:fixed;right:.75rem;z-index:13050;transition:top .25s ease-out;font-family:system-ui,sans-serif}
.tts-mobile-start-control{display:none;top:.65rem}.tts-mobile-start-control.tts-header-visible{top:calc(36px + .65rem)}
.tts-mobile-start-button,.tts-mini-button,.tts-button{border:1px solid rgba(255,255,255,.22);background:rgba(24,24,27,.9);color:#fff;border-radius:.6rem;min-height:2.55rem;padding:0 .8rem;box-shadow:0 4px 18px rgba(0,0,0,.25);backdrop-filter:blur(8px)}
.tts-mobile-start-armed{background:#fff!important;color:#18181b!important}
.tts-settings-toggle{top:.65rem}.tts-settings-toggle.tts-header-visible{top:calc(36px + .65rem)}.tts-mini-button{width:2.55rem;padding:0}
.tts-settings-panel{top:3.7rem;width:min(19rem,calc(100vw - 1.5rem));padding:.8rem;border-radius:.75rem;background:rgba(24,24,27,.94);color:#fff;box-shadow:0 8px 30px rgba(0,0,0,.35);display:grid;gap:.4rem}.tts-settings-panel.tts-header-visible{top:calc(36px + 3.7rem)}.tts-settings-title{font-weight:700;margin-bottom:.2rem}.tts-settings-panel label{font-size:.8rem;display:flex;justify-content:space-between;gap:1rem}.tts-settings-panel input[type=range]{width:100%}.tts-toggle-row{justify-content:flex-start!important;align-items:center}.tts-error{font-size:.78rem;color:#fecaca}
.tts-reader-controls{top:.65rem;display:flex;flex-direction:column;align-items:center;gap:.45rem;padding:.4rem;border-radius:.75rem;background:rgba(24,24,27,.82);box-shadow:0 4px 18px rgba(0,0,0,.25);backdrop-filter:blur(8px)}.tts-reader-controls.tts-header-visible{top:calc(36px + .65rem)}.tts-button{width:2.65rem;padding:0}.tts-button-primary{background:#fff;color:#18181b}.tts-loading-spinner{width:1.15rem;height:1.15rem;border:2px solid rgba(255,255,255,.32);border-top-color:#fff;border-radius:50%;animation:tts-spin .75s linear infinite}@keyframes tts-spin{to{transform:rotate(360deg)}}
@media (hover:none) and (pointer:coarse),(max-width:640px){.tts-mobile-start-control{display:flex}.tts-settings-toggle{top:3.85rem}.tts-settings-toggle.tts-header-visible{top:calc(36px + 3.85rem)}.tts-settings-panel{top:6.9rem}.tts-settings-panel.tts-header-visible{top:calc(36px + 6.9rem)}}
'''
s=append_once(s,"Grimmory Piper TTS",css)
f.write_text(s)


# ---------------------------------------------------------------------------
# Fix Foliate touch navigation in scrolled reading mode.
#
# In scrolled mode, let the browser own touch scrolling completely.
# Foliate must not interpret the same gesture as horizontal page navigation
# when the finger is released.
# ---------------------------------------------------------------------------

paginator_candidates = [
    candidate
    for candidate in ROOT.rglob("paginator.js")
    if "node_modules" not in candidate.parts
]

paginator = None

for candidate in paginator_candidates:
    candidate_text = candidate.read_text(errors="ignore")

    if "#onTouchMove" in candidate_text and "#onTouchEnd" in candidate_text:
        paginator = candidate
        break

if paginator is None:
    raise SystemExit(
        "Could not find Grimmory's Foliate paginator.js."
    )

foliate = paginator.read_text()


def add_scrolled_guard(source: str, handler: str) -> str:
    """
    Insert a guard directly after the opening line of a private
    Foliate touch handler.

    This deliberately avoids matching the implementation inside the
    handler because different Foliate revisions implement the gesture
    logic differently.
    """

    guard = "if (this.getAttribute('flow') === 'scrolled') return"

    lines = source.splitlines(keepends=True)

    handler_line = None

    for i, line in enumerate(lines):
        if handler in line:
            handler_line = i
            break

    if handler_line is None:
        raise SystemExit(
            f"Could not find Foliate handler {handler}."
        )

    # Find the line that actually opens the method body.
    # Usually this is the same line, but this also supports multiline
    # method declarations.
    open_line = None

    for i in range(handler_line, min(handler_line + 10, len(lines))):
        if lines[i].rstrip().endswith("{"):
            open_line = i
            break

    if open_line is None:
        raise SystemExit(
            f"Could not find opening brace for Foliate handler {handler}."
        )

    # Already patched?
    nearby = "".join(lines[open_line + 1:open_line + 5])

    if guard in nearby:
        return source

    method_indent = lines[open_line][
        :len(lines[open_line]) - len(lines[open_line].lstrip())
    ]

    body_indent = method_indent + "    "

    lines.insert(
        open_line + 1,
        body_indent + guard + "\n"
    )

    return "".join(lines)


foliate = add_scrolled_guard(foliate, "#onTouchMove")
foliate = add_scrolled_guard(foliate, "#onTouchEnd")

paginator.write_text(foliate)

print(
    f"Applied scrolled touch-navigation fix to "
    f"{paginator.relative_to(ROOT)}"
)


print("Applied Grimmory v3.4.1 Piper TTS customizations")
