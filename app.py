from __future__ import annotations
import json
import random, sqlite3, statistics, time, copy, os, re
from pathlib import Path
from datetime import timedelta
from flask import Flask, request, jsonify, send_from_directory, session, redirect, Response
from werkzeug.security import generate_password_hash, check_password_hash

ROOT=Path(__file__).parent
DB=Path(os.environ.get('DB_PATH', str(ROOT/'calcul_mental.db')))
app=Flask(__name__, static_folder='static', static_url_path='')
_secret_key=os.environ.get('SECRET_KEY')
if not _secret_key:
    if os.environ.get('RENDER','').lower()=='true':
        raise RuntimeError("SECRET_KEY doit être défini sur Render")
    _secret_key='dev-only-change-me'
app.secret_key=_secret_key
app.config['PERMANENT_SESSION_LIFETIME']=timedelta(days=90)
app.config['SESSION_COOKIE_SAMESITE']='Lax'
app.config['SESSION_COOKIE_SECURE']=os.environ.get('RENDER','').lower()=='true'

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS accounts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS profiles(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        account_id INTEGER NOT NULL, color TEXT NOT NULL DEFAULT '#8fdff7', school_class TEXT NOT NULL DEFAULT '',
        coins INTEGER NOT NULL DEFAULT 0, challenge_stars INTEGER NOT NULL DEFAULT 0, challenge_level_id INTEGER
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_account_name ON profiles(account_id,name COLLATE NOCASE);
    CREATE TABLE IF NOT EXISTS configs(
        profile_id INTEGER PRIMARY KEY, data TEXT NOT NULL, FOREIGN KEY(profile_id) REFERENCES profiles(id)
    );
    CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        active_ms INTEGER NOT NULL DEFAULT 0, rewarded INTEGER NOT NULL DEFAULT 0, mode TEXT NOT NULL DEFAULT 'learning',
        challenge_class TEXT, challenge_level_id INTEGER, star_awarded INTEGER NOT NULL DEFAULT 0, challenge_day TEXT,
        daily_bonus_awarded INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(profile_id) REFERENCES profiles(id)
    );
    CREATE TABLE IF NOT EXISTS questions(
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, position INTEGER NOT NULL, kind TEXT NOT NULL,
        payload TEXT NOT NULL, display TEXT NOT NULL, expected REAL NOT NULL, given_answer REAL, status TEXT NOT NULL,
        response_ms INTEGER, source TEXT NOT NULL, retry_from INTEGER, attempts INTEGER NOT NULL DEFAULT 0,
        had_error INTEGER NOT NULL DEFAULT 0, first_wrong_answer REAL, last_answer REAL, help_used INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
    );
    CREATE TABLE IF NOT EXISTS reward_progress(
        profile_id INTEGER PRIMARY KEY, current_card TEXT, revealed TEXT NOT NULL DEFAULT '[]',
        completed TEXT NOT NULL DEFAULT '[]', FOREIGN KEY(profile_id) REFERENCES profiles(id)
    );
    CREATE TABLE IF NOT EXISTS challenge_levels(
        id INTEGER PRIMARY KEY AUTOINCREMENT, school_class TEXT NOT NULL, name TEXT NOT NULL, position INTEGER NOT NULL,
        data TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, UNIQUE(school_class, position)
    );
    CREATE TABLE IF NOT EXISTS class_settings(school_class TEXT PRIMARY KEY, color TEXT NOT NULL);
    """)
    class_defaults={'CP':'#ef5350','CE1':'#f5b82e','CE2':'#2fbd68','CM1':'#3189dc','CM2':'#8b4de3'}
    for school,color in class_defaults.items():
        c.execute('INSERT OR IGNORE INTO class_settings(school_class,color) VALUES(?,?)',(school,color))
    c.commit(); c.close()

DEFAULT={
 'duration':300,'count':50,
 'categories':{
  'double':{'enabled':True,'weight':3,'min':1,'max':9,'doubleMode':'non_tens','tensValues':[10,20,30,40,50,60,70,80,90,100],'display':'both'},
  'half':{'enabled':False,'weight':3,'min':2,'max':10,'halfMode':'non_tens','tensValues':[10,20,30,40,50,60,70,80,90,100],'roundHundreds':False,'roundThousands':False},
  'addition':{'enabled':True,'weight':4,'aMin':1,'aMax':10,'bMin':1,'bMax':10,'maxResult':100,'withCarry':True},
  'subtraction':{'enabled':True,'weight':3,'aMin':1,'aMax':10,'bMin':1,'bMax':10,'nonNegative':True,'withCarry':True},
  'decimal':{'enabled':False,'weight':3,'min':0,'max':20,'decimals':1,'withCarry':True},
  'multiplication':{'enabled':True,'weight':3,'tables':[2,3],'factorMin':1,'factorMax':9,'powerTables':[],'powerFactorMin':1,'powerFactorMax':99},
  'division':{'enabled':True,'weight':2,'tables':[2,3,4],'quotientMin':1,'quotientMax':10},
  'complement_tens':{'enabled':False,'weight':3,'targets':[10,20,30,40,50,60,70,80,90,100,1000],'gapMin':5,'gapMax':20},
  'place_value':{'enabled':False,'weight':3,'places':['u'],'absenceProbability':50},
  'addition3':{'enabled':False,'weight':3,'maxResult':27},
  'multiple_of':{'enabled':False,'weight':3,'min':1,'max':10,'factors':[3,4]},
  'fraction':{'enabled':False,'weight':3,'min':1,'max':10,'divisors':[3,4]},
  'tens':{'enabled':True,'weight':3,'startMin':10,'startMax':99,'mode':'10','multiples':[10,20,30,40,50,60,70,80,90],'maxResult':100,'withCarry':True},
  'round_tens_add':{'enabled':False,'weight':3,'aMin':10,'aMax':90,'secondMode':'non_tens','bMin':1,'bMax':9,'bTensValues':[10,20,30,40,50,60,70,80,90,100],'maxResult':100},
  'tens_sub':{'enabled':False,'weight':3,'startMin':20,'startMax':100,'mode':'10','multiples':[10,20,30,40,50,60,70,80,90],'nonNegative':True,'withCarry':True},
  'decimal_sub':{'enabled':False,'weight':3,'min':0,'max':20,'decimals':1,'withBorrow':True},
  'decimal_multiplication':{'enabled':False,'weight':3,'multipliers':[10,100,1000],'min':0.1,'max':20,'decimals':1},
  'decimal_division':{'enabled':False,'weight':3,'divisors':[10,100,1000],'min':1,'max':1000,'decimals':1}
 }}

# Défis centralisés : 5 paliers par classe.
# Les réglages sont volontairement côté serveur : aucun bouton de configuration
# n'est exposé à l'enfant dans le mode Défi.
def seed_challenge_cfg(school_class, level):
    school_class=(school_class or 'CP').upper()
    level=max(1,int(level or 1))
    level=max(1,min(5,level))
    cfg=copy.deepcopy(DEFAULT)
    cfg['duration']=300
    cfg['count']=50
    for v in cfg['categories'].values():
        v['enabled']=False

    def on(kind,weight,**kw):
        v=cfg['categories'][kind]; v.update(kw); v['enabled']=True; v['weight']=weight

    # Ces 25 templates constituent une première progression centrale facilement
    # ajustable ensuite sans modifier l'interface.
    if school_class=='CP':
        if level==1:
            on('addition',50,aMin=0,aMax=5,bMin=0,bMax=5,maxResult=10,withCarry=False)
            on('complement_tens',25,targets=[10],gapMin=1,gapMax=9); on('double',25,min=1,max=5,display='both')
        elif level==2:
            on('addition',45,aMin=0,aMax=10,bMin=0,bMax=10,maxResult=20,withCarry=False)
            on('subtraction',30,aMin=0,aMax=20,bMin=0,bMax=10,nonNegative=True)
            on('double',25,min=1,max=10,display='both')
        elif level==3:
            on('addition',40,aMin=0,aMax=20,bMin=0,bMax=10,maxResult=30,withCarry=True)
            on('subtraction',35,aMin=0,aMax=30,bMin=0,bMax=10,nonNegative=True)
            on('complement_tens',25,targets=[10],gapMin=1,gapMax=9)
        elif level==4:
            on('addition',40,aMin=0,aMax=30,bMin=0,bMax=20,maxResult=50,withCarry=True)
            on('subtraction',35,aMin=0,aMax=50,bMin=0,bMax=20,nonNegative=True)
            on('tens',25,startMin=10,startMax=39,mode='10',multiples=[10],maxResult=50)
        else:
            on('addition',40,aMin=0,aMax=50,bMin=0,bMax=30,maxResult=100,withCarry=True)
            on('subtraction',35,aMin=0,aMax=100,bMin=0,bMax=50,nonNegative=True)
            on('tens',25,startMin=10,startMax=89,mode='10',multiples=[10],maxResult=100)
    elif school_class=='CE1':
        if level==1:
            on('addition',30,aMin=1,aMax=30,bMin=1,bMax=20,maxResult=50,withCarry=True)
            on('subtraction',25,aMin=10,aMax=50,bMin=1,bMax=30,nonNegative=True)
            on('double',20,min=1,max=10,display='both'); on('complement_tens',10,targets=[10],gapMin=1,gapMax=9)
            on('tens',15,startMin=10,startMax=89,mode='10',multiples=[10],maxResult=100)
        elif level==2:
            on('addition',30,aMin=1,aMax=60,bMin=1,bMax=40,maxResult=100,withCarry=True)
            on('subtraction',25,aMin=10,aMax=100,bMin=1,bMax=60,nonNegative=True)
            on('double',15,min=1,max=20,display='both')
            on('tens',15,startMin=10,startMax=89,mode='10',multiples=[10],maxResult=100)
            on('multiplication',15,tables=[2,5,10],factorMin=1,factorMax=10)
        elif level==3:
            on('addition',25,aMin=10,aMax=90,bMin=1,bMax=90,maxResult=150,withCarry=True)
            on('subtraction',25,aMin=20,aMax=150,bMin=1,bMax=100,nonNegative=True)
            on('double',15,min=5,max=50,display='both')
            on('multiplication',20,tables=[2,3,4,5,10],factorMin=1,factorMax=10)
            on('division',15,tables=[2,5,10],quotientMin=1,quotientMax=10)
        elif level==4:
            on('addition',25,aMin=20,aMax=150,bMin=10,bMax=100,maxResult=250,withCarry=True)
            on('subtraction',25,aMin=30,aMax=250,bMin=1,bMax=150,nonNegative=True)
            on('multiplication',25,tables=[2,3,4,5,10],factorMin=1,factorMax=10)
            on('division',15,tables=[2,3,4,5,10],quotientMin=1,quotientMax=10)
            on('tens_sub',10,startMin=20,startMax=200,mode='10',multiples=[10],nonNegative=True)
        else:
            on('addition',25,aMin=20,aMax=250,bMin=10,bMax=200,maxResult=400,withCarry=True)
            on('subtraction',25,aMin=50,aMax=400,bMin=1,bMax=250,nonNegative=True)
            on('multiplication',25,tables=[2,3,4,5,6,10],factorMin=1,factorMax=10)
            on('division',20,tables=[2,3,4,5,10],quotientMin=1,quotientMax=10)
            on('double',5,min=10,max=100,display='both')
    elif school_class=='CE2':
        tables_by_level=[[2,3,4,5,10],[2,3,4,5,6,10],[2,3,4,5,6,7,10],[2,3,4,5,6,7,8,9,10],[2,3,4,5,6,7,8,9,10]]
        lim=[300,500,800,1000,1500][level-1]
        on('addition',25,aMin=20,aMax=lim//2,bMin=10,bMax=lim//2,maxResult=lim,withCarry=True)
        on('subtraction',25,aMin=50,aMax=lim,bMin=1,bMax=lim//2,nonNegative=True)
        on('multiplication',30,tables=tables_by_level[level-1],factorMin=1,factorMax=10)
        on('division',20,tables=tables_by_level[level-1],quotientMin=1,quotientMax=10)
    elif school_class=='CM1':
        lim=[1000,2000,5000,10000,20000][level-1]
        on('addition',20,aMin=100,aMax=lim//2,bMin=10,bMax=lim//2,maxResult=lim,withCarry=True)
        on('subtraction',20,aMin=100,aMax=lim,bMin=1,bMax=lim//2,nonNegative=True)
        on('multiplication',25,tables=[2,3,4,5,6,7,8,9,10],factorMin=1,factorMax=10)
        on('division',20,tables=[2,3,4,5,6,7,8,9,10],quotientMin=1,quotientMax=12)
        on('decimal',15,min=0,max=20*(level+1),decimals=1,withCarry=True)
    else: # CM2
        lim=[5000,10000,20000,50000,100000][level-1]
        on('addition',15,aMin=100,aMax=lim//2,bMin=10,bMax=lim//2,maxResult=lim,withCarry=True)
        on('subtraction',15,aMin=100,aMax=lim,bMin=1,bMax=lim//2,nonNegative=True)
        on('multiplication',20,tables=[2,3,4,5,6,7,8,9,10],factorMin=2,factorMax=12)
        on('division',15,tables=[2,3,4,5,6,7,8,9,10],quotientMin=2,quotientMax=15)
        on('decimal',15,min=0,max=100,decimals=1 if level<4 else 2,withCarry=True)
        on('decimal_sub',10,min=0,max=100,decimals=1 if level<4 else 2,withBorrow=True)
        on('decimal_multiplication',5,multipliers=[10,100,1000],min=0.1,max=50,decimals=1)
        on('decimal_division',5,divisors=[10,100,1000],min=1,max=1000,decimals=1)
    return cfg

def merged_cfg(saved):
    """Fusionne uniquement les catégories actuellement supportées."""
    cfg=copy.deepcopy(DEFAULT)
    cfg.update({k:v for k,v in (saved or {}).items() if k!='categories'})
    for kind,values in (saved or {}).get('categories',{}).items():
        if kind in cfg['categories'] and isinstance(values,dict):
            cfg['categories'][kind].update(values)
    # Migration douce des anciens réglages : 100/1000 étaient auparavant mélangés
    # aux tables classiques. On les conserve dans la nouvelle famille dédiée.
    mul=cfg['categories'].get('multiplication',{})
    old_tables=[int(x) for x in mul.get('tables',[]) if str(x).lstrip('-').isdigit()]
    migrated=[x for x in old_tables if x in (100,1000,10000)]
    if migrated and not mul.get('powerTables'):
        mul['powerTables']=migrated
    mul['tables']=[x for x in old_tables if 1 <= x <= 20]
    return cfg

def get_cfg(pid):
    c=db(); r=c.execute('SELECT data FROM configs WHERE profile_id=?',(pid,)).fetchone(); c.close()
    return merged_cfg(json.loads(r['data'])) if r else copy.deepcopy(DEFAULT)

def normalize_category_weights(cats):
    """Garantit simplement un poids positif aux catégories actives."""
    for v in cats.values():
        if v.get('enabled'):
            try: w=int(v.get('weight',3))
            except (TypeError,ValueError): w=3
            v['weight']=max(1,w)
    return cats

def allocate(n,cats):
    normalize_category_weights(cats)
    active=[(k,v) for k,v in cats.items() if v.get('enabled')]
    if not active: return {}
    total=sum(int(v.get('weight',3)) for _,v in active)
    vals=[]; used=0
    for k,v in active:
        exact=n*int(v.get('weight',3))/total
        base=int(exact); vals.append([k,base,exact-base]); used+=base
    vals.sort(key=lambda x:x[2], reverse=True)
    for i in range(n-used): vals[i%len(vals)][1]+=1
    return {k:b for k,b,_ in vals}

def gen(kind,cfg):
    if kind=='double':
        value_mode=cfg.get('doubleMode','non_tens')
        lo=int(cfg.get('min',1)); hi=int(cfg.get('max',9))
        if lo>hi: lo,hi=hi,lo
        choices=[]
        if value_mode in ('non_tens','both'):
            choices += [n for n in range(lo,hi+1) if n%10!=0]
        if value_mode in ('tens','both'):
            choices += [int(x) for x in cfg.get('tensValues',[10,20,30,40,50,60,70,80,90,100])]
        choices=list(dict.fromkeys(choices))
        if not choices: raise ValueError("Aucun double possible avec ces réglages.")
        n=random.choice(choices); mode=cfg.get('display','both'); mode=random.choice(['word','sum']) if mode=='both' else mode
        return {'n':n,'mode':mode}, (f'Double de {n} = __' if mode=='word' else f'{n} + {n} = __'), n*2
    if kind=='half':
        mode=cfg.get('halfMode') or ('both' if cfg.get('tens',False) else 'non_tens')
        lo=int(cfg.get('min',2)); hi=int(cfg.get('max',10))
        if lo>hi: lo,hi=hi,lo
        choices=[]
        if mode in ('non_tens','both'): choices += [n for n in range(max(2,lo),hi+1) if n%2==0 and n%10!=0]
        if mode in ('tens','both'): choices += [int(x) for x in cfg.get('tensValues',[10,20,30,40,50,60,70,80,90,100])]
        if cfg.get('roundHundreds',False): choices += list(range(100,1000,100))
        if cfg.get('roundThousands',False): choices += list(range(1000,10000,1000))
        choices=list(dict.fromkeys(choices))
        if not choices: raise ValueError("Aucune moitié possible avec ces réglages.")
        n=random.choice(choices)
        return {'n':n}, f'Moitié de {n} = __', n//2
    if kind=='addition':
        # "Sans retenue" = aucune colonne décimale ne produit une somme >= 10.
        def no_carry(x,y):
            while x or y:
                if (x % 10) + (y % 10) >= 10: return False
                x//=10; y//=10
            return True
        candidates=[]
        for x in range(int(cfg['aMin']),int(cfg['aMax'])+1):
            for y in range(int(cfg['bMin']),int(cfg['bMax'])+1):
                if cfg.get('maxResult') and x+y>cfg['maxResult']: continue
                if cfg.get('withCarry',True) or no_carry(x,y): candidates.append((x,y))
        if not candidates: raise ValueError("Aucune addition possible avec ces réglages sans retenue")
        a,b=random.choice(candidates)
        return {'a':a,'b':b},f'{a} + {b} = __',a+b
    if kind=='subtraction':
        def no_borrow(x,y):
            while x or y:
                if (x%10)<(y%10): return False
                x//=10; y//=10
            return True
        candidates=[]
        for a in range(int(cfg['aMin']),int(cfg['aMax'])+1):
            for b in range(int(cfg['bMin']),int(cfg['bMax'])+1):
                if cfg.get('nonNegative',True) and a<b: continue
                if not cfg.get('withCarry',True) and not no_borrow(a,b): continue
                candidates.append((a,b))
        if not candidates: raise ValueError("Aucune soustraction possible avec ces réglages.")
        a,b=random.choice(candidates)
        return {'a':a,'b':b},f'{a} − {b} = __',a-b
    if kind=='decimal':
        # Addition de décimaux uniquement. Sans retenue, chaque colonne de chiffres
        # (partie décimale et partie entière) doit rester strictement inférieure à 10.
        decimals=max(1,min(2,int(cfg.get('decimals',1)))); scale=10**decimals
        lo=int(round(float(cfg.get('min',0))*scale)); hi=int(round(float(cfg.get('max',20))*scale))
        if hi<lo: lo,hi=hi,lo
        def no_carry_scaled(x,y):
            while x or y:
                if (x % 10) + (y % 10) >= 10: return False
                x//=10; y//=10
            return True
        candidates=[]
        # Random sampling avoids building an enormous Cartesian product for wide ranges.
        for _ in range(1200):
            x=random.randint(lo,hi); y=random.randint(lo,hi)
            if cfg.get('withCarry',True) or no_carry_scaled(x,y):
                candidates.append((x,y))
                if len(candidates)>=80: break
        if not candidates: raise ValueError("Aucune addition de décimaux possible avec ces réglages sans retenue")
        a,b=random.choice(candidates)
        av=a/scale; bv=b/scale; expected=(a+b)/scale
        fmt=lambda x: (f'{x:.{decimals}f}'.rstrip('0').rstrip('.')).replace('.',',')
        return {'a':av,'b':bv,'op':'addition','decimals':decimals},f'{fmt(av)} + {fmt(bv)} = __',expected
    if kind=='multiplication':
        # Deux familles indépendantes : tables classiques (1–20) et puissances de 10.
        # Chacune possède sa propre plage de 2e facteur afin de pouvoir, par exemple,
        # travailler 45 × 1000 sans générer 45 × 5.
        candidates=[]
        for a in cfg.get('tables',[]):
            candidates.append((int(a), int(cfg.get('factorMin',1)), int(cfg.get('factorMax',9))))
        for a in cfg.get('powerTables',[]):
            candidates.append((int(a), int(cfg.get('powerFactorMin',1)), int(cfg.get('powerFactorMax',99))))
        if not candidates: raise ValueError('Choisis au moins une table de multiplication.')
        a,lo,hi=random.choice(candidates)
        if lo>hi: lo,hi=hi,lo
        b=random.randint(lo,hi)
        return {'a':a,'b':b},f'{a} × {b} = __',a*b
    if kind=='division':
        d=random.choice(cfg['tables']); q=random.randint(cfg['quotientMin'],cfg['quotientMax']); return {'dividend':d*q,'divisor':d},f'{d*q} : {d} = __',q
    if kind=='decimal_multiplication':
        m=random.choice(cfg.get('multipliers',[10,100,1000])); dec=max(1,min(2,int(cfg.get('decimals',1))))
        scale=10**dec; lo=max(1,int(round(float(cfg.get('min',0.1))*scale))); hi=max(lo,int(round(float(cfg.get('max',20))*scale)))
        ai=random.randint(lo,hi); x=ai/scale; expected=x*m
        fmt=lambda v: (f'{v:.{dec}f}'.rstrip('0').rstrip('.')).replace('.',',')
        return {'a':x,'b':m},f'{fmt(x)} × {m} = __',expected
    if kind=='decimal_division':
        d=random.choice(cfg.get('divisors',[10,100,1000])); dec=max(0,min(2,int(cfg.get('decimals',1))))
        scale=10**dec; lo=max(1,int(round(float(cfg.get('min',1))*scale))); hi=max(lo,int(round(float(cfg.get('max',1000))*scale)))
        ai=random.randint(lo,hi); x=ai/scale; expected=x/d
        fmt=lambda v: (f'{v:.{dec}f}'.rstrip('0').rstrip('.')).replace('.',',')
        return {'dividend':x,'divisor':d},f'{fmt(x)} : {d} = __',expected
    if kind=='complement_tens':
        targets=[int(x) for x in cfg.get('targets',[10,20,30,40,50,60,70,80,90,100,1000])]
        if not targets: raise ValueError("Choisis au moins une dizaine cible.")
        gap_min=max(1,int(cfg.get('gapMin',5)))
        gap_max=max(gap_min,int(cfg.get('gapMax',20)))
        possible=[(target,gap) for target in targets for gap in range(gap_min,gap_max+1) if gap < target]
        if not possible: raise ValueError("Aucune opération possible avec cet écart et ces cibles.")
        target,gap=random.choice(possible); a=target-gap
        display=f'{a} + __ = {target}'
        return {'a':a,'target':target},display,gap
    if kind=='place_value':
        places=[p for p in cfg.get('places',['u']) if p in ('m','c','d','u')]
        if not places: raise ValueError("Choisis au moins un terme parmi m, c, d et u.")
        absent=max(0,min(80,int(cfg.get('absenceProbability',50))))/100
        present=[]
        for _ in range(20):
            present=[p for p in places if random.random()>=absent]
            if present: break
        if not present: present=[random.choice(places)]
        factors={p:random.randint(1,9) for p in present}; mult={'m':1000,'c':100,'d':10,'u':1}
        expected=sum(factors[p]*mult[p] for p in present)
        display_order=list(factors.keys()); random.shuffle(display_order)
        display=' '.join(f'{factors[p]}{p}' for p in display_order)+' = __'
        return {'factors':factors,'order':display_order},display,expected
    if kind=='addition3':
        max_result=max(3,int(cfg.get('maxResult',27)))
        candidates=[(a,b,c) for a in range(1,10) for b in range(1,10) for c in range(1,10) if a+b+c<=max_result]
        if not candidates: raise ValueError("Aucune addition à 3 termes possible avec ce résultat max.")
        nums=list(random.choice(candidates))
        return {'numbers':nums},f'{nums[0]} + {nums[1]} + {nums[2]} = __',sum(nums)
    if kind=='multiple_of':
        factors=[int(x) for x in cfg.get('factors',[3,4]) if int(x) in (3,4)]
        if not factors: raise ValueError("Choisis au moins Triple ou Quadruple.")
        n=random.randint(int(cfg.get('min',1)),int(cfg.get('max',10))); factor=random.choice(factors)
        word='Triple' if factor==3 else 'Quadruple'
        return {'n':n,'factor':factor},f'{word} de {n} = __',n*factor
    if kind=='fraction':
        divisors=[int(x) for x in cfg.get('divisors',[3,4]) if int(x) in (3,4)]
        if not divisors: raise ValueError("Choisis au moins Tiers ou Quart.")
        divisor=random.choice(divisors); q=random.randint(int(cfg.get('min',1)),int(cfg.get('max',10))); n=q*divisor
        word='Tiers' if divisor==3 else 'Quart'
        return {'n':n,'divisor':divisor},f'{word} de {n} = __',q
    if kind=='tens':
        choices=[10] if cfg.get('mode')=='10' else [int(x) for x in cfg.get('multiples',[10])]
        def no_carry(x,y):
            while x or y:
                if (x%10)+(y%10)>=10: return False
                x//=10; y//=10
            return True
        candidates=[(a,b) for a in range(int(cfg['startMin']),int(cfg['startMax'])+1) for b in choices
                    if (not cfg.get('maxResult') or a+b<=int(cfg['maxResult']))
                    and (cfg.get('withCarry',True) or no_carry(a,b))]
        if not candidates: raise ValueError("Aucune addition de dizaines possible avec ces réglages.")
        a,b=random.choice(candidates)
        return {'a':a,'b':b},f'{a} + {b} = __',a+b
    if kind=='round_tens_add':
        a_min=int(cfg.get('aMin',10)); a_max=int(cfg.get('aMax',90))
        if a_min>a_max: a_min,a_max=a_max,a_min
        first=[x for x in range(a_min,a_max+1) if x%10==0]
        if not first: raise ValueError("Aucune dizaine ronde dans la plage du premier terme.")
        mode=cfg.get('secondMode','non_tens'); second=[]
        if mode in ('non_tens','both'):
            b_min=int(cfg.get('bMin',1)); b_max=int(cfg.get('bMax',9))
            if b_min>b_max: b_min,b_max=b_max,b_min
            second += [x for x in range(b_min,b_max+1) if x%10!=0]
        if mode in ('tens','both'):
            second += [int(x) for x in cfg.get('bTensValues',[10,20,30,40,50,60,70,80,90,100])]
        second=list(dict.fromkeys(second))
        if not second: raise ValueError("Aucun second terme possible avec ces réglages.")
        max_result=int(cfg.get('maxResult',100) or 0)
        candidates=[(a,b) for a in first for b in second if not max_result or a+b<=max_result]
        if not candidates: raise ValueError("Aucun ajout à dizaine ronde possible avec ce résultat max.")
        a,b=random.choice(candidates)
        return {'a':a,'b':b},f'{a} + {b} = __',a+b
    if kind=='tens_sub':
        choices=[10] if cfg.get('mode')=='10' else [int(x) for x in cfg.get('multiples',[10])]
        def no_borrow_tens(x,y):
            while x or y:
                if (x%10)<(y%10): return False
                x//=10; y//=10
            return True
        candidates=[(x,y) for x in range(int(cfg['startMin']),int(cfg['startMax'])+1) for y in choices
                    if (not cfg.get('nonNegative',True) or x>=y)
                    and (cfg.get('withCarry',True) or no_borrow_tens(x,y))]
        if not candidates: raise ValueError("Aucune soustraction de dizaines possible avec ces réglages")
        x,y=random.choice(candidates)
        return {'a':x,'b':y},f'{x} − {y} = __',x-y
    if kind=='decimal_sub':
        decimals=max(1,min(2,int(cfg.get('decimals',1)))); scale=10**decimals
        lo=int(round(float(cfg.get('min',0))*scale)); hi=int(round(float(cfg.get('max',20))*scale))
        if hi<lo: lo,hi=hi,lo
        def no_borrow_scaled(x,y):
            while x or y:
                if (x % 10) < (y % 10): return False
                x//=10; y//=10
            return True
        candidates=[]
        for _ in range(1600):
            x=random.randint(lo,hi); y=random.randint(lo,x)
            if cfg.get('withBorrow',True) or no_borrow_scaled(x,y):
                candidates.append((x,y))
                if len(candidates)>=80: break
        if not candidates: raise ValueError("Aucune soustraction de décimaux possible avec ces réglages")
        x,y=random.choice(candidates); xv=x/scale; yv=y/scale
        fmt=lambda v: (f'{v:.{decimals}f}'.rstrip('0').rstrip('.')).replace('.',',')
        return {'a':xv,'b':yv,'op':'subtraction','decimals':decimals},f'{fmt(xv)} − {fmt(yv)} = __',(x-y)/scale

def previous_errors(pid, mode='learning'):
    c=db(); s=c.execute('SELECT id FROM sessions WHERE profile_id=? AND mode=? ORDER BY id DESC LIMIT 1',(pid,mode)).fetchone()
    if not s: c.close(); return []
    rows=c.execute("SELECT id,kind,payload,display,expected FROM questions WHERE session_id=? AND status='INCORRECT' ORDER BY position",(s['id'],)).fetchall(); c.close(); return [dict(x) for x in rows]

def authenticated(): return isinstance(session.get('account_id'), int)
def current_account_id(): return session.get('account_id')
def require_auth():
    if not authenticated(): return ({'error':'Connexion requise'},401)
    return None
def owns_profile(pid):
    aid=current_account_id()
    c=db(); r=c.execute('SELECT id FROM profiles WHERE id=? AND account_id=?',(pid,aid)).fetchone(); c.close(); return bool(r)

def password_error(password):
    if len(password)<12: return 'Le mot de passe doit contenir au moins 12 caractères.'
    if not re.search(r'[a-z]',password) or not re.search(r'[A-Z]',password) or not re.search(r'\d',password) or not re.search(r'[^A-Za-z0-9]',password):
        return 'Utilise au moins une minuscule, une majuscule, un chiffre et un caractère spécial.'
    return None

@app.get('/')
def index():
    # index.html évolue souvent : ne jamais laisser le navigateur réutiliser une ancienne UI.
    resp=send_from_directory(ROOT/'static','index.html',max_age=0)
    resp.headers['Cache-Control']='no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma']='no-cache'
    resp.headers['Expires']='0'
    return resp
@app.get('/api/auth/status')
def auth_status():
    if not authenticated(): return {'authenticated':False}
    c=db(); a=c.execute('SELECT username FROM accounts WHERE id=?',(current_account_id(),)).fetchone(); c.close()
    if not a: session.clear(); return {'authenticated':False}
    return {'authenticated':True,'username':a['username']}
@app.post('/api/auth/register')
def auth_register():
    data=request.json or {}; username=(data.get('username') or '').strip(); password=str(data.get('password') or '')
    if len(username)<3 or len(username)>40: return {'error':'L’identifiant doit contenir entre 3 et 40 caractères.'},400
    if not re.fullmatch(r'[A-Za-z0-9._-]+',username): return {'error':'Identifiant : lettres, chiffres, point, tiret et underscore uniquement.'},400
    if (err:=password_error(password)): return {'error':err},400
    c=db()
    try:
        cur=c.execute('INSERT INTO accounts(username,password_hash) VALUES(?,?)',(username,generate_password_hash(password)))
        aid=cur.lastrowid
        c.commit()
    except sqlite3.IntegrityError:
        c.close(); return {'error':'Cet identifiant existe déjà.'},409
    c.close(); session.clear(); session['account_id']=aid; session.permanent=True; return {'ok':True,'username':username}

@app.post('/auth/login-form')
def auth_login_form():
    username=(request.form.get('username') or '').strip()
    password=str(request.form.get('password') or '')
    c=db(); acc=c.execute('SELECT id,username,password_hash FROM accounts WHERE username=? COLLATE NOCASE',(username,)).fetchone(); c.close()
    if not acc or not check_password_hash(acc['password_hash'],password):
        return redirect('/?login=error')
    session.clear(); session['account_id']=acc['id']; session.permanent=True
    return redirect('/?login=ok')

@app.post('/api/auth/login')
def auth_login():
    data=request.json or {}; username=(data.get('username') or '').strip(); password=str(data.get('password') or '')
    c=db(); a=c.execute('SELECT id,username,password_hash FROM accounts WHERE username=? COLLATE NOCASE',(username,)).fetchone(); c.close()
    if not a or not check_password_hash(a['password_hash'],password): return {'error':'Identifiant ou mot de passe incorrect.'},401
    session.clear(); session['account_id']=a['id']; session.permanent=True; return {'ok':True,'username':a['username']}
@app.post('/api/auth/logout')
def auth_logout(): session.clear(); return {'ok':True}
def admin_unlocked():
    admin_password=os.environ.get('ADMIN_PASSWORD')
    return authenticated() and (not admin_password or session.get('admin_unlocked') is True)

def require_admin():
    if not authenticated(): return ({'error':'Connexion requise'},401)
    if not admin_unlocked(): return ({'error':'Accès administrateur requis'},403)
    return None

@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if not authenticated(): return redirect('/')
    admin_password=os.environ.get('ADMIN_PASSWORD')
    if not admin_password:
        session['admin_unlocked']=True
        return redirect('/admin')
    error=''
    if request.method=='POST':
        supplied=str(request.form.get('password') or '')
        if supplied==admin_password:
            session['admin_unlocked']=True
            return redirect('/admin')
        error='<p style="color:#b42318;font-weight:700">Mot de passe incorrect.</p>'
    return f'''<!doctype html><html lang="fr"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Administration</title><body style="font-family:system-ui;background:#f4f8fb;margin:0;display:grid;place-items:center;min-height:100vh">
    <form method="post" style="background:white;padding:28px;border-radius:18px;box-shadow:0 8px 30px #0002;min-width:min(320px,80vw)">
    <h1 style="font-size:24px">Administration</h1>{error}<input name="password" type="password" autocomplete="current-password" placeholder="Mot de passe admin"
    style="box-sizing:border-box;width:100%;padding:12px;border:1px solid #ccd5df;border-radius:10px"><button style="width:100%;margin-top:14px;padding:12px;border:0;border-radius:10px;background:#269ee8;color:white;font-weight:800">Entrer</button></form></body></html>'''

@app.get('/admin')
def admin_page():
    if not authenticated(): return redirect('/')
    if not admin_unlocked(): return redirect('/admin/login')
    return send_from_directory(ROOT/'static','admin.html')


CLASSES=('CP','CE1','CE2','CM1','CM2')

def class_rank(school):
    try: return CLASSES.index((school or 'CP').upper())
    except ValueError: return 0

def initial_challenge_school(real_school):
    i=class_rank(real_school)
    return CLASSES[max(0,i-1)]

def required_stars_for(challenge_school, real_school):
    # Tout palier inférieur à la classe réelle sert de validation rapide : 1 étoile.
    return 1 if class_rank(challenge_school) < class_rank(real_school) else 3

def color_name_fr(hex_color):
    """Nom simple de la couleur configurée, par proximité RGB, pour le message enfant."""
    palette={'rouge':'#ef5350','orange':'#f28c28','jaune':'#f5c542','verte':'#2fbd68','bleue':'#3189dc','violette':'#8b4de3','rose':'#e85aa6','turquoise':'#22b8b2'}
    try:
        h=(hex_color or '').lstrip('#'); rgb=tuple(int(h[i:i+2],16) for i in (0,2,4))
        def dist(v):
            x=v.lstrip('#'); q=tuple(int(x[i:i+2],16) for i in (0,2,4)); return sum((a-b)**2 for a,b in zip(rgb,q))
        return min(palette,key=lambda k:dist(palette[k]))
    except Exception: return 'suivante'

def challenge_levels_for(c, school):
    return c.execute('SELECT id,school_class,name,position,data FROM challenge_levels WHERE school_class=? AND active=1 ORDER BY position',(school,)).fetchall()

def first_level_for(c, school):
    return c.execute('SELECT id,school_class,name,position,data FROM challenge_levels WHERE school_class=? AND active=1 ORDER BY position LIMIT 1',(school,)).fetchone()

def resolve_profile_level(c, profile):
    real_school=(profile['school_class'] or 'CP').upper()
    level_id=profile['challenge_level_id']
    row=c.execute('SELECT id,school_class,name,position,data FROM challenge_levels WHERE id=? AND active=1',(level_id,)).fetchone() if level_id else None
    if row is None:
        challenge_school=initial_challenge_school(real_school)
        row=first_level_for(c,challenge_school)
        if row is None:
            return challenge_school,None,1,'Niveau 1'
    return row['school_class'],row,row['position'],row['name']

def sync_profile_level(c, pid):
    p=c.execute('SELECT id,school_class,challenge_level_id FROM profiles WHERE id=?',(pid,)).fetchone()
    if not p: return None
    _,row,_,_=resolve_profile_level(c,p)
    if row and p['challenge_level_id']!=row['id']:
        c.execute('UPDATE profiles SET challenge_level_id=? WHERE id=?',(row['id'],pid))
    return row

def next_challenge_level(c, row):
    """Niveau suivant, y compris le passage à la couleur/classe suivante."""
    if not row: return None
    nxt=c.execute('SELECT id,school_class,name,position,data FROM challenge_levels WHERE school_class=? AND active=1 AND position>? ORDER BY position LIMIT 1',
                  (row['school_class'],row['position'])).fetchone()
    if nxt: return nxt
    i=class_rank(row['school_class'])
    for school in CLASSES[i+1:]:
        nxt=first_level_for(c,school)
        if nxt: return nxt
    return None

def validate_cfg_data(data):
    data=merged_cfg(data or {})
    data['duration']=max(60,min(3600,int(data.get('duration',300))))
    data['count']=max(1,min(500,int(data.get('count',50))))
    cats=data['categories']
    normalize_category_weights(cats)
    if not any(v.get('enabled') for v in cats.values()):
        raise ValueError('Choisis au moins un exercice.')
    if cats.get('multiplication',{}).get('enabled'):
        m=cats['multiplication']
        m['tables']=[int(x) for x in m.get('tables',[]) if 1 <= int(x) <= 20]
        m['powerTables']=[int(x) for x in m.get('powerTables',[]) if int(x) in (10,100,1000,10000)]
        if not m['tables'] and not m['powerTables']:
            raise ValueError('Choisis au moins une table de multiplication.')
        m['factorMin']=int(m.get('factorMin',1)); m['factorMax']=int(m.get('factorMax',9))
        m['powerFactorMin']=int(m.get('powerFactorMin',1)); m['powerFactorMax']=int(m.get('powerFactorMax',99))
        if m['factorMin']>m['factorMax']: raise ValueError('La plage du 2e facteur des tables 1 à 20 est invalide.')
        if m['powerFactorMin']>m['powerFactorMax']: raise ValueError('La plage du 2e facteur des multiples de 10 est invalide.')
    if cats.get('division',{}).get('enabled') and not cats['division'].get('tables'):
        raise ValueError('Choisis au moins une table de division.')
    if cats.get('decimal_multiplication',{}).get('enabled') and not cats['decimal_multiplication'].get('multipliers'):
        raise ValueError('Choisis au moins un multiplicateur décimal.')
    if cats.get('decimal_division',{}).get('enabled') and not cats['decimal_division'].get('divisors'):
        raise ValueError('Choisis au moins un diviseur décimal.')
    if cats.get('double',{}).get('enabled'):
        d=cats['double']
        mode=d.get('doubleMode','non_tens')
        if mode not in ('non_tens','tens','both'): mode='non_tens'
        d['doubleMode']=mode
        d['min']=int(d.get('min',1)); d['max']=int(d.get('max',9))
        if d['min']>d['max']: raise ValueError('La plage des doubles est invalide.')
        d['tensValues']=[int(x) for x in d.get('tensValues',[10,20,30,40,50,60,70,80,90,100]) if int(x) in (10,20,30,40,50,60,70,80,90,100)]
        if mode in ('non_tens','both') and not any(n%10!=0 for n in range(d['min'],d['max']+1)):
            raise ValueError('Aucune valeur hors dizaine possible dans la plage des doubles.')
        if mode in ('tens','both') and not d['tensValues']:
            raise ValueError('Choisis au moins une dizaine pour les doubles.')
    if cats.get('half',{}).get('enabled'):
        h=cats['half']
        mode=h.get('halfMode') or ('both' if h.get('tens',False) else 'non_tens')
        if mode not in ('non_tens','tens','both'): mode='non_tens'
        h['halfMode']=mode; h.pop('tens',None)
        h['roundHundreds']=bool(h.get('roundHundreds',False)); h['roundThousands']=bool(h.get('roundThousands',False))
        h['tensValues']=[int(x) for x in h.get('tensValues',[10,20,30,40,50,60,70,80,90,100]) if int(x) in (10,20,30,40,50,60,70,80,90,100)]
        if mode in ('tens','both') and not h['tensValues']:
            raise ValueError('Choisis au moins une dizaine pour les moitiés.')
        h['min']=int(h.get('min',2)); h['max']=int(h.get('max',10))
        if h['min']>h['max']: raise ValueError('La plage des moitiés est invalide.')
        if mode in ('non_tens','both') and not any(n%2==0 and n%10!=0 for n in range(max(2,h['min']),h['max']+1)) and not (h['roundHundreds'] or h['roundThousands']):
            raise ValueError('Aucune moitié hors dizaine possible dans cette plage.')
    if cats.get('round_tens_add',{}).get('enabled'):
        rta=cats['round_tens_add']
        rta['aMin']=int(rta.get('aMin',10)); rta['aMax']=int(rta.get('aMax',90))
        if rta['aMin']>rta['aMax']: raise ValueError('La plage du premier terme est invalide.')
        if not any(x%10==0 for x in range(rta['aMin'],rta['aMax']+1)):
            raise ValueError('Aucune dizaine ronde dans la plage du premier terme.')
        mode=rta.get('secondMode','non_tens')
        if mode not in ('non_tens','tens','both'): mode='non_tens'
        rta['secondMode']=mode
        rta['maxResult']=int(rta.get('maxResult',100) or 0)
        if rta['maxResult'] < 0: raise ValueError('Le résultat max doit être positif.')
        rta['bMin']=int(rta.get('bMin',1)); rta['bMax']=int(rta.get('bMax',9))
        if rta['bMin']>rta['bMax']: raise ValueError('La plage hors dizaine du second terme est invalide.')
        vals=[int(x) for x in rta.get('bTensValues',[10,20,30,40,50,60,70,80,90,100]) if int(x) in (10,20,30,40,50,60,70,80,90,100)]
        rta['bTensValues']=vals
        if mode in ('non_tens','both') and not any(x%10!=0 for x in range(rta['bMin'],rta['bMax']+1)):
            raise ValueError('Aucune valeur hors dizaine dans la plage du second terme.')
        if mode in ('tens','both') and not vals:
            raise ValueError('Choisis au moins une dizaine pour le second terme.')
    if cats.get('complement_tens',{}).get('enabled') and not cats['complement_tens'].get('targets'):
        raise ValueError('Choisis au moins une dizaine cible pour les compléments.')
    if cats.get('place_value',{}).get('enabled'):
        pv=cats['place_value']; places=[p for p in pv.get('places',[]) if p in ('m','c','d','u')]
        if not places: raise ValueError('Choisis au moins un terme parmi m, c, d et u.')
        pv['places']=places; pv['absenceProbability']=max(0,min(80,(int(pv.get('absenceProbability',50))//10)*10))
    if cats.get('multiple_of',{}).get('enabled'):
        factors=[int(x) for x in cats['multiple_of'].get('factors',[]) if int(x) in (3,4)]
        if not factors: raise ValueError('Choisis au moins Triple ou Quadruple.')
        cats['multiple_of']['factors']=factors
    if cats.get('fraction',{}).get('enabled'):
        divisors=[int(x) for x in cats['fraction'].get('divisors',[]) if int(x) in (3,4)]
        if not divisors: raise ValueError('Choisis au moins Tiers ou Quart.')
        cats['fraction']['divisors']=divisors
    return data

def balanced_question_order(items):
    """Répartit les catégories sur toute la séance en évitant les séries quand c'est possible."""
    if len(items) < 2:
        return list(items)
    buckets={}
    for item in items:
        buckets.setdefault(item['kind'], []).append(item)
    for bucket in buckets.values():
        random.shuffle(bucket)
    totals={k:len(v) for k,v in buckets.items()}
    remaining=dict(totals)
    result=[]; previous=None
    while sum(remaining.values()):
        available=[k for k,n in remaining.items() if n>0]
        alternatives=[k for k in available if k!=previous]
        pool=alternatives or available
        # Catégorie la plus en retard sur sa progression idéale. Un léger aléa départage les égalités.
        done=len(result); total=sum(totals.values())
        def priority(k):
            used=totals[k]-remaining[k]
            expected=(done+1)*totals[k]/total
            return (expected-used, remaining[k]/totals[k], random.random()*0.01)
        chosen=max(pool,key=priority)
        result.append(buckets[chosen].pop())
        remaining[chosen]-=1
        previous=chosen
    return result


