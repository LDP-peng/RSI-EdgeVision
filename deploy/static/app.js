// ===== 工具 =====
function $(id){return document.getElementById(id);}
function toast(msg){
  var t=$('toast'); t.textContent=msg; t.classList.add('show');
  clearTimeout(toast._t); toast._t=setTimeout(function(){t.classList.remove('show');},2600);
}
async function getJSON(url){var r=await fetch(url);return r.json();}
async function postJSON(url,body){var r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});return r.json();}
function downloadDataUrl(dataUrl,filename){var a=document.createElement('a');a.href=dataUrl;a.download=filename;document.body.appendChild(a);a.click();a.remove();}
function downloadText(text,filename,mime){
  var blob=new Blob([text],{type:mime||'text/plain'});
  var url=URL.createObjectURL(blob);
  var a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();
  setTimeout(function(){URL.revokeObjectURL(url);},2000);
}

// ===== 按住拖动滚动（适合鼠标式触摸屏） =====
function initDragScroll(){
  var dragging=false,moved=false,sx=0,sy=0,ssx=0,ssy=0;
  var lastX=0,lastY=0,lastT=0,velX=0,velY=0,anim=null;
  function shouldSkip(t){
    return t.closest('button,input,select,textarea,a,.compare,.hlbox,.lb-stage');
  }
  function pt(e){
    if(e.type==='touchstart'||e.type==='touchmove'){return{x:e.touches[0].clientX,y:e.touches[0].clientY};}
    return{x:e.clientX,y:e.clientY};
  }
  function start(e){
    if($('lightbox')&&$('lightbox').style.display!=='none')return;
    if(shouldSkip(e.target))return;
    if(anim){cancelAnimationFrame(anim);anim=null;}
    var p=pt(e);dragging=true;moved=false;velX=0;velY=0;
    sx=p.x;sy=p.y;lastX=p.x;lastY=p.y;lastT=performance.now();
    ssx=window.scrollX;ssy=window.scrollY;
  }
  function move(e){
    if(!dragging)return;
    var p=pt(e),t=performance.now();
    var dx=p.x-sx,dy=p.y-sy;
    if(!moved){if(Math.abs(dx)<6&&Math.abs(dy)<6)return;moved=true;}
    var dt=t-lastT;if(dt>0){velX=(p.x-lastX)/(dt/1000);velY=(p.y-lastY)/(dt/1000);}
    window.scrollTo(ssx-dx,ssy-dy);
    lastX=p.x;lastY=p.y;lastT=t;
    if(e.cancelable)e.preventDefault();
  }
  function end(){
    if(!dragging)return;dragging=false;moved=false;
    var vx=velX/60,vy=velY/60;
    if(Math.abs(vx)<1&&Math.abs(vy)<1)return;
    function step(){
      vx*=0.92;vy*=0.92;
      if(Math.abs(vx)<0.3&&Math.abs(vy)<0.3)return;
      window.scrollBy(-vx,-vy);
      anim=requestAnimationFrame(step);
    }
    anim=requestAnimationFrame(step);
  }
  document.addEventListener('mousedown',start);
  document.addEventListener('mousemove',move);
  document.addEventListener('mouseup',end);
  document.addEventListener('touchstart',start,{passive:true});
  document.addEventListener('touchmove',move,{passive:false});
  document.addEventListener('touchend',end);
}

