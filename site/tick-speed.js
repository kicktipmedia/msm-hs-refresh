/* next90b: all tickers scroll at the same on-screen speed. Duration = one copy width / PXS. */
(function(){var PXS=62.7;
function fit(d){var w=d.scrollWidth/2;if(!(w>0))return;var dur=(w/PXS).toFixed(2)+'s';if(d.style.getPropertyValue('animation-duration')!==dur)d.style.setProperty('animation-duration',dur,'important')}
function all(){document.querySelectorAll('.ticker>div').forEach(fit)}
function init(){all();if(document.fonts&&document.fonts.ready)document.fonts.ready.then(all);window.addEventListener('resize',all);window.addEventListener('load',all);
 if(window.ResizeObserver){var ro=new ResizeObserver(all);document.querySelectorAll('.ticker>div').forEach(function(d){ro.observe(d)})}
 if(window.MutationObserver){var mo=new MutationObserver(function(){requestAnimationFrame(all)});document.querySelectorAll('.ticker>div').forEach(function(d){mo.observe(d,{childList:true,subtree:true,characterData:true})})}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init()})();
