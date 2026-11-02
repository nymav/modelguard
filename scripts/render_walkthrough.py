"""Render a captioned offline evidence walkthrough, not a staged live recording.

Dev-only requirements: Pillow and imageio-ffmpeg. No provider requests are made.
Screenshots are captured from the actual local reports using browser tooling.
"""
from pathlib import Path
import argparse
import json
import textwrap
import subprocess
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg

parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[1];assets=root/'artifacts/walkthrough-assets';assets.mkdir(exist_ok=True)
W,H=1920,1080
fontpath='/System/Library/Fonts/Supplemental/Arial.ttf';mono='/System/Library/Fonts/Menlo.ttc'
if not Path(fontpath).exists():fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
if not Path(mono).exists():mono='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
font=lambda n:ImageFont.truetype(fontpath,n)
mfont=lambda n:ImageFont.truetype(mono,n)
ink='#23312e';muted='#6f7c77';green='#2f6d56';line='#d8e1dc'
demo=json.loads((root/'artifacts/walkthrough-demo/demo.json').read_text())
comp=json.loads((root/'artifacts/walkthrough-demo/regression/comparison.json').read_text())
drift=json.loads((root/'artifacts/walkthrough-demo/slow-drift-fixture.json').read_text())
remote=json.loads((root/'artifacts/activation/remote-pr-evidence.json').read_text())
comments=[c for c in remote['comments'] if 'modelguard:release-gate:v1' in c.get('body','')]
assert len(comments)==1,'Expected real bot upsert evidence'
chapters=[]
def canvas(index,title,subtitle):
 im=Image.new('RGB',(W,H),'#f7f9f6');d=ImageDraw.Draw(im)
 d.rectangle((0,0,W,72),fill='#243b31');d.text((65,18),'MODEL GUARD',font=font(25),fill='#ffffff')
 d.text((1370,23),'OFFLINE EVIDENCE WALKTHROUGH',font=mfont(16),fill='#b9cebf')
 d.text((70,109),f'{index:02d}  /  09',font=mfont(17),fill='#819286')
 d.text((70,150),title,font=font(42),fill=ink);d.text((70,216),subtitle,font=font(23),fill=muted)
 d.line((70,985,1850,985),fill=line,width=2)
 d.text((70,1006),'Scripted model outputs; actual evaluator, report and GitHub integration evidence.',font=font(19),fill=muted)
 d.text((1625,1006),f'{(index-1)*20//60:02d}:{(index-1)*20%60:02d} - {index*20//60:02d}:{index*20%60:02d}',font=mfont(17),fill=muted)
 return im,d

def textblock(d,text,y=300,width=110,size=25,color=ink,x=90,gap=47):
 rows=[row for raw in text.splitlines() for row in (textwrap.wrap(raw,width=width,replace_whitespace=False) or [''])]
 gap=min(gap,max(20,int((940-y)/max(1,len(rows)))))
 size=min(size,max(16,int(gap*.75)))
 for row in rows:
  d.text((x,y),row,font=font(size),fill=color);y+=gap
 return y

