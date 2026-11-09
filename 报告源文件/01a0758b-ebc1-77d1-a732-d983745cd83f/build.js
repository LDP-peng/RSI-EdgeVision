
const fs=require('fs');
const dir=__dirname;
let head=fs.readFileSync(dir+'\\rpt_head.html','utf8');

// ---- CSS 微调：页边距 / 页眉页脚 / 行距 / 密度 ----
const R=[
  ['padding:25mm 30mm 22mm','padding:25mm 30mm 25mm'],
  ['.rhead{position:absolute;top:12mm','.rhead{position:absolute;top:13mm'],
  ['.rfoot{position:absolute;bottom:10mm','.rfoot{position:absolute;bottom:13mm'],
  ['font-size:12pt;line-height:1.5}','font-size:12pt;line-height:1.36}'],
  ['p{margin:5px 0;','p{margin:2px 0;'],
  ['h1{font-size:16pt;font-weight:700;margin:2px 0 6px;','h1{font-size:16pt;font-weight:700;margin:2px 0 5px;'],
  ['h2{font-size:14pt;font-weight:700;margin:14px 0 5px;','h2{font-size:14pt;font-weight:700;margin:9px 0 3px;'],
  ['h3{font-size:12pt;font-weight:700;margin:10px 0 4px}','h3{font-size:12pt;font-weight:700;margin:7px 0 2px}'],
  ['ul,ol{margin:5px 0 5px 0;padding-left:2em}li{margin:3px 0;','ul,ol{margin:4px 0 4px 0;padding-left:2em}li{margin:1px 0;'],
  ['.tip{border-left:4px solid var(--cyan);background:#f0faf8;padding:8px 12px;margin:9px 0;',
   '.tip{border-left:4px solid var(--cyan);background:#f0faf8;padding:5px 11px;margin:6px 0;'],
  ['.cards{display:flex;gap:8px;margin:9px 0}','.cards{display:flex;gap:8px;margin:6px 0}'],
  ['.card{flex:1;border:1px solid var(--line);border-radius:8px;padding:9px 6px;','.card{flex:1;border:1px solid var(--line);border-radius:8px;padding:6px 5px;'],
  ['table{width:100%;border-collapse:collapse;margin:8px 0;','table{width:100%;border-collapse:collapse;margin:6px 0;'],
  ['th,td{border:1px solid var(--line);padding:5px 8px;','th,td{border:1px solid var(--line);padding:3.5px 6.5px;'],
  ['figure{margin:9px 0}','figure{margin:5px 0}'],
  ['figcaption{font-size:9.5pt;color:var(--sub);margin-top:5px;','figcaption{font-size:9.5pt;color:var(--sub);margin-top:3px;'],
  ['.flow .st{flex:1;border:1px solid var(--line);border-radius:7px;padding:7px 6px;','.flow .st{flex:1;border:1px solid var(--line);border-radius:7px;padding:5px 4px;'],
  ['.flow{display:flex;align-items:stretch;gap:0;margin:9px 0}','.flow{display:flex;align-items:stretch;gap:0;margin:6px 0}'],
  ['.lblrow{display:flex;gap:8px;margin:8px 0 -4px}','.lblrow{display:flex;gap:8px;margin:6px 0 -4px}'],
  ['.panel{background:#0d1626;border-radius:8px;padding:8px}','.panel{background:#0d1626;border-radius:8px;padding:7px}'],
];
for(const [a,b] of R){ if(!head.includes(a)) throw new Error('CSS anchor not found: '+a); head=head.replace(a,b); }

const svgs=[0,1,2].map(i=>fs.readFileSync(dir+'\\svg'+i+'.svg','utf8'));

let body='';
for(let i=1;i<=7;i++) body+=fs.readFileSync(dir+'\\p'+i+'.html','utf8');

// ---- 去掉重复的一级标题（同一标题只保留首次出现） ----
const seen=new Set();
body=body.replace(/<h1 class="bar">([^<]+)<\/h1>\s*/g,(m,txt)=>{
  if(seen.has(txt)) return '';
  seen.add(txt); return m;
});

// ---- 把 panel + figcaption 包进 figure，并插入 SVG ----
body=body.replace(/<div class="panel">\s*<!--SVG(\d)-->\s*<\/div>\s*<figcaption>([\s\S]*?)<\/figcaption>/g,
  (m,i,cap)=>'<figure><div class="panel">'+svgs[+i]+'</div><figcaption>'+cap+'</figcaption></figure>');

// ---- 图片内联为 data URI ----
body=body.replace(/<!--IMG:([^>]+?)-->/g,(m,f)=>{
  const b=fs.readFileSync(dir+'\\'+f);
  const mime=/\.jpe?g$/i.test(f)?'image/jpeg':'image/png';
  return 'data:'+mime+';base64,'+b.toString('base64');
});

const html=head+body+'\n</body></html>\n';
fs.writeFileSync(dir+'\\rpt.html',html,'utf8');
const left=(html.match(/<!--SVG\d-->|<!--IMG:/g)||[]).length;
console.log('rpt.html bytes='+Buffer.byteLength(html),'pages='+(html.match(/class="page/g)||[]).length,'unreplaced='+left);
