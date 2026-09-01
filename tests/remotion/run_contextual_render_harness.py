#!/usr/bin/env python3
import hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];C=ROOT/"remotion-composer";REM=C/"node_modules/.bin/remotion";F,W,H=24,320,180
TS=("hard_cut","crossfade","subtle_zoom","directional_push","matched_motion","section_transition")
def run(c,cwd=ROOT,cap=False):
 p=subprocess.run([str(x) for x in c],cwd=cwd,text=True,capture_output=cap)
 if p.returncode:raise RuntimeError(" ".join(map(str,c))+"\n"+(p.stdout or "")+(p.stderr or ""))
 return p.stdout
def gen(d):
 a={n:d/n for n in ("r.png","b.png","v.png","r.mp4","b.mp4","n.wav","m.wav")}
 for n,c in (("r.png","red"),("b.png","blue")):run(["ffmpeg","-loglevel","error","-f","lavfi","-i",f"color={c}:s={W}x{H}","-frames:v","1","-y",a[n]])
 run(["ffmpeg","-loglevel","error","-f","lavfi","-i","color=green:s=100x300","-vf","drawbox=0:0:100:100:red:t=fill,drawbox=0:200:100:100:blue:t=fill","-frames:v","1","-y",a["v.png"]])
 for n,c,hz in (("r.mp4","red",330),("b.mp4","blue",440)):run(["ffmpeg","-loglevel","error","-f","lavfi","-i",f"color={c}:s={W}x{H}:r={F}:d=2.2","-f","lavfi","-i",f"sine={hz}:sample_rate=48000:duration=2.2","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest","-y",a[n]])
 for n,hz in (("n.wav",660),("m.wav",110)):run(["ffmpeg","-loglevel","error","-f","lavfi","-i",f"sine={hz}:sample_rate=48000:duration=2","-y",a[n]])
 return a
def src(p):return p.relative_to(C/"public").as_posix()
def profiles(t,a=False,vert=False):
 return {"voice":{"enabled":a,"volume":.42,"captions":{"enabled":False,"words_per_page":6,"font_size":20}},"music":{"enabled":a,"volume":.18,"fade_in_seconds":0,"fade_out_seconds":0,"loop":False,"ducking":{"enabled":False,"volume_multiplier":1}},"editing":{"motion":"static","transition":t,"transition_seconds":.25,"transition_mode":"contextual_v1","image_fit":"cover","video_fit":"cover","background_color":"#000","scale_from":1,"scale_to":1,"pan_x":0,"pan_y":0},"source_audio":{"default_mode":"original" if a else "muted","volume":.35,"ducking":{"enabled":False,"volume_multiplier":1}},"branding":{"enabled":False,"position":"top-right","opacity":1,"max_width":40,"safe_margin":4,"primary_color":"#fff","text_color":"#fff","caption_background_color":"#000","font_family":"Arial","title_font_size":20,"subtitle_font_size":12},"export":{"media_profile":"harness","width":H if vert else W,"height":W if vert else H,"fps":F}}
def photo(a,t,vert=False):
 cuts=[{"id":"r","source":src(a["r.png"]),"in_seconds":0,"out_seconds":1},{"id":"b","source":src(a["b.png"]),"in_seconds":1,"out_seconds":2,"transition_in":t,"transition_in_direction":"right"}]
 if vert:cuts=[{"id":"top","source":src(a["v.png"]),"in_seconds":0,"out_seconds":1,"transform":{"position":"center top"}},{"id":"bottom","source":src(a["v.png"]),"in_seconds":1,"out_seconds":2,"transition_in":"hard_cut","transform":{"position":"center bottom","crop":{"x":-20,"y":-20,"width":220,"height":360}}}]
 p=profiles(t,vert=vert);p["editing"].pop("video_fit");p.pop("source_audio");return {"cuts":cuts,"profiles":p,"audio":{},"captions":[]}
def hybrid(a,pair,t="crossfade",audio=False,short=False):
 d=.25 if short else 1;cuts=[]
 for i,m in enumerate(pair):
  k="r" if i==0 else "b";c={"media_type":m,"id":f"{m}{i}","source":src(a[k+(".png" if m=="photo" else ".mp4")])}
  if m=="photo":c["duration_seconds"]=d
  else:c.update(trim_in_seconds=0,trim_out_seconds=d,source_audio="original" if audio else "muted")
  if i:c.update(transition_in=t,transition_in_direction="right")
  cuts.append(c)
 if short:cuts.append({"media_type":"photo","id":"last","source":src(a["r.png"]),"duration_seconds":d,"transition_in":t,"transition_in_duration":2})
 x={"cuts":cuts,"profiles":profiles(t,audio),"audio":{},"captions":[]}
 if audio:x["audio"]={"narration":{"segments":[{"src":src(a["n.wav"]),"start_seconds":.25,"end_seconds":1.25}]},"music":{"src":src(a["m.wav"]),"offset_seconds":0}}
 return x