def save(index,title,subtitle,body=None,screenshot=None):
 im,d=canvas(index,title,subtitle)
 if body:textblock(d,body)
 if screenshot:
  capture=Image.open(assets/screenshot).convert('RGB');capture.thumbnail((1760,680))
  im.paste(capture,((W-capture.width)//2,285))
 name=f'chapter-{index:02d}.png';im.save(assets/name);chapters.append({'start':(index-1)*20,'duration':20,'title':title,'image':name})

save(1,'What this system checks','ModelGuard 0.2.0 - project P01',
 'A versioned prompt classifies support emails and summarizes their intent.\n\nA candidate is compared against the same cases and scoring policy as its baseline.\n\nThis walkthrough uses 16 synthetic system-test scenarios and scripted responses.\n\nIt demonstrates software behavior. It does not claim live model accuracy, human-reviewed gold, or a delivered Slack alert.')
console=json.dumps(json.loads((root/'artifacts/activation/demo-console.json').read_text()),indent=2)
im,d=canvas(2,'Run the actual evaluation path','The command below was executed locally without external API access.')
d.rounded_rectangle((75,290,1845,940),radius=9,fill='#1f2d29')
d.text((105,314),'$ modelguard demo --output artifacts/walkthrough-demo',font=mfont(23),fill='#aed5b4')
y=368
for row in console.splitlines():
 if len(row)>115:row=row[:112]+'...'
 d.text((105,y),row,font=mfont(21),fill='#e0e8e2');y+=29
im.save(assets/'chapter-02.png');chapters.append({'start':20,'duration':20,'title':'Run the actual evaluation path','image':'chapter-02.png'})
save(3,'Inspect the regression report','Actual generated HTML. Every regressed case has an old and new output.',screenshot='regression.jpg')
old={c['case_id']:c for c in comp['baseline']['cases']};new={c['case_id']:c for c in comp['candidate']['cases']}
rows=['Baseline: 13/16 passed. Candidate: 10/16 passed. Delta: -18.75 percentage points.','']
for case in comp['comparison']['regressions']:rows.append(f"{case}: {old[case]['prediction']['category']} -> {new[case]['prediction']['category']}")
rows+=['','Four regressions and one improvement trigger the configured practical gate.','The paired exact p-value is 0.375. Critical severity is not a claim of statistical significance.']
save(4,'Follow individual failures','A single accuracy number would hide which behavior changed.','\n'.join(rows))
save(5,'Check a recovery against the same baseline','Actual saved recheck: 15/16 passed; no new regressions relative to baseline.',screenshot='recovery.jpg')
save(6,'Catch a gradual decline','A separate, explicitly configured system-test sequence.',
 f"Seven runs. Moving average: {100*drift['result']['moving_average']:.2f}%. Floor: 93%.\n\nIndividual step statuses: {', '.join(drift['individual_step_statuses'])}.\n\nThe small fixture changes in 6.25-point increments, so this test explicitly uses a 7-point warning threshold. It is not a live production trend.\n\nCI persistence now stores aggregate rates and identity metadata only. Emails and raw outputs are not placed in the history cache.")
body=comments[0]['body'].replace('<!-- modelguard:release-gate:v1 -->\n','').replace('## ','')
save(7,'Verify the real pull-request integration','The same bot comment was updated after a second run; no duplicate was posted.',body+'\n\nThis is an actual BLOCKED result. It is not a model-quality approval.')
save(8,'Prepare genuine human-reviewed data','A 64-row blank authoring file is supplied. No real cases are approved yet.',
 '1. People author or lawfully source emails, labels, summaries and rationale.\n\n2. dataset-import creates a review queue with no automatic approvals.\n\n3. dataset-review requires individual decisions in an interactive terminal.\n\n4. dataset-freeze requires 50-100 reviewed cases across all four categories.\n\nChanging case content invalidates its approval hash. Human identity remains a declaration, not an independently verified fact.')
save(9,'What remains before live activation','Implementation is testable. Missing prerequisites remain visible.',
 'OpenAI API key and explicit classifier/judge model IDs.\n\nA genuinely human-authored and reviewed golden dataset.\n\nA Slack incoming webhook for an actual delivered alert.\n\nAn eligible GitHub plan for enforced checks on this private repository.\n\nP04 was left untouched. P01 remains private and MIT licensed.\n\nThis is a captioned evidence walkthrough, not a Loom upload or a fabricated live deployment.')
# Every scene lasts 20 seconds: nine scenes give exactly three minutes.
concat=assets/'chapters.ffconcat'
concat.write_text('ffconcat version 1.0\n'+''.join(f"file '{c['image']}'\nduration 20\n" for c in chapters)+f"file '{chapters[-1]['image']}'\n")
args.output.parent.mkdir(parents=True,exist_ok=True)
command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-t','180','-vf','fps=15,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','21','-movflags','+faststart',str(args.output)]
subprocess.run(command,check=True)
manifest={'kind':'captioned offline evidence walkthrough','duration_seconds':180,'resolution':[W,H],
 'audio':False,'live_provider_calls':0,'slack_delivery_performed':False,'pr_comment':comments[0]['url'],
 'chapters':chapters,'source':'actual local CLI outputs, browser report screenshots and GitHub API evidence'}
(assets/'walkthrough-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'video':str(args.output),'seconds':180,'chapters':len(chapters)}))