// ===== 图片点击放大 =====
function initLightbox(){
  var lb=$('lightbox'),stage=$('lbStage'),img=$('lbImg'),cap=$('lbCap');
  if(!lb)return;
  var baseW=256,baseH=256,scale=1,tx=0,ty=0,movedInLB=false;
  function apply(){img.style.transform='translate('+tx+'px,'+ty+'px) scale('+scale+')';}
  function reset(){scale=1;tx=(stage.clientWidth-baseW)/2;ty=(stage.clientHeight-baseH)/2;apply();}
  function fit(){
    var sw=stage.clientWidth,sh=stage.clientHeight;
    var iw=img.naturalWidth||256,ih=img.naturalHeight||256;
    var s=Math.min(sw/iw,sh/ih);
    baseW=iw*s;baseH=ih*s;
    img.style.width=baseW+'px';img.style.height=baseH+'px';reset();
  }
  function zoomAt(factor,px,py){
    var ns=Math.max(0.4,Math.min(12,scale*factor));
    var k=ns/scale;
    tx=px-(px-tx)*k;ty=py-(py-ty)*k;scale=ns;apply();
  }
  function open(src,txt){
    img.src=src;cap.textContent=txt||'';lb.style.display='flex';movedInLB=false;
    if(img.complete){fit();}else{img.onload=fit;}
  }
  function close(){lb.style.display='none';movedInLB=false;}
  function stageXY(e){var r=stage.getBoundingClientRect();return {x:e.clientX-r.left,y:e.clientY-r.top};}

  document.querySelectorAll('.imgwrap img,.compare img').forEach(function(im){
    im.style.cursor='zoom-in';
    im.addEventListener('click',function(ev){
      ev.stopPropagation();
      var h3=im.closest('.img-card,.err-card');
      open(im.src,h3?h3.querySelector('h3').textContent.trim():'');
    });
  });
  lb.addEventListener('click',function(e){
    if((e.target===lb||e.target===stage)&&!movedInLB)close();
  });
  var c=$('lbClose');if(c)c.addEventListener('click',function(e){e.stopPropagation();close();});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});
  var bi=$('lbIn'),bo=$('lbOut'),br=$('lbReset');
  if(bi)bi.addEventListener('click',function(e){e.stopPropagation();zoomAt(1.25,stage.clientWidth/2,stage.clientHeight/2);});
  if(bo)bo.addEventListener('click',function(e){e.stopPropagation();zoomAt(0.8,stage.clientWidth/2,stage.clientHeight/2);});
  if(br)br.addEventListener('click',function(e){e.stopPropagation();reset();});

  stage.addEventListener('wheel',function(e){
    e.preventDefault();
    var p=stageXY(e);
    zoomAt(e.deltaY<0?1.12:0.9,p.x,p.y);
  },{passive:false});
  stage.addEventListener('dblclick',function(e){
    e.preventDefault();var p=stageXY(e);
    if(scale>1.01){reset();}else{zoomAt(2.2,p.x,p.y);}
  });

  var ptrs={},pan=null,pinch=null;
  stage.addEventListener('pointerdown',function(e){
    e.preventDefault();movedInLB=false;
    ptrs[e.pointerId]={x:e.clientX,y:e.clientY};
    var ids=Object.keys(ptrs);
    if(ids.length===1){
      var p=stageXY(e);pan={x:p.x,y:p.y,tx:tx,ty:ty};pinch=null;
    }else if(ids.length===2){
      var p1=ptrs[ids[0]],p2=ptrs[ids[1]];
      var a=stageXY({clientX:p1.x,clientY:p1.y}),b=stageXY({clientX:p2.x,clientY:p2.y});
      pinch={dist:Math.hypot(p2.x-p1.x,p2.y-p1.y),scale:scale,tx:tx,ty:ty,mx:(a.x+b.x)/2,my:(a.y+b.y)/2};
      pan=null;
    }
  });
  stage.addEventListener('pointermove',function(e){
    if(!ptrs[e.pointerId])return;
    e.preventDefault();movedInLB=true;
    ptrs[e.pointerId]={x:e.clientX,y:e.clientY};
    var ids=Object.keys(ptrs);
    if(ids.length===1&&pan){
      var p=stageXY(e);tx=pan.tx+(p.x-pan.x);ty=pan.ty+(p.y-pan.y);apply();
    }else if(ids.length===2&&pinch){
      var p1=ptrs[ids[0]],p2=ptrs[ids[1]];
      var a=stageXY({clientX:p1.x,clientY:p1.y}),b=stageXY({clientX:p2.x,clientY:p2.y});
      var mx=(a.x+b.x)/2,my=(a.y+b.y)/2;
      var dist=Math.hypot(p2.x-p1.x,p2.y-p1.y);
      var s=Math.max(0.4,Math.min(12,pinch.scale*dist/pinch.dist));
      var k=s/pinch.scale;
      tx=mx-(pinch.mx-pinch.tx)*k;ty=my-(pinch.my-pinch.ty)*k;scale=s;apply();
    }
  });
  function ptrEnd(e){
    if(ptrs[e.pointerId])delete ptrs[e.pointerId];
    var ids=Object.keys(ptrs);
    if(ids.length===0){pan=null;pinch=null;}
    else if(ids.length===1){
      var id=ids[0],p=stageXY({clientX:ptrs[id].x,clientY:ptrs[id].y});
      pan={x:p.x,y:p.y,tx:tx,ty:ty};pinch=null;
    }
  }
  stage.addEventListener('pointerup',ptrEnd);
  stage.addEventListener('pointercancel',ptrEnd);
}