def browser_args():
 configured=os.environ.get("REMOTION_BROWSER_EXECUTABLE")
 if configured:
  path=Path(configured)
  if not path.is_file():raise SystemExit(f"REMOTION_BROWSER_EXECUTABLE does not exist: {path}")
  return [f"--browser-executable={path}"]
 for name in ("google-chrome","chromium","chromium-browser"):
  found=shutil.which(name)
  if found:return [f"--browser-executable={found}"]
 return []
def render(comp,p,o):
 j=o.with_suffix(".json");j.write_text(json.dumps(p));run([REM,"render","src/index.tsx",comp,o,f"--props={j}","--codec=h264","--audio-codec=aac","--crf=28","--concurrency=1","--log=error",*browser_args()],C)
def probe(p):return json.loads(run(["ffprobe","-v","error","-count_frames","-show_streams","-show_format","-of","json",p],cap=True))
def px(p,n,x=W//2,y=H//2):
 q=subprocess.run(["ffmpeg","-loglevel","error","-i",p,"-vf",f"select=eq(n\\,{n}),format=rgb24,crop=1:1:{x}:{y}","-frames:v","1","-f","rawvideo","-"],capture_output=True,check=True);assert len(q.stdout)==3;return tuple(q.stdout)
def check(p,n):
 i=probe(p);v=next(s for s in i["streams"] if s["codec_type"]=="video");assert int(v.get("nb_read_frames") or v["nb_frames"])==n
 assert abs(float(i["format"]["duration"])-n/F)<.11
 analysis=subprocess.run(["ffmpeg","-hide_banner","-i",str(p),"-vf","blackdetect=d=.02:pix_th=.02","-an","-f","null","-"],text=True,capture_output=True)
 if analysis.returncode:raise AssertionError("black-frame analysis failed\n"+analysis.stdout+analysis.stderr)
 log=analysis.stdout+analysis.stderr
 assert "black_start:" not in log,f"unintended black frame in {p.name}\n{log}"
 assert max(px(p,0))>24 and max(px(p,n-1))>24
def audiohash(p):
 q=subprocess.run(["ffmpeg","-loglevel","error","-i",p,"-map","0:a:0","-f","s16le","-"],capture_output=True,check=True);return hashlib.sha256(q.stdout).hexdigest()
def main():
 if not REM.is_file():raise SystemExit("run npm ci in this worktree remotion-composer")
 node_path=os.environ.get("NODE_PATH")
 if node_path and Path(node_path).resolve()!=(C/"node_modules").resolve():raise SystemExit("NODE_PATH must resolve to this worktree")
 d=Path(tempfile.mkdtemp(prefix="ct-render-",dir=C/"public"))
 try:
  a=gen(d);outs={}
  for t in TS:outs[t]=d/f"{t}.mp4";render("PhotoCoreV1",photo(a,t),outs[t]);check(outs[t],48)
  for t in TS[1:]:r,_,b=px(outs[t],21);assert r>20 and b>20,(t,r,b)
  assert px(outs["hard_cut"],23)[0]>100 and px(outs["hard_cut"],24)[2]>100
  pairs={"PHOTO_TO_PHOTO":("photo","photo"),"VIDEO_TO_VIDEO":("video","video"),"PHOTO_TO_VIDEO":("photo","video"),"VIDEO_TO_PHOTO":("video","photo")}
  for n,pair in pairs.items():
   o=outs["crossfade"] if n=="PHOTO_TO_PHOTO" else d/(n+".mp4")
   if n!="PHOTO_TO_PHOTO":render("HybridCoreV1",hybrid(a,pair),o)
   check(o,48);r,_,b=px(o,21);assert r>20 and b>20
  o=d/"short.mp4";render("HybridCoreV1",hybrid(a,("photo","video"),short=True),o);check(o,18)
  o=d/"vertical.mp4";render("PhotoCoreV1",photo(a,"hard_cut",True),o);check(o,48)
  top,bottom=px(o,12,H//2,8),px(o,36,H//2,W-9);assert top[0]>top[2] and bottom[2]>bottom[0]
  for f in (12,36):
   for x,y in ((0,0),(H-1,0),(0,W-1),(H-1,W-1)):assert max(px(o,f,x,y))>24
  x,y=d/"audio-x.mp4",d/"audio-control.mp4";render("HybridCoreV1",hybrid(a,("video","video"),audio=True),x);render("HybridCoreV1",hybrid(a,("video","video"),"hard_cut",True),y)
  for o in (x,y):
   check(o,48);s=[z for z in probe(o)["streams"] if z["codec_type"]=="audio"];assert len(s)==1 and abs(float(s[0]["duration"])-2)<.05
  assert audiohash(x)==audiohash(y),"visual overlap shifted audio"
  print("CONTEXTUAL_REMOTION_RENDER_HARNESS=PASS");print(json.dumps({"remotion":str(REM),"transitions":TS,"boundaries":tuple(pairs),"frame_count":True,"black_frames":True,"audio_timing":True,"crop_object_position":True,"vertical_cover":True},sort_keys=True))
 finally:shutil.rmtree(d,ignore_errors=True)
if __name__=="__main__":main()