def operation_key(kind, payload):
    """Identifie une opération uniquement à l'intérieur de sa catégorie."""
    if kind in ('double','half'): return (kind, payload.get('n'))
    if kind in ('addition','subtraction','multiplication','decimal_multiplication','tens','tens_sub'):
        return (kind, payload.get('a'), payload.get('b'))
    if kind in ('decimal','decimal_sub'):
        return (kind, payload.get('a'), payload.get('b'), payload.get('op'))
    if kind in ('division','decimal_division'):
        return (kind, payload.get('dividend'), payload.get('divisor'))
    if kind == 'round_tens_add': return (kind,payload.get('a'),payload.get('b'))
    if kind == 'complement_tens': return (kind,payload.get('a'),payload.get('target'))
    if kind == 'place_value':
        return (kind,json.dumps(payload.get('factors',{}),sort_keys=True),tuple(payload.get('order',[])))
    if kind == 'addition3': return (kind,tuple(payload.get('numbers',[])))
    if kind == 'multiple_of': return (kind,payload.get('factor'),payload.get('n'))
    if kind == 'fraction': return (kind,payload.get('divisor'),payload.get('n'))
    return (kind, json.dumps(payload, sort_keys=True))

def generate_with_duplicate_retry(kind, cat_cfg, seen_by_kind):
    """
    Génération commune à tous les contextes.
    Tirage normal ; si la même opération existe déjà dans LA MÊME catégorie,
    au maximum 3 relances. Après la 3e relance, le doublon est accepté.
    """
    seen=seen_by_kind.setdefault(kind,set())
    for attempt in range(4):  # tirage initial + 3 relances
        payload,display,expected=gen(kind,cat_cfg)
        key=operation_key(kind,payload)
        if key not in seen or attempt==3:
            seen.add(key)
            return payload,display,expected
    raise RuntimeError('Génération impossible')