// ===== 状态 =====
var currentName='';
var lastRegions=[];
var lastSize=256;
var lastEval=null;
var sysPoints=[];

// ===== 启动 =====
window.addEventListener('DOMContentLoaded',function(){
  bindEvents();
  initCompare();
  initDir();
  pollStatus();
  setInterval(pollStatus,1000);
  initDragScroll();
  initLightbox();
});

function bindEvents(){
  $('btnList').addEventListener('click',loadList);
  $('btnDetect').addEventListener('click',detect);
  $('btnEval').addEventListener('click',eval_);
  $('btnExplain').addEventListener('click',explain_);
  $('btnExport').addEventListener('click',export_);
  $('btnReport').addEventListener('click',exportReport);
  $('pairSel').addEventListener('change',loadPair);
  $('thresh').addEventListener('input',function(){$('threshVal').textContent=this.value;});
  $('dataDir').addEventListener('keydown',function(e){if(e.key==='Enter')loadList();});
  document.querySelectorAll('.nav[data-goto]').forEach(function(b){
    b.addEventListener('click',function(){
      document.querySelectorAll('.nav').forEach(function(x){x.classList.remove('active');});
      b.classList.add('active');
      var g=b.dataset.goto;
      if(g==='detect')$('imgMask').scrollIntoView({behavior:'smooth',block:'center'});
      else if(g==='eval')$('imgError').scrollIntoView({behavior:'smooth',block:'center'});
      else if(g==='model')document.querySelector('.cards').scrollIntoView({behavior:'smooth',block:'center'});
    });
  });
  $('btnShutdown').addEventListener('click',function(){
    if(confirm('确定要关机吗？\n为防止误操作，请回到终端执行：sudo poweroff')){toast('请在终端执行 sudo poweroff 关机');}
  });
}

function setBusy(b){
  ['btnList','btnDetect','btnEval','btnExplain','btnExport','btnReport'].forEach(function(id){$(id).disabled=b;});
  if(b){$('progress').style.width='72%';}else{$('progress').style.width='0%';}
}

