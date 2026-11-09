
const fs=require('fs'); const dir=__dirname;
let src=fs.readFileSync(dir+'\\rpt.html','utf8');
src=src.replace('</body>', '<script>(function(){var st=document.createElement("style");st.textContent=".page{min-height:0 !important}";document.head.appendChild(st);var out=[];document.querySelectorAll(".page").forEach(function(p,i){var r=p.getBoundingClientRect();out.push("P"+(i+1)+"="+(r.height/3.7795).toFixed(0));});var d=document.createElement("pre");d.id="PROBE";d.textContent="##"+out.join(" | ")+"##";document.body.appendChild(d);})();<\/script></body>');
fs.writeFileSync(dir+'\\probe.html',src,'utf8');
console.log('probe ok');
