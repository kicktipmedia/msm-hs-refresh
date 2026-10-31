(function(){var t=document.querySelector('.ticker[data-lvl=hs]');if(!t)return;var n=Date.now(),W=3*36e5;
var up=[].slice.call(t.querySelectorAll('[data-kt]')).filter(function(s){return new Date(s.dataset.kt).getTime()+W<n});
up.forEach(function(s){s.remove()});
if(t.querySelector('.tkh [data-kt]'))return;
var f=t.querySelectorAll('template.tkf');if(f.length&&f[0].innerHTML.trim()){t.querySelectorAll('.tkh').forEach(function(h){h.innerHTML=f[0].innerHTML});return}
t.hidden=true})();