// ===== 设备监控 =====
async function pollStatus(){
  try{
    var r=await getJSON('/api/status');
    if(!r.ok)return;
    $('cRuntime').textContent=r.runtime||'-';
    $('cModel').textContent=r.model||'-';
    $('cEngine').textContent=r.mock?'模拟(无依赖)':'Horizon/BPU';
    $('cDevice').textContent=(typeof r.temp==='number'&&!isNaN(r.temp))?(r.temp+' °C'):'-';
    $('cServer').textContent=r.ip||'-';
    pushSys(r.temp, r.mem, r.cpu);
  }catch(e){}
}
function pushSys(temp,mem,cpu){
  sysPoints.push({temp:(typeof temp==='number'&&!isNaN(temp))?temp:0, mem:mem||0, cpu:cpu||0});
  if(sysPoints.length>60)sysPoints.shift();
  drawSpark();
}
function drawSpark(){
  var cv=$('spark');if(!cv)return;
  var ctx=cv.getContext('2d');var W=cv.width,H=cv.height;
  ctx.clearRect(0,0,W,H);
  ctx.strokeStyle='rgba(80,150,220,.12)';ctx.lineWidth=1;
  for(var g=0;g<=4;g++){var y=g/4*H;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
  var n=sysPoints.length;if(n<2)return;
  // 固定范围，曲线平稳（温度0~90，内存/CPU 0~100）
  function line(key,color,maxv){
    ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();
    for(var i=0;i<n;i++){
      var x=n===1?0:i/(n-1)*W;
      var v=Math.max(0,Math.min(maxv,sysPoints[i][key]||0));
      var y=H-(v/maxv*H);
      if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
    }
    ctx.stroke();
  }
  line('temp','#38e1ff',90);
  line('mem','#5aa8ff',100);
  line('cpu','#b06bff',100);
}

// ===== 自动目录 =====
async function initDir(){
  try{
    var r=await getJSON('/api/default_dir');
    if(r.ok&&r.dir){$('dataDir').value=r.dir;loadList();return;}
  }catch(e){}
  loadList();
}

// ===== 读取目录 =====
async function loadList(){
  var dir=$('dataDir').value.trim();
  if(!dir){toast('请先填写数据目录');return;}
  setBusy(true);
  try{
    var r=await getJSON('/api/list?dir='+encodeURIComponent(dir));
    if(!r.ok)throw new Error(r.error||'读取目录失败');
    var names=r.names||[];
    var slice=names.slice(0,500);
    var sel=$('pairSel');
    sel.innerHTML='';
    if(slice.length===0){
      var o=document.createElement('option');o.value='';o.textContent='（无影像对）';sel.appendChild(o);
      toast('目录下没有 A/B 影像对');
    }else{
      slice.forEach(function(n){var o=document.createElement('option');o.value=n;o.textContent=n;sel.appendChild(o);});
      if(names.length>slice.length){
        var h=document.createElement('option');h.disabled=true;h.textContent='…共 '+names.length+' 对，显示前 500';sel.appendChild(h);
      }
      loadPair();
      toast('发现 '+names.length+' 对'+(names.length>slice.length?('，显示前 500'):''));
    }
  }catch(e){toast('读取失败: '+e.message);}
  finally{setBusy(false);}
}

// ===== 切换影像对 =====
function loadPair(){
  var name=$('pairSel').value;
  if(!name){currentName='';$('sourceInfo').textContent='当前数据源：未选择';return;}
  currentName=name;
  var dir=$('dataDir').value.trim();
  $('sourceInfo').textContent='当前数据源：'+name;
  var q='dir='+encodeURIComponent(dir)+'&name='+encodeURIComponent(name);
  $('imgA').src='/api/img?'+q+'&kind=A';
  $('imgB').src='/api/img?'+q+'&kind=B';
  $('imgLabel').src='/api/img?'+q+'&kind=label';
  $('imgLabel').onerror=function(){this.src='';$('capL').textContent='（无 label）';};
  $('capA').textContent='A / '+name;
  $('capB').textContent='B / '+name;
  $('capL').textContent='label / '+name;
  $('capM').textContent='-';$('capO').textContent='-';$('capP').textContent='-';
  $('imgMask').src='';$('imgOverlay').src='';$('imgProb').src='';$('imgError').src='';
  $('mPrec').textContent='-';$('mRec').textContent='-';$('mF1').textContent='-';$('mIoU').textContent='-';
  $('cmText').textContent='TP / FP / FN / TN：-';
  $('hlBox').style.display='none';
  $('regionList').innerHTML='<div class="region-empty">暂无区域</div>';
  lastRegions=[];lastSize=256;lastEval=null;
  syncCompare();
}

// ===== 对比滑杆 =====
function syncCompare(){
  $('compareA').src=$('imgA').src||'';
  $('compareB').src=$('imgB').src||'';
  $('compare').style.setProperty('--p','50%');
}
function initCompare(){
  var c=$('compare'),dragging=false;
  function setP(x){
    var r=c.getBoundingClientRect();
    var p=Math.max(0,Math.min(100,(x-r.left)/r.width*100));
    c.style.setProperty('--p',p+'%');
  }
  c.addEventListener('pointerdown',function(e){dragging=true;try{c.setPointerCapture(e.pointerId);}catch(_){}setP(e.clientX);e.preventDefault();});
  c.addEventListener('pointermove',function(e){if(dragging)setP(e.clientX);});
  c.addEventListener('pointerup',function(){dragging=false;});
  c.addEventListener('pointercancel',function(){dragging=false;});
}

// ===== 检测 =====
async function detect(){
  var name=currentName||$('pairSel').value;
  if(!name){toast('请先选择影像对');return;}
  var dir=$('dataDir').value.trim();
  var a=dir+'/A/'+name,b=dir+'/B/'+name;
  var thresh=parseFloat($('thresh').value);
  setBusy(true);
  try{
    var r=await postJSON('/api/detect',{a:a,b:b,thresh:thresh});
    if(!r.ok)throw new Error(r.error||'检测失败');
    $('imgA').src=r.a_img||'';$('imgB').src=r.b_img||'';
    $('imgOverlay').src=r.overlay||'';$('imgMask').src=r.mask||'';$('imgProb').src=r.prob||'';
    $('capM').textContent='预测变化占比 '+(r.stats.ratio*100).toFixed(1)+'%  区域 '+r.stats.num+' 处';
    $('capO').textContent='A/B 叠加，红色=变化';
    $('capP').textContent='概率热力图 (0~1)';
    lastSize=r.size||256;
    $('hlBox').style.display='none';
    renderRegions(r.stats.regions||[]);
    syncCompare();
    toast('检测完成'+(r.mock?'（模拟推理）':''));
  }catch(e){toast('检测失败: '+e.message);}
  finally{setBusy(false);}
}

// ===== 区域高亮 =====
function renderRegions(regions){
  lastRegions=regions;
  var box=$('regionList');
  if(!lastRegions.length){box.innerHTML='<div class="region-empty">无变化区域</div>';$('hlBox').style.display='none';return;}
  box.innerHTML='';
  lastRegions.forEach(function(r,i){
    var div=document.createElement('div');
    div.className='region-item';
    div.textContent='区域'+(i+1)+'：'+r.pos+'，面积 '+(r.area/(lastSize*lastSize)*100).toFixed(1)+'%';
    div.dataset.i=i;
    div.addEventListener('click',function(){highlightRegion(i);});
    box.appendChild(div);
  });
}
function highlightRegion(i){
  var r=lastRegions[i];if(!r)return;
  document.querySelectorAll('.region-item').forEach(function(el){el.classList.toggle('active',parseInt(el.dataset.i,10)===i);});
  var box=$('hlBox');
  box.style.display='block';
  box.style.left=(r.x/lastSize*100)+'%';
  box.style.top=(r.y/lastSize*100)+'%';
  box.style.width=(r.w/lastSize*100)+'%';
  box.style.height=(r.h/lastSize*100)+'%';
}

// ===== 评估 =====
async function eval_(){
  var name=currentName||$('pairSel').value;
  if(!name){toast('请先选择影像对');return;}
  var dir=$('dataDir').value.trim();
  var a=dir+'/A/'+name,b=dir+'/B/'+name,label=dir+'/label/'+name;
  var thresh=parseFloat($('thresh').value);
  setBusy(true);
  try{
    var r=await postJSON('/api/eval',{a:a,b:b,label:label,thresh:thresh});
    if(!r.ok)throw new Error(r.error||'评估失败');
    $('imgError').src=r.error_map||'';
    $('mPrec').textContent=(r.precision*100).toFixed(1)+'%';
    $('mRec').textContent=(r.recall*100).toFixed(1)+'%';
    $('mF1').textContent=(r.f1*100).toFixed(1)+'%';
    $('mIoU').textContent=(r.iou*100).toFixed(1)+'%';
    $('cmText').textContent='TP / FP / FN / TN：'+r.tp+' / '+r.fp+' / '+r.fn+' / '+r.tn;
    lastEval=r;
    toast('评估完成');
  }catch(e){toast('评估失败: '+e.message);}
  finally{setBusy(false);}
}

// ===== AI 解释 =====
async function explain_(){
  var name=currentName||$('pairSel').value;
  if(!name){toast('请先选择影像对');return;}
  var dir=$('dataDir').value.trim();
  var a=dir+'/A/'+name,b=dir+'/B/'+name;
  setBusy(true);
  $('explainBox').textContent='AI 解析中，请稍候…';
  try{
    var r=await postJSON('/api/explain',{a:a,b:b});
    if(!r.ok)throw new Error(r.error||'AI 调用失败');
    $('explainBox').textContent=r.text||'（无返回内容）';
    toast(r.ok?'AI 解析完成':'AI 返回异常');
  }catch(e){$('explainBox').textContent='AI 解析失败: '+e.message;toast('AI 失败: '+e.message);}
  finally{setBusy(false);}
}

// ===== 导出 =====
function buildCSV(name,thresh){
  var e=lastEval;
  var head=['name','threshold','precision','recall','f1','iou','tp','fp','fn','tn'];
  var vals=[name,thresh,
    e?e.precision.toFixed(4):'',
    e?e.recall.toFixed(4):'',
    e?e.f1.toFixed(4):'',
    e?e.iou.toFixed(4):'',
    e?e.tp:'',e?e.fp:'',e?e.fn:'',e?e.tn:''];
  return head.join(',')+'\n'+vals.join(',')+'\n';
}
async function export_(){
  var name=currentName||$('pairSel').value;
  if(!name){toast('请先选择影像对');return;}
  var dir=$('dataDir').value.trim();
  var a=dir+'/A/'+name,b=dir+'/B/'+name,label=dir+'/label/'+name;
  var thresh=parseFloat($('thresh').value);
  setBusy(true);
  try{
    var r=await postJSON('/api/export',{a:a,b:b,label:label,thresh:thresh});
    if(!r.ok)throw new Error(r.error||'导出失败');
    downloadDataUrl(r.image, name+'_report.png');
    downloadText(buildCSV(name,thresh), name+'_metrics.csv','text/csv');
    var ai=$('explainBox').textContent;
    if(ai && ai!=='尚未调用 AI'){downloadText(ai, name+'_ai.txt','text/plain');}
    toast('已导出报告图 + CSV'+(ai?' + AI文字':''));
  }catch(e){toast('导出失败: '+e.message);}
  finally{setBusy(false);}
}
// ===== 导出评估报告（HTML） =====
async function exportReport(){
  var dir=$('dataDir').value.trim();
  var thresh=parseFloat($('thresh').value);
  setBusy(true);
  toast('正在生成评估报告，请稍候…');
  try{
    var r=await postJSON('/api/report',{dir:dir,thresh:thresh,samples:3});
    if(!r.ok)throw new Error(r.error||'生成失败');
    window.open(r.url,'_blank');
    toast('评估报告已生成');
  }catch(e){toast('报告生成失败: '+e.message);}
  finally{setBusy(false);}
}

// ===== 工具栏按钮点击闪光反馈 =====
document.addEventListener('click',function(e){
  if(!e.target)return;
  var b=e.target.closest?e.target.closest('.toolbar .btn'):null;
  if(b){b.classList.add('on');setTimeout(function(){b.classList.remove('on');},360);}
});