@app.post('/api/config/preview')
def config_preview():
    if (e:=require_auth()): return e
    try:
        cfg=validate_cfg_data(request.get_json(silent=True) or {})
        count=max(1,min(500,int(cfg.get('count',50))))
        alloc=allocate(count,cfg['categories'])
        questions=[]
        seen_by_kind={}
        for kind,n in alloc.items():
            for _ in range(n):
                try:
                    _,display,_=generate_with_duplicate_retry(kind,cfg['categories'][kind],seen_by_kind)
                    questions.append({'kind':kind,'display':display})
                except ValueError as ex:
                    return {'error':str(ex)},400
        questions=balanced_question_order(questions)
        return {'questions':[q['display'] for q in questions[:count]]}
    except (ValueError,TypeError,KeyError) as ex:
        return {'error':str(ex)},400

@app.get('/api/admin/class-colors')
def admin_class_colors():
    if (e:=require_admin()): return e
    c=db(); rows=c.execute('SELECT school_class,color FROM class_settings').fetchall(); c.close()
    return {r['school_class']:r['color'] for r in rows}

@app.put('/api/admin/class-colors/<school>')
def admin_class_color_save(school):
    if (e:=require_admin()): return e
    school=(school or '').upper()
    if school not in ('CP','CE1','CE2','CM1','CM2'): return {'error':'Classe inconnue'},400
    color=str((request.json or {}).get('color') or '')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',color): return {'error':'Couleur invalide'},400
    c=db(); c.execute('INSERT INTO class_settings(school_class,color) VALUES(?,?) ON CONFLICT(school_class) DO UPDATE SET color=excluded.color',(school,color)); c.commit(); c.close()
    return {'ok':True,'schoolClass':school,'color':color}


