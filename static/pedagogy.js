// Source unique des méthodes pédagogiques : utilisée par le test ET par /admin.
(function(global){
function hfmt(n){
  if(n===undefined||n===null)return '';
  let x=Number(n); if(!Number.isFinite(x))return String(n);
  return String(Math.round(x*1000000)/1000000).replace('.',',');
}
function helpBox(content,tip){return {html:content,tip}}
function placeValueHelp(a,b,op){
  let au=Math.abs(a)%10, at=Math.floor(Math.abs(a)/10), bu=Math.abs(b)%10, bt=Math.floor(Math.abs(b)/10), r=op==='+'?a+b:a-b;
  let ru=Math.abs(r)%10, rt=Math.floor(Math.abs(r)/10);
  return `<div class="place-grid"><div class="place-head">Dizaines</div><div class="place-head">Unités</div><div class="place-cell">${at}</div><div class="place-cell">${au}</div><div class="place-cell">${op} ${bt}</div><div class="place-cell">${op} ${bu}</div><div class="place-cell changed">${rt}</div><div class="place-cell">${ru}</div></div><div class="help-step">${a} ${op} ${b} <span class="help-arrow">→</span> ${r}</div>`;
}
function contextualHelp(q){
  const p=q.payload||{}, k=q.kind, a=Number(p.a), b=Number(p.b), n=Number(p.n), d=Number(p.divisor), dividend=Number(p.dividend);
  if(k==='tens'||k==='tens_sub'){
    const op=k==='tens'?'+':'−', r=k==='tens'?a+b:a-b;
    return helpBox(placeValueHelp(a,b,k==='tens'?'+':'-'),`${b} représente ${Math.abs(b/10)} dizaine${Math.abs(b/10)>1?'s':''}. On change les dizaines, mais le chiffre des unités reste ${Math.abs(a)%10}.`);
  }
  if(k==='addition'){
    let to10=10-(a%10||10);
    if(a%10!==0 && b>to10 && to10>0){let rest=b-to10,r=a+b;return helpBox(`<div class="help-step"><span class="help-split">${b} = ${to10} + ${rest}</span></div><div class="help-step">${a} + ${to10} <span class="help-arrow">→</span> ${a+to10}</div><div class="help-step">${a+to10} + ${rest} <span class="help-arrow">→</span> ${r}</div>`,`On fabrique d’abord la dizaine ronde ${a+to10}. C’est souvent plus facile pour calculer de tête.`)}
    let tens=Math.floor(b/10)*10, units=b-tens,r=a+b;return helpBox(`<div class="help-step"><span class="help-split">${b} = ${tens} + ${units}</span></div><div class="help-step">${a} + ${tens} <span class="help-arrow">→</span> ${a+tens}</div>${units?`<div class="help-step">${a+tens} + ${units} <span class="help-arrow">→</span> ${r}</div>`:''}`,`Découpe le deuxième nombre en dizaines et unités, puis ajoute-les l’une après l’autre.`)
  }
  if(k==='subtraction'){
    let tens=Math.floor(b/10)*10, units=b-tens,r=a-b;
    if(b<10 && a%10<b){let down=a%10, rest=b-down;return helpBox(`<div class="help-step"><span class="help-split">${b} = ${down} + ${rest}</span></div><div class="help-step">${a} − ${down} <span class="help-arrow">→</span> ${a-down}</div><div class="help-step">${a-down} − ${rest} <span class="help-arrow">→</span> ${r}</div>`,`Descends d’abord jusqu’à la dizaine ronde, puis enlève ce qui reste.`)}
    return helpBox(`<div class="help-step"><span class="help-split">${b} = ${tens} + ${units}</span></div><div class="help-step">${a} − ${tens} <span class="help-arrow">→</span> ${a-tens}</div>${units?`<div class="help-step">${a-tens} − ${units} <span class="help-arrow">→</span> ${r}</div>`:''}`,`Enlève d’abord les dizaines, puis les unités.`)
  }
  if(k==='double'){
    let x=Number(n), tens=Math.floor(x/10)*10, units=x-tens;
    // Une seule pédagogie, déterminée par le nombre affiché et non par la catégorie
    // technique qui l'a généré. Ainsi un même type de double reçoit toujours la même aide.
    if(x>=10&&units){return helpBox(`<div class="help-step">${x} + ${x}</div><div class="help-step">= (${tens} + ${units}) + (${tens} + ${units})</div><div class="help-step">= ${tens} + ${tens} + ${units} + ${units}</div><div class="help-step">= double de ${tens} + double de ${units}</div><div class="help-step">= ${tens*2} + ${units*2} <span class="help-arrow">→</span> ${x*2}</div>`,`Sépare les dizaines et les unités : double les dizaines, double les unités, puis additionne les deux résultats.`)}
    if(x>=10){let d=x/10;return helpBox(`<div class="help-step">${x} = ${d} dizaine${d>1?'s':''}</div><div class="help-step">Double de ${d} dizaine${d>1?'s':''} = ${d*2} dizaines</div><div class="help-step">${d*2} dizaines <span class="help-arrow">→</span> ${x*2}</div>`,`Calcule le double pour les dizaines et ajoute le zéro des unités.`)}
    return helpBox(`<div class="help-step">${x} + ${x} <span class="help-arrow">→</span> ${x*2}</div>`,`Un double, c’est deux fois le même nombre.`)
  }
  if(k==='half'){
    let x=n,tens=Math.floor(x/10)*10,units=x-tens;
    // Pour une dizaine « impaire » (30, 50, 70, 90), on revient à la dizaine
    // précédente dont la moitié est immédiate, puis on ajoute la moitié de 10.
    if(x>=30 && x%20===10){let previous=x-10;return helpBox(`<div class="help-step"><span class="help-split">${x} = ${previous} + 10</span></div><div class="help-step">Moitié de ${x} = moitié de ${previous} + moitié de 10</div><div class="help-step">= ${previous/2} + 5 <span class="help-arrow">→</span> ${x/2}</div>`,`Prends la dizaine précédente : découpe ${x} en ${previous} + 10. Calcule la moitié de chaque morceau, puis additionne.`)}
    if(x>=20 && tens%20===0 && units%2===0){return helpBox(`<div class="help-step"><span class="help-split">${x} = ${tens} + ${units}</span></div><div class="help-step">${tens} ÷ 2 = ${tens/2}</div>${units?`<div class="help-step">${units} ÷ 2 = ${units/2}</div>`:''}<div class="help-step">${tens/2}${units?` + ${units/2}`:''} <span class="help-arrow">→</span> ${x/2}</div>`,`Partage chaque morceau en deux parts égales.`)}
    return helpBox(`<div class="groups"><span class="group-box">${x/2}</span><span class="group-box">${x/2}</span></div><div class="help-step">${x} ÷ 2 <span class="help-arrow">→</span> ${x/2}</div>`,`Cherche deux parts identiques qui, ensemble, redonnent ${x}.`)
  }
  if(k==='round_tens_add'){
    return helpBox(`<div class="help-step">${a} + ${b}</div><div class="help-step">${a} <span class="help-arrow">→</span> ${a+b}</div>`,`Pars de la dizaine ronde ${a} et ajoute ${b}.`)
  }
  if(k==='complement_tens'){
    let target=Number(p.target),missing=target-a;
    if(missing>10){let nextTen=Math.ceil(a/10)*10;if(nextTen===a)nextTen=a+10;let first=nextTen-a,second=target-nextTen;return helpBox(`<div class="help-jump"><div class="jump-label jump-label-1">+${first}</div><div class="jump-label jump-label-2">+${second}</div><div class="jump-line"><span>${a}</span><span class="jump-arrow">→</span><span>${nextTen}</span><span class="jump-arrow">→</span><span>${target}</span></div></div><div class="help-step">${first} + ${second} <span class="help-arrow">→</span> ${missing}</div><div class="help-step">${a} + ${missing} = ${target}</div>`,`Repère d’abord la dizaine supérieure à ${a} : c’est ${nextTen}. Saute de ${a} à ${nextTen} (+${first}), puis de ${nextTen} à ${target} (+${second}). Additionne les deux sauts.`)}
    return helpBox(`<div class="help-step">${a} <span class="help-arrow">→</span> ${target}</div><div class="help-step">Il manque <span class="help-split">${missing}</span></div><div class="help-step">${a} + ${missing} = ${target}</div>`,`Cherche l’écart entre ${a} et ${target}.`)
  }
  if(k==='place_value'){
    let f=p.factors||{}, order=(p.order||['m','c','d','u']).filter(x=>f[x]), parts=order.map(x=>`${f[x]}${x}`), values={m:1000,c:100,d:10,u:1};
    let detail=order.map(x=>`${f[x]} × ${values[x]} = ${f[x]*values[x]}`).join('<br>');
    return helpBox(`<div class="help-note"><strong>c</strong> = centaines, <strong>d</strong> = dizaines, <strong>u</strong> = unités.<br><strong>1c = 100 &nbsp; 1d = 10 &nbsp; 1u = 1</strong></div><div class="help-step">${parts.join(' ')}</div><div class="help-step">${detail}</div>`,`Lis chaque lettre avant de calculer : c vaut 100, d vaut 10 et u vaut 1.`)
  }
  if(k==='addition3'){
    let ns=p.numbers||[], x=Number(ns[0]),y=Number(ns[1]),z=Number(ns[2]);return helpBox(`<div class="help-step">${x} + ${y} = ${x+y}</div><div class="help-step">${x+y} + ${z} <span class="help-arrow">→</span> ${x+y+z}</div>`,`Additionne deux nombres, puis ajoute le troisième.`)
  }
  if(k==='multiple_of'){
    let factor=Number(p.factor)||(/Quadruple/i.test(q.display)?4:3), word=factor===3?'triple':'quadruple';
    let explanation=factor===3?'Tripler un nombre, c’est le multiplier par 3.':'Quadrupler un nombre, c’est le multiplier par 4.';
    return helpBox(`<div class="help-step">${factor} × ${n} <span class="help-arrow">→</span> ${factor*n}</div>`,explanation)
  }
  if(k==='fraction'){
    let divisor=Number(p.divisor)||(/Quart/i.test(q.display)?4:3), qn=n/divisor, word=divisor===3?'tiers':'quart';return helpBox(`<div class="help-step">${n} ÷ ${divisor} <span class="help-arrow">→</span> ${qn}</div>`,`Le ${word} d’un nombre, c’est le partager en ${divisor} parts égales.`)
  }
  if(k==='multiplication'){
    let x=a,y=b; if(x>y){let t=x;x=y;y=t} // x = petit facteur / stratégie
    if([10,100,1000].includes(x)||[10,100,1000].includes(y)){let m=[10,100,1000].includes(x)?x:y,base=m===x?y:x,steps=Math.round(Math.log10(m)),zeros='0'.repeat(steps);return helpBox(`<div class="help-step">${hfmt(base)} × ${m}</div><div class="decimal-track">${hfmt(base)} <span class="help-arrow">→</span> ${hfmt(base*m)}</div><div class="help-note">Ajoute ${steps} zéro${steps>1?'s':''} à droite.</div>`,`Pour multiplier un entier par ${m}, ajoute ${steps} zéro${steps>1?'s':''} à droite.`)};
    if(x===9){return helpBox(`<div class="help-step">10 × ${y} = ${10*y}</div><div class="help-step">${10*y} − ${y} <span class="help-arrow">→</span> ${9*y}</div>`,`× 9, c’est × 10 puis enlever une fois le nombre.`)}
    if(x===5){return helpBox(`<div class="help-step">10 × ${y} = ${10*y}</div><div class="help-step">Moitié de ${10*y} <span class="help-arrow">→</span> ${5*y}</div>`,`× 5, c’est la moitié de × 10.`)}
    if(x===4){return helpBox(`<div class="help-step">Double de ${y} = ${2*y}</div><div class="help-step">Double de ${2*y} <span class="help-arrow">→</span> ${4*y}</div>`,`× 4, c’est doubler deux fois.`)}
    if(x===6||x===7||x===8){let extra=x-5;return helpBox(`<div class="help-step">5 × ${y} = ${5*y}</div><div class="help-step">${extra} × ${y} = ${extra*y}</div><div class="help-step">${5*y} + ${extra*y} <span class="help-arrow">→</span> ${x*y}</div>`,`Pars de 5 × ${y}, puis ajoute ${extra} fois ${y}.`)}
    return helpBox(`<div class="groups">${Array.from({length:Math.min(x,10)},()=>`<span class="group-box">${y}</span>`).join('')}</div><div class="help-step">${x} groupes de ${y} <span class="help-arrow">→</span> ${x*y}</div>`,`Imagine ${x} groupes contenant chacun ${y}.`)
  }
  if(k==='division'){
    let qn=dividend/d;return helpBox(`<div class="help-step">${hfmt(dividend)} ÷ ${hfmt(d)} = ?</div><div class="help-step">${hfmt(d)} × ? = ${hfmt(dividend)}</div><div class="help-step">${hfmt(d)} × ${hfmt(qn)} = ${hfmt(dividend)}</div>`,`Retourne la division : cherche dans la table de ${hfmt(d)} le nombre qui donne ${hfmt(dividend)}.`)
  }
  if(k==='decimal_multiplication'){
    let m=b,steps=Math.round(Math.log10(m)); if([10,100,1000].includes(m)){
      if(Number.isInteger(a)){
        return helpBox(`<div class="help-step">${hfmt(a)} × ${m}</div><div class="decimal-track">${hfmt(a)} <span class="help-arrow">→</span> ${hfmt(a*m)}</div><div class="help-note">Ajoute ${steps} zéro${steps>1?'s':''} à droite.</div>`,`Pour multiplier un entier par ${m}, ajoute ${steps} zéro${steps>1?'s':''} à droite.`)
      }
      let vals=[a];for(let i=0;i<steps;i++)vals.push(vals[vals.length-1]*10);
      return helpBox(`<div class="decimal-track">${vals.map(hfmt).join('  →  ')}</div><div class="decimal-arrow">${'→ '.repeat(steps)}</div><div class="help-note">Déplace la virgule ${steps} fois vers la droite.</div>`,`Pour multiplier un nombre décimal par ${m}, déplace la virgule ${steps} fois vers la droite.`)
    }
  }
  if(k==='decimal_division'){
    let steps=Math.round(Math.log10(d)); if([10,100,1000].includes(d)){
      let vals=[dividend];for(let i=0;i<steps;i++)vals.push(vals[vals.length-1]/10);
      return helpBox(`<div class="decimal-track">${vals.map(hfmt).join('  →  ')}</div><div class="decimal-arrow">${'← '.repeat(steps)}</div><div class="help-note">${steps} déplacement${steps>1?'s':''} vers la gauche</div>`,`Diviser par ${d}, c’est déplacer la virgule de ${steps} rang${steps>1?'s':''} vers la gauche.`)
    }
  }
  if(k==='decimal'||k==='decimal_sub'){
    let op=k==='decimal'?'+':'−',r=k==='decimal'?a+b:a-b;
    return helpBox(`<div class="place-grid"><div class="place-head">Unités</div><div class="place-head">Après la virgule</div><div class="place-cell">${Math.trunc(a)}</div><div class="place-cell">${hfmt(Math.abs(a-Math.trunc(a))).replace('0,','0,')}</div><div class="place-cell">${Math.trunc(b)}</div><div class="place-cell">${hfmt(Math.abs(b-Math.trunc(b))).replace('0,','0,')}</div></div><div class="help-step">${hfmt(a)} ${op} ${hfmt(b)} <span class="help-arrow">→</span> ${hfmt(r)}</div>`,`Garde les virgules au même endroit : unités avec unités, dixièmes avec dixièmes.`)
  }
  return helpBox(`<div class="help-step">${q.display.replace(' = __','')}</div>`,`Décompose le calcul en petites étapes que tu connais déjà.`)
}


function pedagogicalCase(q){
  const p=q.payload||{}, k=q.kind;
  if(k==='complement_tens') return Number(p.target)-Number(p.a)>10?'gap_gt_10':'gap_le_10';
  if(k==='half'){
    const x=Number(p.n), tens=Math.floor(x/10)*10, units=x-tens;
    if(x>=30 && x%20===10) return 'odd_ten';
    if(x>=20 && tens%20===0 && units%2===0) return 'even_decomposition';
    return 'simple';
  }
  if(k==='decimal_multiplication') return 'x'+p.b;
  if(k==='decimal_division') return 'div'+p.divisor;
  if(k==='multiple_of') return 'factor'+p.factor;
  return 'default';
}
function exampleFor(q){
  const p={...(q.payload||{})}, k=q.kind, branch=pedagogicalCase(q);
  // Exemples déterministes pour les branches sensibles : aucune boucle possible.
  if(k==='complement_tens'){
    if(branch==='gap_gt_10') return {kind:k,payload:{a:45,target:60},display:'45 + __ = 60',expected:15};
    return {kind:k,payload:{a:43,target:50},display:'43 + __ = 50',expected:7};
  }
  if(k==='half'){
    if(branch==='odd_ten'){
      let x=Number(p.n)===70?50:70; return {kind:k,payload:{n:x},display:`Moitié de ${x} = __`,expected:x/2};
    }
    if(branch==='even_decomposition'){
      let x=Number(p.n)===48?64:48; return {kind:k,payload:{n:x},display:`Moitié de ${x} = __`,expected:x/2};
    }
    let x=Number(p.n)===18?16:18; return {kind:k,payload:{n:x},display:`Moitié de ${x} = __`,expected:x/2};
  }
  const bump=(x,d=2)=>Number(x)+d; let display=q.display;
  if(['addition','subtraction','tens','tens_sub'].includes(k)){p.a=bump(p.a,10);display=`${hfmt(p.a)} ${k==='addition'||k==='tens'?'+':'−'} ${hfmt(p.b)} = __`}
  else if(k==='multiplication'){p.b=Math.max(2,Number(p.b)+1);display=`${hfmt(p.a)} × ${hfmt(p.b)} = __`}
  else if(k==='division'){let quotient=Math.max(2,Math.round(Number(p.dividend)/Number(p.divisor))+1);p.dividend=Number(p.divisor)*quotient;display=`${hfmt(p.dividend)} : ${hfmt(p.divisor)} = __`}
  else if(k==='double'){p.n=Number(p.n)+2;display=`Double de ${hfmt(p.n)} = __`}
  else if(k==='round_tens_add'){p.b=Number(p.b)>=9?1:Number(p.b)+1;display=`${p.a} + ${p.b} = __`}
  else if(k==='addition3'){p.numbers=(p.numbers||[1,2,3]).map((x,i)=>Math.max(1,Math.min(9,Number(x)+(i===0?1:0))));display=`${p.numbers.join(' + ')} = __`}
  else if(k==='multiple_of'){let f=Number(p.factor)||3;p.n=Math.max(1,Number(p.n)+1);p.factor=f;display=`${f===3?'Triple':'Quadruple'} de ${p.n} = __`}
  else if(k==='fraction'){let d=Number(p.divisor)||3;p.n=Math.max(d,Number(p.n)+d);p.n-=p.n%d;p.divisor=d;display=`${d===3?'Tiers':'Quart'} de ${p.n} = __`}
  else if(k==='decimal_multiplication'){p.a=Math.round((Number(p.a)+1.1)*100)/100;display=`${hfmt(p.a)} × ${hfmt(p.b)} = __`}
  else if(k==='decimal_division'){p.dividend=Math.round((Number(p.dividend)+Number(p.divisor))*100)/100;display=`${hfmt(p.dividend)} : ${hfmt(p.divisor)} = __`}
  else if(k==='decimal'||k==='decimal_sub'){p.a=Math.round((Number(p.a)+1.1)*100)/100;display=`${hfmt(p.a)} ${k==='decimal'?'+':'−'} ${hfmt(p.b)} = __`}
  return {...q,payload:p,display};
}

const catalog=[
  {id:'addition',name:'Additions',samples:[
    ['Passage par 10',{kind:'addition',payload:{a:8,b:7},display:'8 + 7 = __'}],
    ['Décomposition',{kind:'addition',payload:{a:23,b:14},display:'23 + 14 = __'}]]},
  {id:'subtraction',name:'Soustractions',samples:[
    ['Passage par la dizaine',{kind:'subtraction',payload:{a:32,b:7},display:'32 − 7 = __'}],
    ['Décomposition',{kind:'subtraction',payload:{a:47,b:23},display:'47 − 23 = __'}]]},
  {id:'double',name:'Doubles',samples:[
    ['Petit nombre',{kind:'double',payload:{n:7},display:'Double de 7 = __'}],
    ['Nombre à 2 chiffres',{kind:'double',payload:{n:14},display:'Double de 14 = __'}],
    ['Dizaine ronde',{kind:'double',payload:{n:30},display:'Double de 30 = __'}]]},
  {id:'half',name:'Moitiés',samples:[
    ['Partage simple',{kind:'half',payload:{n:18},display:'Moitié de 18 = __'}],
    ['Dizaine impaire : 30 / 50 / 70 / 90',{kind:'half',payload:{n:70},display:'Moitié de 70 = __'}],
    ['Décomposition paire',{kind:'half',payload:{n:48},display:'Moitié de 48 = __'}]]},
  {id:'complement_tens',name:'Compléments',samples:[
    ['Écart ≤ 10',{kind:'complement_tens',payload:{a:43,target:50},display:'43 + __ = 50'}],
    ['Écart > 10',{kind:'complement_tens',payload:{a:45,target:60},display:'45 + __ = 60'}]]},
  {id:'multiplication',name:'Multiplications',samples:[
    ['× 4',{kind:'multiplication',payload:{a:4,b:7},display:'4 × 7 = __'}],
    ['× 5',{kind:'multiplication',payload:{a:5,b:7},display:'5 × 7 = __'}],
    ['× 6, 7, 8',{kind:'multiplication',payload:{a:7,b:6},display:'7 × 6 = __'}],
    ['× 9',{kind:'multiplication',payload:{a:9,b:7},display:'9 × 7 = __'}],
    ['× 10 / 100 / 1000',{kind:'multiplication',payload:{a:10,b:7},display:'10 × 7 = __'}]]},
  {id:'division',name:'Divisions',samples:[['Multiplication inverse',{kind:'division',payload:{dividend:42,divisor:6},display:'42 : 6 = __'}]]},
  {id:'tens',name:'Additions de dizaines',samples:[['Dizaines / unités',{kind:'tens',payload:{a:34,b:20},display:'34 + 20 = __'}]]},
  {id:'tens_sub',name:'Soustractions de dizaines',samples:[['Dizaines / unités',{kind:'tens_sub',payload:{a:54,b:20},display:'54 − 20 = __'}]]},
  {id:'decimal_multiplication',name:'Multiplications décimales',samples:[['× 10',{kind:'decimal_multiplication',payload:{a:2.4,b:10},display:'2,4 × 10 = __'}],['× 100',{kind:'decimal_multiplication',payload:{a:2.4,b:100},display:'2,4 × 100 = __'}],['× 1000',{kind:'decimal_multiplication',payload:{a:2.4,b:1000},display:'2,4 × 1000 = __'}]]},
  {id:'decimal_division',name:'Divisions décimales',samples:[['÷ 10',{kind:'decimal_division',payload:{dividend:24,divisor:10},display:'24 : 10 = __'}],['÷ 100',{kind:'decimal_division',payload:{dividend:240,divisor:100},display:'240 : 100 = __'}],['÷ 1000',{kind:'decimal_division',payload:{dividend:2400,divisor:1000},display:'2400 : 1000 = __'}]]}
];
global.Pedagogy={contextualHelp,pedagogicalCase,exampleFor,catalog};
})(window);
