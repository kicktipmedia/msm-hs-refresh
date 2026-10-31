/* next103: Top 25 submenu + homepage expand controls */
(function(){
[].forEach.call(document.querySelectorAll('.ndd'),function(d){var b=d.querySelector('.ndt');if(!b)return;
 function set(o){d.classList.toggle('open',o);b.setAttribute('aria-expanded',o?'true':'false')}
 b.addEventListener('click',function(e){e.stopPropagation();set(!d.classList.contains('open'))});
 d.addEventListener('keydown',function(e){if(e.key==='Escape'&&d.classList.contains('open')){set(false);b.focus()}});
 d.addEventListener('focusout',function(e){if(!d.contains(e.relatedTarget))set(false)});
 document.addEventListener('click',function(e){if(!d.contains(e.target))set(false)})});
[].forEach.call(document.querySelectorAll('.xbtn[data-x]'),function(b){var s=document.getElementById(b.getAttribute('data-x'));if(!s)return;
 var a=b.getAttribute('data-open'),c=b.textContent;s.classList.add('clp');
 b.addEventListener('click',function(){var o=s.classList.toggle('clp');b.setAttribute('aria-expanded',o?'false':'true');b.textContent=o?c:a})});
})();