@app.get('/api/admin/levels/export')
def admin_levels_export():
    if (e:=require_admin()): return e
    c=db()
    rows=c.execute(
        'SELECT school_class,name,position,active,data FROM challenge_levels '
        'ORDER BY CASE school_class WHEN "CP" THEN 1 WHEN "CE1" THEN 2 WHEN "CE2" THEN 3 WHEN "CM1" THEN 4 ELSE 5 END,position'
    ).fetchall()
    colors={r['school_class']:r['color'] for r in c.execute('SELECT school_class,color FROM class_settings')}
    c.close()
    payload={
        'format':'calcul-mental-levels',
        'version':1,
        'class_colors':colors,
        'levels':[
            {'school_class':r['school_class'],'name':r['name'],'position':r['position'],
             'active':bool(r['active']),'config':json.loads(r['data'])}
            for r in rows
        ]
    }
    body=json.dumps(payload,ensure_ascii=False,indent=2)
    return Response(
        body,
        mimetype='application/json',
        headers={'Content-Disposition':'attachment; filename="calcul-mental-niveaux.json"'}
    )

@app.post('/api/admin/levels/import')
def admin_levels_import():
    if (e:=require_admin()): return e
    d=request.get_json(silent=True) or {}
    if d.get('format')!='calcul-mental-levels' or d.get('version')!=1 or not isinstance(d.get('levels'),list):
        return {'error':"Fichier de niveaux invalide."},400
    levels=d['levels']
    cleaned=[]
    seen_positions=set()
    try:
        for item in levels:
            school=(item.get('school_class') or '').upper()
            name=(item.get('name') or '').strip()
            position=int(item.get('position'))
            if school not in CLASSES or not name or position<1:
                raise ValueError
            key=(school,position)
            if key in seen_positions: raise ValueError
            seen_positions.add(key)
            cfg=validate_cfg_data(item.get('config') or {})
            cleaned.append((school,name,position,1 if bool(item.get('active',True)) else 0,json.dumps(cfg)))
    except (ValueError,TypeError,KeyError):
        return {'error':"Le fichier contient un niveau invalide."},400

    colors=d.get('class_colors') or {}
    clean_colors={}
    for school,color in colors.items():
        if school in CLASSES and isinstance(color,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',color):
            clean_colors[school]=color

    # Import = restauration complète des niveaux : on remplace la configuration
    # actuelle uniquement après validation intégrale du fichier.
    c=db()
    try:
        c.execute('BEGIN')
        c.execute('DELETE FROM challenge_levels')
        for row in cleaned:
            c.execute('INSERT INTO challenge_levels(school_class,name,position,active,data) VALUES(?,?,?,?,?)',row)
        for school,color in clean_colors.items():
            c.execute('INSERT INTO class_settings(school_class,color) VALUES(?,?) '
                      'ON CONFLICT(school_class) DO UPDATE SET color=excluded.color',(school,color))
        c.commit()
    except Exception:
        c.rollback(); c.close()
        return {'error':"Impossible d'importer les niveaux."},500
    c.close()
    return {'ok':True,'count':len(cleaned)}

@app.get('/api/admin/levels')
def admin_levels():
    if (e:=require_admin()): return e
    c=db(); rows=[dict(r) for r in c.execute('SELECT id,school_class,name,position,active FROM challenge_levels ORDER BY CASE school_class WHEN "CP" THEN 1 WHEN "CE1" THEN 2 WHEN "CE2" THEN 3 WHEN "CM1" THEN 4 ELSE 5 END,position')]; c.close(); return jsonify(rows)
@app.get('/api/admin/levels/<int:lid>')
def admin_level(lid):
    if (e:=require_admin()): return e
    c=db(); r=c.execute('SELECT * FROM challenge_levels WHERE id=?',(lid,)).fetchone(); c.close()
    if not r:return {'error':'Niveau introuvable'},404
    return {'id':r['id'],'school_class':r['school_class'],'name':r['name'],'position':r['position'],'active':bool(r['active']),'config':merged_cfg(json.loads(r['data']))}
@app.post('/api/admin/levels')
def admin_level_create():
    if (e:=require_admin()): return e
    d=request.json or {}; school=(d.get('school_class') or '').upper(); name=(d.get('name') or '').strip(); source=d.get('copy_from')
    if school not in CLASSES or not name:return {'error':'Classe et nom requis.'},400
    c=db(); pos=c.execute('SELECT COALESCE(MAX(position),0)+1 n FROM challenge_levels WHERE school_class=?',(school,)).fetchone()['n']
    cfg=copy.deepcopy(DEFAULT)
    for v in cfg['categories'].values():v['enabled']=False
    if source:
        r=c.execute('SELECT data FROM challenge_levels WHERE id=?',(int(source),)).fetchone()
        if r:cfg=merged_cfg(json.loads(r['data']))
    cur=c.execute('INSERT INTO challenge_levels(school_class,name,position,data) VALUES(?,?,?,?)',(school,name,pos,json.dumps(cfg))); c.commit(); lid=cur.lastrowid;c.close();return {'ok':True,'id':lid}
@app.put('/api/admin/levels/<int:lid>')
def admin_level_save(lid):
    if (e:=require_admin()): return e
    d=request.json or {}; c=db(); old=c.execute('SELECT id FROM challenge_levels WHERE id=?',(lid,)).fetchone()
    if not old:c.close();return {'error':'Niveau introuvable'},404
    try: cfg=validate_cfg_data(d.get('config',{}))
    except ValueError as ex:c.close();return {'error':str(ex)},400
    name=(d.get('name') or '').strip() or 'Niveau'; c.execute('UPDATE challenge_levels SET name=?,data=? WHERE id=?',(name,json.dumps(cfg),lid));c.commit();c.close();return {'ok':True}
@app.put('/api/admin/levels/<int:lid>/active')
def admin_level_active(lid):
    if (e:=require_admin()): return e
    d=request.json or {}
    active=1 if bool(d.get('active',True)) else 0
    c=db()
    r=c.execute('SELECT id FROM challenge_levels WHERE id=?',(lid,)).fetchone()
    if not r:
        c.close(); return {'error':'Niveau introuvable'},404
    c.execute('UPDATE challenge_levels SET active=? WHERE id=?',(active,lid))
    c.commit(); c.close()
    return {'ok':True,'active':bool(active)}

@app.post('/api/admin/levels/<int:lid>/move')
def admin_level_move(lid):
    if (e:=require_admin()): return e
    direction=(request.json or {}).get('direction'); c=db(); r=c.execute('SELECT school_class,position FROM challenge_levels WHERE id=?',(lid,)).fetchone()
    if not r:c.close();return {'error':'Niveau introuvable'},404
    target=r['position']+(-1 if direction=='up' else 1); other=c.execute('SELECT id FROM challenge_levels WHERE school_class=? AND position=?',(r['school_class'],target)).fetchone()
    if other:
        c.execute('UPDATE challenge_levels SET position=-1 WHERE id=?',(lid,));c.execute('UPDATE challenge_levels SET position=? WHERE id=?',(r['position'],other['id']));c.execute('UPDATE challenge_levels SET position=? WHERE id=?',(target,lid));c.commit()
    c.close();return {'ok':True}
@app.delete('/api/admin/levels/<int:lid>')
def admin_level_delete(lid):
    if (e:=require_admin()): return e
    c=db(); r=c.execute('SELECT school_class,position FROM challenge_levels WHERE id=?',(lid,)).fetchone()
    if not r:c.close();return {'error':'Niveau introuvable'},404
    c.execute('DELETE FROM challenge_levels WHERE id=?',(lid,));c.execute('UPDATE challenge_levels SET position=position-1 WHERE school_class=? AND position>?',(r['school_class'],r['position']));c.commit();c.close();return {'ok':True}

@app.get('/api/profiles')
def profiles():
    if (e:=require_auth()): return e
    c=db()
    pids=[r['id'] for r in c.execute('SELECT id FROM profiles WHERE account_id=?',(current_account_id(),)).fetchall()]
    for pid in pids: sync_profile_level(c,pid)
    c.commit()
    rows=[dict(x) for x in c.execute('SELECT id,name,color,school_class,coins,challenge_level_id,challenge_stars,created_at FROM profiles WHERE account_id=? ORDER BY name',(current_account_id(),))]
    c.close(); return jsonify(rows)
@app.post('/api/profiles')
def create_profile():
    if (e:=require_auth()): return e
    data=request.json or {}
    name=(data.get('name') or '').strip()
    color=(data.get('color') or '#8fdff7').strip()
    school_class=(data.get('school_class') or '').strip()
    if not name: return {'error':'Nom requis'},400
    if school_class not in ('CP','CE1','CE2','CM1','CM2'): return {'error':'Classe requise'},400
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}',color): color='#8fdff7'
    c=db()
    if c.execute('SELECT 1 FROM profiles WHERE account_id=? AND name=? COLLATE NOCASE',(current_account_id(),name)).fetchone():
        c.close(); return {'error':'Ce profil existe déjà'},409
    try:
        start_school=initial_challenge_school(school_class); first=first_level_for(c,start_school); first_id=first['id'] if first else None; cur=c.execute('INSERT INTO profiles(name,account_id,color,school_class,challenge_level_id,challenge_stars) VALUES(?,?,?,?,?,0)',(name,current_account_id(),color,school_class,first_id)); pid=cur.lastrowid; c.execute('INSERT INTO configs(profile_id,data) VALUES(?,?)',(pid,json.dumps(DEFAULT))); c.commit(); c.close(); return {'id':pid,'name':name,'color':color,'school_class':school_class}
    except sqlite3.IntegrityError: return {'error':'Ce profil existe déjà'},409
@app.put('/api/profiles/<int:pid>')
def update_profile(pid):
    if (e:=require_auth()): return e
    data=request.json or {}
    name=(data.get('name') or '').strip()
    color=(data.get('color') or '#8fdff7').strip()
    school_class=(data.get('school_class') or '').strip()
    if not name: return {'error':'Nom requis'},400
    if school_class not in ('CP','CE1','CE2','CM1','CM2'): return {'error':'Classe requise'},400
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}',color): return {'error':'Couleur invalide'},400
    c=db()
    if not c.execute('SELECT id FROM profiles WHERE id=? AND account_id=?',(pid,current_account_id())).fetchone():
        c.close(); return {'error':'Profil introuvable'},404
    try:
        old_class=c.execute('SELECT school_class FROM profiles WHERE id=?',(pid,)).fetchone()['school_class']
        if old_class != school_class:
            clear_challenge_stats(c,pid)
            start_school=initial_challenge_school(school_class); first=first_level_for(c,start_school); first_id=first['id'] if first else None; c.execute('UPDATE profiles SET name=?,color=?,school_class=?,challenge_level_id=?,challenge_stars=0 WHERE id=?',(name,color,school_class,first_id,pid))
        else:
            c.execute('UPDATE profiles SET name=?,color=?,school_class=? WHERE id=?',(name,color,school_class,pid))
        c.commit()
    except sqlite3.IntegrityError:
        c.close(); return {'error':'Ce profil existe déjà'},409
    c.close(); return {'id':pid,'name':name,'color':color,'school_class':school_class}

@app.delete('/api/profiles/<int:pid>')
def delete_profile(pid):
    if (e:=require_auth()): return e
    c=db()
    p=c.execute('SELECT id,name FROM profiles WHERE id=? AND account_id=?',(pid,current_account_id())).fetchone()
    if not p:
        c.close(); return {'error':'Profil introuvable'},404
    session_ids=[r['id'] for r in c.execute('SELECT id FROM sessions WHERE profile_id=?',(pid,)).fetchall()]
    if session_ids:
        marks=','.join('?' for _ in session_ids)
        c.execute(f'DELETE FROM questions WHERE session_id IN ({marks})',session_ids)
    c.execute('DELETE FROM sessions WHERE profile_id=?',(pid,))
    c.execute('DELETE FROM configs WHERE profile_id=?',(pid,))
    c.execute('DELETE FROM reward_progress WHERE profile_id=?',(pid,))
    c.execute('DELETE FROM profiles WHERE id=?',(pid,))
    c.commit(); c.close()
    return {'ok':True}
@app.get('/api/config/<int:pid>')
def config(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    return jsonify(get_cfg(pid))
@app.put('/api/config/<int:pid>')
def save_config(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    try: data=validate_cfg_data(request.json or {})
    except (ValueError,TypeError) as ex: return {'error':str(ex)},400
    c=db(); c.execute('INSERT INTO configs(profile_id,data) VALUES(?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data',(pid,json.dumps(data))); c.commit(); c.close(); return {'ok':True}
@app.get('/api/challenge/<int:pid>')
def challenge_status(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    day=(request.args.get('date') or '')[:10]
    c=db()
    p=c.execute('SELECT school_class,challenge_level_id,challenge_stars FROM profiles WHERE id=?',(pid,)).fetchone()
    challenge_school,row,current,level_name=resolve_profile_level(c,p)
    levels=challenge_levels_for(c,challenge_school); max_level=max(1,len(levels))
    cr=c.execute('SELECT color FROM class_settings WHERE school_class=?',(challenge_school,)).fetchone(); class_color=cr['color'] if cr else '#3189dc'
    needed=required_stars_for(challenge_school,p['school_class'])
    # Auto-réparation : si le nombre d'étoiles requis est déjà atteint, avancer proprement.
    if row and p['challenge_stars']>=needed:
        next_row=next_challenge_level(c,row)
        if next_row:
            c.execute('UPDATE profiles SET challenge_level_id=?,challenge_stars=0 WHERE id=?',
                      (next_row['id'],pid)); c.commit()
            row=next_row; challenge_school=row['school_class']; current=row['position']; level_name=row['name']
            levels=challenge_levels_for(c,challenge_school); max_level=max(1,len(levels))
            cr=c.execute('SELECT color FROM class_settings WHERE school_class=?',(challenge_school,)).fetchone(); class_color=cr['color'] if cr else '#3189dc'
            p=c.execute('SELECT school_class,challenge_level_id,challenge_stars FROM profiles WHERE id=?',(pid,)).fetchone()
            needed=required_stars_for(challenge_school,p['school_class'])
    if row and p['challenge_level_id']!=row['id']:
        c.execute('UPDATE profiles SET challenge_level_id=? WHERE id=?',(row['id'],pid)); c.commit()
    done_today=False
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',day):
        done_today=bool(c.execute("SELECT 1 FROM sessions WHERE profile_id=? AND mode='challenge' AND rewarded=1 AND challenge_day=? LIMIT 1",(pid,day)).fetchone())
    c.close()
    return {'schoolClass':challenge_school,'realSchoolClass':p['school_class'],'classColor':class_color,'level':current,'levelName':level_name,'stars':p['challenge_stars'],'requiredStars':needed,'maxLevel':max_level,'threshold':45,'doneToday':done_today,'levels':[{'id':x['id'],'name':x['name'],'position':x['position']} for x in levels]}

def clear_challenge_stats(c,pid,keep_session_id=None):
    # Lors d'une promotion automatique, on conserve uniquement la séance qui vient
    # de se terminer comme marqueur du défi quotidien ; elle appartient à l'ancien
    # niveau et n'est plus affichée dans les stats du nouveau niveau.
    if keep_session_id is None:
        c.execute("DELETE FROM questions WHERE session_id IN (SELECT id FROM sessions WHERE profile_id=? AND mode='challenge')",(pid,))
        c.execute("DELETE FROM sessions WHERE profile_id=? AND mode='challenge'",(pid,))
    else:
        c.execute("DELETE FROM questions WHERE session_id IN (SELECT id FROM sessions WHERE profile_id=? AND mode='challenge' AND id<>?)",(pid,keep_session_id))
        c.execute("DELETE FROM sessions WHERE profile_id=? AND mode='challenge' AND id<>?",(pid,keep_session_id))


@app.post('/api/session/start/<int:pid>')
def start(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    mode=(request.args.get('mode') or 'learning').lower()
    if mode not in ('learning','challenge'): mode='learning'
    challenge_class=None; challenge_level=None; challenge_level_id=None
    if mode=='challenge':
        c0=db(); p0=c0.execute('SELECT school_class,challenge_level_id FROM profiles WHERE id=?',(pid,)).fetchone()
        challenge_class,row,challenge_level,_=resolve_profile_level(c0,p0); challenge_level_id=row['id'] if row else None
        if row:
            c0.execute('UPDATE profiles SET challenge_level_id=? WHERE id=?',(challenge_level_id,pid)); c0.commit()
            cfg=merged_cfg(json.loads(row['data']))
        else:
            cfg=copy.deepcopy(DEFAULT)
        c0.close()
    else:
        cfg=get_cfg(pid)
    # Valide et normalise la configuration au démarrage.
    # Les poids de fréquence ne doivent jamais bloquer silencieusement une séance.
    try:
        cfg=validate_cfg_data(cfg)
    except (ValueError,TypeError,KeyError) as ex:
        return {'error':str(ex)},400
    count=cfg.get('count',50)
    active_kinds={k for k,v in cfg['categories'].items() if v.get('enabled') and int(v.get('weight',0) or 0)>0}
    # Un Défi doit rester standardisé : aucune reprise d'erreur d'une séance précédente.
    retries=[] if mode=='challenge' else [r for r in previous_errors(pid,'learning') if r['kind'] in active_kinds][:count]
    remaining=count-len(retries); alloc=allocate(remaining,cfg['categories']) if remaining else {}
    qs=[]
    for r in retries:
        payload=json.loads(r['payload'])
        qs.append({'kind':r['kind'],'payload':payload,'display':r['display'],'expected':r['expected'],'source':'RETRY','retry_from':r['id']})

    # Anti-doublon volontairement simple : génération normale à la demande.
    # Si le calcul existe déjà DANS LA MÊME CATÉGORIE, on retente au maximum
    # trois fois. Après ces trois relances, on accepte le doublon.
    # Aucune comparaison n'est faite entre deux catégories différentes.
    seen_by_kind={}
    for q in qs:
        seen_by_kind.setdefault(q['kind'],set()).add(operation_key(q['kind'],q['payload']))

    for kind,n in alloc.items():
        for _ in range(n):
            payload,display,expected=generate_with_duplicate_retry(kind,cfg['categories'][kind],seen_by_kind)
            qs.append({'kind':kind,'payload':payload,'display':display,'expected':expected,'source':'GENERATED','retry_from':None})

    # Garde-fou : complète toujours le quota avec exactement la même règle simple.
    if len(qs) < count:
        enabled=[k for k,v in cfg['categories'].items() if v.get('enabled') and int(v.get('weight',0) or 0)>0]
        while len(qs) < count:
            kind=random.choice(enabled)
            payload,display,expected=generate_with_duplicate_retry(kind,cfg['categories'][kind],seen_by_kind)
            qs.append({'kind':kind,'payload':payload,'display':display,'expected':expected,'source':'GENERATED','retry_from':None})
    qs=balanced_question_order(qs)
    c=db()
    # Une séance interrompue (fermeture/navigation sans STOP) ne doit jamais devenir une statistique.
    # STOP la supprime déjà immédiatement côté API ; ici on nettoie aussi les éventuels abandons orphelins.
    abandoned=[r['id'] for r in c.execute('SELECT id FROM sessions WHERE profile_id=? AND mode=? AND rewarded=0',(pid,mode))]
    for old_sid in abandoned:
        c.execute('DELETE FROM questions WHERE session_id=?',(old_sid,))
        c.execute('DELETE FROM sessions WHERE id=?',(old_sid,))
    cur=c.execute('INSERT INTO sessions(profile_id,mode,challenge_class,challenge_level_id) VALUES(?,?,?,?)',(pid,mode,challenge_class,challenge_level_id)); sid=cur.lastrowid
    for i,q in enumerate(qs): c.execute('INSERT INTO questions(session_id,position,kind,payload,display,expected,status,source,retry_from) VALUES(?,?,?,?,?,?,\'UNANSWERED\',?,?)',(sid,i,q['kind'],json.dumps(q['payload']),q['display'],q['expected'],q['source'],q['retry_from']))
    c.commit()
    rows=[]
    for x in c.execute('SELECT id,position,kind,payload,display,source FROM questions WHERE session_id=? ORDER BY position',(sid,)):
        row=dict(x)
        try: row['payload']=json.loads(row.get('payload') or '{}')
        except (TypeError,ValueError): row['payload']={}
        rows.append(row)
    c.close(); return {'sessionId':sid,'duration':cfg.get('duration',300),'questions':rows}
@app.post('/api/session/<int:sid>/answer')
def answer(sid):
    if (e:=require_auth()): return e
    c0=db(); own=c0.execute('SELECT 1 FROM sessions s JOIN profiles p ON p.id=s.profile_id WHERE s.id=? AND p.account_id=?',(sid,current_account_id())).fetchone(); c0.close()
    if not own: return {'error':'Séance inconnue'},404
    qid=int(request.json['questionId']); given=float(request.json['answer']); ms=max(0,int(request.json.get('responseMs',0)))
    c=db(); q=c.execute('SELECT expected FROM questions WHERE id=? AND session_id=?',(qid,sid)).fetchone()
    if not q: c.close(); return {'error':'Question inconnue'},404
    oldq=c.execute('SELECT expected,given_answer,attempts,had_error,first_wrong_answer FROM questions WHERE id=? AND session_id=?',(qid,sid)).fetchone()
    attempts=(oldq['attempts'] or 0)+1
    ok=abs(given-float(oldq['expected'])) < 1e-9; had_error=bool(oldq['had_error']) or not ok
    # given_answer devient volontairement la PREMIÈRE réponse saisie et n'est plus jamais écrasée.
    first_answer=oldq['given_answer'] if oldq['given_answer'] is not None else given
    first_wrong=oldq['first_wrong_answer']
    if not ok and first_wrong is None: first_wrong=given
    # Une question reste statistiquement en erreur dès le premier essai faux, même si elle est corrigée ensuite.
    status=('INCORRECT' if had_error else 'CORRECT') if ok or attempts>=2 else 'UNANSWERED'
    c.execute('UPDATE questions SET given_answer=?,last_answer=?,first_wrong_answer=?,status=?,response_ms=?,attempts=?,had_error=? WHERE id=?',(first_answer,given,first_wrong,status,ms,attempts,1 if had_error else 0,qid)); c.commit(); c.close(); return {'correct':ok,'expected':oldq['expected'],'attempts':attempts,'remaining':max(0,2-attempts)}
@app.post('/api/session/<int:sid>/help')
def mark_help(sid):
    if (e:=require_auth()): return e
    qid=int((request.json or {}).get('questionId',0))
    c=db()
    row=c.execute("""SELECT q.id FROM questions q JOIN sessions s ON s.id=q.session_id
                     JOIN profiles p ON p.id=s.profile_id
                     WHERE q.id=? AND s.id=? AND p.account_id=?""",(qid,sid,current_account_id())).fetchone()
    if not row: c.close(); return {'error':'Question inconnue'},404
    c.execute('UPDATE questions SET help_used=1 WHERE id=? AND session_id=?',(qid,sid)); c.commit(); c.close()
    # La génération et le choix de la branche pédagogique vivent uniquement dans pedagogy.js.
    # Cette route ne fait plus que mémoriser l'utilisation de l'aide.
    return {'ok':True}

@app.delete('/api/session/<int:sid>')
def cancel_session(sid):
    if (e:=require_auth()): return e
    c0=db(); own=c0.execute('SELECT 1 FROM sessions s JOIN profiles p ON p.id=s.profile_id WHERE s.id=? AND p.account_id=?',(sid,current_account_id())).fetchone(); c0.close()
    if not own: return {'error':'Séance inconnue'},404
    c=db(); c.execute('DELETE FROM questions WHERE session_id=?',(sid,)); c.execute('DELETE FROM sessions WHERE id=?',(sid,)); c.commit(); c.close(); return {'ok':True}

@app.post('/api/session/<int:sid>/finish')
def finish(sid):
    if (e:=require_auth()): return e
    data=request.json or {}; ms=max(0,int(data.get('activeMs',0)))
    local_day=str(data.get('localDate',''))[:10]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',local_day): local_day=None
    c=db(); s=c.execute('SELECT s.id,s.profile_id,s.rewarded,s.mode,s.challenge_class,s.challenge_level_id,s.star_awarded,s.daily_bonus_awarded FROM sessions s JOIN profiles p ON p.id=s.profile_id WHERE s.id=? AND p.account_id=?',(sid,current_account_id())).fetchone()
    if not s: c.close(); return {'error':'Séance inconnue'},404
    earned=0
    if not s['rewarded']:
        earned=c.execute("SELECT COUNT(*) n FROM questions WHERE session_id=? AND status='CORRECT'",(sid,)).fetchone()['n']
        c.execute('UPDATE profiles SET coins=coins+? WHERE id=?',(earned,s['profile_id']))
        c.execute('UPDATE sessions SET active_ms=?,rewarded=1 WHERE id=?',(ms,sid))
    else:
        c.execute('UPDATE sessions SET active_ms=? WHERE id=?',(ms,sid))
    daily_bonus=0
    star_awarded=False
    if s['mode']=='challenge':
        # finish() n'est jamais appelé par STOP : seuls 50 calculs traités ou le timer écoulé valident le défi.
        already_done=bool(local_day and c.execute("SELECT 1 FROM sessions WHERE profile_id=? AND mode='challenge' AND rewarded=1 AND challenge_day=? AND id<>? LIMIT 1",(s['profile_id'],local_day,sid)).fetchone())
        c.execute('UPDATE sessions SET challenge_day=? WHERE id=?',(local_day,sid))
        if local_day and not already_done and not s['daily_bonus_awarded']:
            daily_bonus=10
            c.execute('UPDATE profiles SET coins=coins+10 WHERE id=?',(s['profile_id'],))
            c.execute('UPDATE sessions SET daily_bonus_awarded=1 WHERE id=?',(sid,))
    star_bonus=0
    level_bonus=0
    class_completed=False
    completed_class=None
    next_class=None
    completed_color=None
    next_color=None
    new_record=False
    previous_record=0
    record_score=0
    record_level_position=None
    record_level_color=None
    if s['mode']=='challenge':
        record_score=c.execute("SELECT COUNT(*) n FROM questions WHERE session_id=? AND status='CORRECT'",(sid,)).fetchone()['n']
        # Record du même niveau de Défi uniquement, en excluant la séance qui vient de finir.
        # Un record est célébré à partir de 15 bonnes réponses incluses.
        previous_attempts=c.execute("""SELECT COUNT(*) n FROM sessions ss
            WHERE ss.profile_id=? AND ss.mode='challenge' AND ss.challenge_level_id=?
              AND ss.rewarded=1 AND ss.id<>?
        """,(s['profile_id'],s['challenge_level_id'],sid)).fetchone()['n']
        prev=c.execute("""SELECT MAX(score) best FROM (
            SELECT ss.id, COUNT(CASE WHEN q.status='CORRECT' THEN 1 END) score
            FROM sessions ss LEFT JOIN questions q ON q.session_id=ss.id
            WHERE ss.profile_id=? AND ss.mode='challenge' AND ss.challenge_level_id=?
              AND ss.rewarded=1 AND ss.id<>?
            GROUP BY ss.id
        )""",(s['profile_id'],s['challenge_level_id'],sid)).fetchone()
        previous_record=int((prev['best'] if prev else 0) or 0)
        # La toute première partie d'un niveau établit la référence : elle ne peut jamais être un « nouveau record ».
        # À partir de la deuxième partie : score >= 15 ET strictement supérieur au meilleur score précédent.
        new_record=previous_attempts>0 and record_score>=15 and record_score>previous_record
        rr=c.execute('SELECT position,school_class FROM challenge_levels WHERE id=?',(s['challenge_level_id'],)).fetchone() if s['challenge_level_id'] else None
        record_level_position=rr['position'] if rr else 1
        if rr:
            rc=c.execute('SELECT color FROM class_settings WHERE school_class=?',(rr['school_class'],)).fetchone()
            record_level_color=rc['color'] if rc else '#3189dc'
    if s['mode']=='challenge' and not s['star_awarded']:
        correct=record_score
        p=c.execute('SELECT school_class,challenge_level_id,challenge_stars FROM profiles WHERE id=?',(s['profile_id'],)).fetchone()
        current_row=c.execute('SELECT id,school_class,name,position,data FROM challenge_levels WHERE id=?',(s['challenge_level_id'],)).fetchone() if s['challenge_level_id'] else None
        same_level=(p['challenge_level_id']==s['challenge_level_id'])
        challenge_school=current_row['school_class'] if current_row else (s['challenge_class'] or p['school_class'])
        needed=required_stars_for(challenge_school,p['school_class'])
        if correct>=45 and same_level and p['challenge_stars']<needed:
            new_stars=p['challenge_stars']+1
            c.execute('UPDATE profiles SET challenge_stars=? WHERE id=?',(new_stars,s['profile_id']))
            star_awarded=True
            star_bonus=10
            c.execute('UPDATE profiles SET coins=coins+10 WHERE id=?',(s['profile_id'],))
            if new_stars>=needed:
                next_row=next_challenge_level(c,current_row)
                if next_row:
                    level_bonus=20
                    c.execute('UPDATE profiles SET coins=coins+20,challenge_level_id=?,challenge_stars=0 WHERE id=?',
                              (next_row['id'],s['profile_id']))
                    # Nouveau niveau = nouveau référentiel statistique. On efface
                    # l'historique Défi précédent, sans toucher aux Entraînements.
                    # La séance courante reste seulement comme marqueur du défi du jour.
                    clear_challenge_stats(c,s['profile_id'],keep_session_id=sid)
                    if current_row and next_row['school_class']!=current_row['school_class']:
                        class_completed=True; completed_class=current_row['school_class']; next_class=next_row['school_class']
                        cc=c.execute('SELECT color FROM class_settings WHERE school_class=?',(completed_class,)).fetchone()
                        nc=c.execute('SELECT color FROM class_settings WHERE school_class=?',(next_class,)).fetchone()
                        completed_color=cc['color'] if cc else '#3189dc'; next_color=nc['color'] if nc else '#3189dc'
        c.execute('UPDATE sessions SET star_awarded=1 WHERE id=?',(sid,))
    pstate=c.execute('SELECT coins,challenge_level_id,challenge_stars,school_class FROM profiles WHERE id=?',(s['profile_id'],)).fetchone()
    balance=pstate['coins']
    current_level_row=c.execute('SELECT position FROM challenge_levels WHERE id=?',(pstate['challenge_level_id'],)).fetchone() if pstate['challenge_level_id'] else None
    current_level_position=current_level_row['position'] if current_level_row else 1
    promoted_level_name=None
    if s['mode']=='challenge' and pstate['challenge_level_id'] and pstate['challenge_level_id']!=s['challenge_level_id']:
        nr=c.execute('SELECT name FROM challenge_levels WHERE id=?',(pstate['challenge_level_id'],)).fetchone()
        promoted_level_name=nr['name'] if nr else 'Niveau suivant'
    c.commit(); c.close(); return {'ok':True,'coinsEarned':earned,'dailyBonus':daily_bonus,'starBonus':star_bonus,'levelBonus':level_bonus,'balance':balance,'starAwarded':star_awarded,'levelUnlocked':bool(promoted_level_name),'unlockedLevelName':promoted_level_name,'classCompleted':class_completed,'completedClass':completed_class,'nextClass':next_class,'completedColor':completed_color,'nextColor':next_color,'completedColorName':color_name_fr(completed_color) if completed_color else None,'nextColorName':color_name_fr(next_color) if next_color else None,'newRecord':new_record,'recordScore':record_score,'previousRecord':previous_record,'recordLevel':record_level_position,'recordColor':record_level_color,'challenge':{'level':current_level_position,'stars':pstate['challenge_stars']}}

@app.get('/api/rewards/<int:pid>')
def rewards(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    c=db(); p=c.execute('SELECT coins FROM profiles WHERE id=?',(pid,)).fetchone(); r=c.execute('SELECT current_card,revealed,completed FROM reward_progress WHERE profile_id=?',(pid,)).fetchone(); c.close()
    if r: state={'currentCard':r['current_card'],'revealed':json.loads(r['revealed'] or '[]'),'completed':json.loads(r['completed'] or '[]')}
    else: state={'currentCard':None,'revealed':[],'completed':[]}
    return {'coins':p['coins'],'cards':[{'id': 'robot-1', 'type': 'robot', 'label': 'Bolt', 'image': '/rewards/robot-1.jpg'},{'id': 'robot-2', 'type': 'robot', 'label': 'Rex', 'image': '/rewards/robot-2.jpg'},{'id': 'robot-3', 'type': 'robot', 'label': 'Orion', 'image': '/rewards/robot-3.jpg'},{'id': 'robot-4', 'type': 'robot', 'label': 'Z3RO', 'image': '/rewards/robot-4.jpg'},{'id': 'robot-5', 'type': 'robot', 'label': 'Pixel', 'image': '/rewards/robot-5.jpg'},{'id': 'robot-6', 'type': 'robot', 'label': 'Atlas', 'image': '/rewards/robot-6.jpg'},{'id': 'robot-7', 'type': 'robot', 'label': 'Moka', 'image': '/rewards/robot-7.jpg'},{'id': 'robot-8', 'type': 'robot', 'label': 'Teko', 'image': '/rewards/robot-8.jpg'},{'id': 'robot-9', 'type': 'robot', 'label': 'K-7', 'image': '/rewards/robot-9.jpg'},{'id': 'robot-10', 'type': 'robot', 'label': 'Orbi', 'image': '/rewards/robot-10.jpg'},{'id': 'fairy-1', 'type': 'fairy', 'label': 'Lunéa', 'image': '/rewards/fairy-1.jpg'},{'id': 'fairy-2', 'type': 'fairy', 'label': 'Églantine', 'image': '/rewards/fairy-2.jpg'},{'id': 'fairy-3', 'type': 'fairy', 'label': 'Nyméa', 'image': '/rewards/fairy-3.jpg'},{'id': 'fairy-4', 'type': 'fairy', 'label': 'Aélia', 'image': '/rewards/fairy-4.jpg'},{'id': 'fairy-5', 'type': 'fairy', 'label': 'Sélène', 'image': '/rewards/fairy-5.jpg'},{'id': 'fairy-6', 'type': 'fairy', 'label': 'Rosélia', 'image': '/rewards/fairy-6.jpg'},{'id': 'fairy-7', 'type': 'fairy', 'label': 'Feuille', 'image': '/rewards/fairy-7.jpg'},{'id': 'fairy-8', 'type': 'fairy', 'label': 'Maréa', 'image': '/rewards/fairy-8.jpg'},{'id': 'fairy-9', 'type': 'fairy', 'label': 'Étoile', 'image': '/rewards/fairy-9.jpg'},{'id': 'fairy-10', 'type': 'fairy', 'label': 'Violette', 'image': '/rewards/fairy-10.jpg'},{'id': 'dinosaur-1', 'type': 'dinosaur', 'label': 'Tyrannosaure', 'image': '/rewards/dinosaur-1.jpg'},{'id': 'dinosaur-2', 'type': 'dinosaur', 'label': 'Tricératops', 'image': '/rewards/dinosaur-2.jpg'},{'id': 'dinosaur-3', 'type': 'dinosaur', 'label': 'Vélociraptor', 'image': '/rewards/dinosaur-3.jpg'},{'id': 'dinosaur-4', 'type': 'dinosaur', 'label': 'Diplodocus', 'image': '/rewards/dinosaur-4.jpg'},{'id': 'dinosaur-5', 'type': 'dinosaur', 'label': 'Stégosaure', 'image': '/rewards/dinosaur-5.jpg'},{'id': 'dinosaur-6', 'type': 'dinosaur', 'label': 'Ankylosaure', 'image': '/rewards/dinosaur-6.jpg'},{'id': 'dinosaur-7', 'type': 'dinosaur', 'label': 'Spinosaurus', 'image': '/rewards/dinosaur-7.jpg'},{'id': 'dinosaur-8', 'type': 'dinosaur', 'label': 'Parasaurolophus', 'image': '/rewards/dinosaur-8.jpg'},{'id': 'dinosaur-9', 'type': 'dinosaur', 'label': 'Ptéranodon', 'image': '/rewards/dinosaur-9.jpg'},{'id': 'dinosaur-10', 'type': 'dinosaur', 'label': 'Brachiosaure', 'image': '/rewards/dinosaur-10.jpg'},{'id': 'animal-1', 'type': 'animal', 'label': 'Panda roux', 'image': '/rewards/animal-1.jpg'},{'id': 'animal-2', 'type': 'animal', 'label': 'Okapi', 'image': '/rewards/animal-2.jpg'},{'id': 'animal-3', 'type': 'animal', 'label': 'Fennec', 'image': '/rewards/animal-3.jpg'},{'id': 'animal-4', 'type': 'animal', 'label': 'Axolotl', 'image': '/rewards/animal-4.jpg'},{'id': 'animal-5', 'type': 'animal', 'label': 'Ornithorynque', 'image': '/rewards/animal-5.jpg'},{'id': 'animal-6', 'type': 'animal', 'label': 'Quokka', 'image': '/rewards/animal-6.jpg'},{'id': 'animal-7', 'type': 'animal', 'label': 'Capybara', 'image': '/rewards/animal-7.jpg'},{'id': 'animal-8', 'type': 'animal', 'label': 'Piranha', 'image': '/rewards/animal-8.jpg'},{'id': 'animal-9', 'type': 'animal', 'label': 'Toucan', 'image': '/rewards/animal-9.jpg'},{'id': 'animal-10', 'type': 'animal', 'label': 'Margay', 'image': '/rewards/animal-10.jpg'}],**state}

@app.post('/api/rewards/<int:pid>/choose')
def choose_reward(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    data=request.json or {}
    kind=data.get('type')
    card=data.get('card')
    if kind not in {'robot','fairy','dinosaur','animal'}: return {'error':'Type de récompense inconnu'},400
    c=db(); r=c.execute('SELECT current_card,completed FROM reward_progress WHERE profile_id=?',(pid,)).fetchone()
    if r and r['current_card']:
        c.close(); return {'error':'Termine d’abord la carte en cours.'},409
    completed=json.loads(r['completed'] or '[]') if r else []
    candidates=[f'{kind}-{i}' for i in range(1,11) if f'{kind}-{i}' not in completed]
    if not candidates:
        c.close(); return {'error':'Toutes les cartes de ce type sont déjà révélées.'},409
    if card:
        if card not in candidates or not card.startswith(kind+'-'):
            c.close(); return {'error':'Carte indisponible.'},400
    else:
        card=random.choice(candidates)
    if r: c.execute("UPDATE reward_progress SET current_card=?,revealed='[]' WHERE profile_id=?",(card,pid))
    else: c.execute("INSERT INTO reward_progress(profile_id,current_card,revealed,completed) VALUES(?,?,'[]','[]')",(pid,card))
    c.commit(); c.close(); return {'ok':True,'card':card}


@app.post('/api/rewards/<int:pid>/reveal')
def reveal_reward(pid):
    """Révèle en une fois autant de cases que le solde le permet (10 pièces par case)."""
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    c=db(); p=c.execute('SELECT coins FROM profiles WHERE id=?',(pid,)).fetchone(); r=c.execute('SELECT current_card,revealed,completed FROM reward_progress WHERE profile_id=?',(pid,)).fetchone()
    if not r or not r['current_card']: c.close(); return {'error':'Choisis une carte.'},400
    if p['coins']<10: c.close(); return {'error':'Il faut 10 pièces.'},400
    revealed=json.loads(r['revealed'] or '[]'); remaining=[i for i in range(20) if i not in revealed]
    if not remaining: c.close(); return {'error':'Carte déjà terminée.'},400
    count=min(len(remaining),p['coins']//10)
    pieces=random.sample(remaining,count)
    revealed.extend(pieces); completed=json.loads(r['completed'] or '[]'); card=r['current_card']; done=len(revealed)>=20
    cost=count*10
    c.execute('UPDATE profiles SET coins=coins-? WHERE id=?',(cost,pid))
    if done:
        if card not in completed: completed.append(card)
        c.execute("UPDATE reward_progress SET current_card=NULL,revealed='[]',completed=? WHERE profile_id=?",(json.dumps(completed),pid))
    else: c.execute('UPDATE reward_progress SET revealed=? WHERE profile_id=?',(json.dumps(revealed),pid))
    balance=p['coins']-cost; c.commit(); c.close()
    return {'ok':True,'pieces':pieces,'piece':pieces[0] if pieces else None,'revealedCount':count,'spent':cost,'done':done,'coins':balance,'revealed':([] if done else revealed),'completed':completed}

@app.get('/api/stats/<int:pid>')
def stats(pid):
    if (e:=require_auth()): return e
    if not owns_profile(pid): return {'error':'Profil introuvable'},404
    mode=(request.args.get('mode') or 'learning').lower()
    if mode not in ('learning','challenge'): mode='learning'
    c=db()
    if mode=='challenge':
        # Les stats Défi décrivent uniquement le niveau actuellement travaillé.
        p=c.execute('SELECT challenge_level_id FROM profiles WHERE id=?',(pid,)).fetchone()
        current_level_id=p['challenge_level_id'] if p else None
        ss=[dict(x) for x in c.execute('SELECT id,started_at,active_ms,mode,rewarded FROM sessions WHERE profile_id=? AND mode=? AND challenge_level_id=? ORDER BY id DESC',(pid,mode,current_level_id))] if current_level_id else []
    else:
        ss=[dict(x) for x in c.execute('SELECT id,started_at,active_ms,mode,rewarded FROM sessions WHERE profile_id=? AND mode=? ORDER BY id DESC',(pid,mode))]
    out=[]
    for s in ss:
        qs=[dict(x) for x in c.execute("SELECT * FROM questions WHERE session_id=? AND status!='UNANSWERED'",(s['id'],))]
        correct=[q for q in qs if q['status']=='CORRECT']
        times=[q['response_ms'] for q in qs if q['response_ms'] is not None]
        cats=[]
        for kind in dict.fromkeys(q['kind'] for q in qs):
            kqs=[q for q in qs if q['kind']==kind]; kc=sum(1 for q in kqs if q['status']=='CORRECT')
            kt=[q['response_ms'] for q in kqs if q['response_ms'] is not None]; cats.append({'kind':kind,'attempted':len(kqs),'correct':kc,'accuracy':round(100*kc/len(kqs),1) if kqs else 0,'medianMs':int(statistics.median(kt)) if kt else None,'helpUsed':sum(1 for q in kqs if q.get('help_used'))})
        out.append({'id':s['id'],'date':s['started_at'],'activeMs':s['active_ms'],'attempted':len(qs),'correct':len(correct),'incorrect':len(qs)-len(correct),'accuracy':round(100*len(correct)/len(qs),1) if qs else 0,'medianMs':int(statistics.median(times)) if times else None,'avgMs':int(sum(times)/len(times)) if times else None,'helpUsed':sum(1 for q in qs if q.get('help_used')),'categories':cats,'inProgress':not bool(s.get('rewarded',0))})
    c.close(); return {'sessions':out,'mode':mode}

@app.delete('/api/session/<int:sid>/stats')
def delete_session_stats(sid):
    if (e:=require_auth()): return e
    c=db()
    s=c.execute('SELECT id,profile_id FROM sessions WHERE id=?',(sid,)).fetchone()
    if not s or not owns_profile(s['profile_id']):
        c.close(); return {'error':'Séance inconnue'},404
    # Suppression complète de la séance statistique. Les anciennes BDD ne
    # garantissent pas toutes le ON DELETE CASCADE sur questions.
    c.execute('DELETE FROM questions WHERE session_id=?',(sid,))
    c.execute('DELETE FROM sessions WHERE id=?',(sid,))
    c.commit(); c.close()
    return {'ok':True}

@app.get('/api/session/<int:sid>/stats')
def session_stats(sid):
    if (e:=require_auth()): return e
    c=db(); s=c.execute('SELECT id,profile_id,started_at,active_ms,rewarded FROM sessions WHERE id=?',(sid,)).fetchone()
    if not s: c.close(); return {'error':'Séance inconnue'},404
    if not owns_profile(s['profile_id']): c.close(); return {'error':'Séance inconnue'},404
    qs=[dict(x) for x in c.execute("SELECT id,position,kind,display,expected,given_answer,last_answer,first_wrong_answer,status,response_ms,source,attempts,had_error,help_used FROM questions WHERE session_id=? AND status!='UNANSWERED' ORDER BY position",(sid,))]
    correct=[q for q in qs if q['status']=='CORRECT']; times=[q['response_ms'] for q in correct if q['response_ms'] is not None]
    kinds=[]
    for kind in dict.fromkeys(q['kind'] for q in qs):
        kqs=[q for q in qs if q['kind']==kind]; kc=sum(1 for q in kqs if q['status']=='CORRECT')
        kinds.append({'kind':kind,'attempted':len(kqs),'correct':kc,'incorrect':len(kqs)-kc,'accuracy':round(100*kc/len(kqs),1) if kqs else 0,'helpUsed':sum(1 for q in kqs if q.get('help_used'))})
    result={'id':s['id'],'date':s['started_at'],'activeMs':s['active_ms'],'attempted':len(qs),'correct':len(correct),'incorrect':len(qs)-len(correct),'accuracy':round(100*len(correct)/len(qs),1) if qs else 0,'medianMs':int(statistics.median(times)) if times else None,'helpUsed':sum(1 for q in qs if q.get('help_used')),'categories':kinds,'questions':qs,'inProgress':not bool(s['rewarded'])}
    c.close(); return result

init_db()
def seed_challenge_levels():
    c=db(); n=c.execute('SELECT COUNT(*) n FROM challenge_levels').fetchone()['n']
    if n==0:
        for school in CLASSES:
            for level in range(1,6):
                c.execute('INSERT INTO challenge_levels(school_class,name,position,data) VALUES(?,?,?,?)',(school,f'{school}-{level}',level,json.dumps(seed_challenge_cfg(school,level))))
        c.commit()
    c.close()
seed_challenge_levels()
def migrate_profile_level_ids():
    c=db()
    for r in c.execute('SELECT id FROM profiles').fetchall():
        sync_profile_level(c,r['id'])
    c.commit(); c.close()
migrate_profile_level_ids()
if __name__=='__main__': app.run(host='127.0.0.1',port=5050,debug=True)
