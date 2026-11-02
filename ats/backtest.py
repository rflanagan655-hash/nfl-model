import json,re
A=json.load(open('/home/claude/nfl-model/ats/atsstats_2026.json'))['teams']
DIV={'NE':'AE','BUF':'AE','MIA':'AE','NYJ':'AE','BAL':'AN','CIN':'AN','CLE':'AN','PIT':'AN','HOU':'AS','IND':'AS','JAX':'AS','TEN':'AS','DEN':'AW','KC':'AW','LV':'AW','LAC':'AW','DAL':'NE','NYG':'NE','PHI':'NE','WAS':'NE','CHI':'NN','DET':'NN','GB':'NN','MIN':'NN','ATL':'NS','CAR':'NS','NO':'NS','TB':'NS','ARI':'NW','LAR':'NW','SF':'NW','SEA':'NW'}
def match(tag,home,fav,s,div):
    t=tag.lower().strip()
    if 'vs elite' in t or 'after long' in t or 'bad defensive' in t or 'over' in t.split() or t.endswith('under') and 'underdog' not in t or 'totals' in t or 'defensive favorite' in t: return False
    if 'spot' in t and ('division' in t or 'nfc west' in t or 'conference' in t):
        if home: return False
        return div if ('division' in t or 'nfc west' in t) else False
    if 'select home dog' in t: t='home dog'
    isfav='favorite' in t; isdog='dog' in t
    if not(isfav or isdog): return False
    if isfav!=fav: return False
    if 'home' in t and not home: return False
    if 'road' in t and home: return False
    if 'inflated' in t and s<7: return False
    if ('large' in t or 'big' in t) and s<7: return False
    if 'short' in t and s>3.5: return False
    return True
def role(team,home,hs,opp):
    if hs==0: return 0,[]
    fav=(hs<0)==home; s=abs(hs); div=DIV[team]==DIV[opp]
    d=A[team]; b=any(match(x,home,fav,s,div) for x in d['best'].split('/')); a=any(match(x,home,fav,s,div) for x in d['avoid'].split('/'))
    return (1 if b else 0)-(1 if a else 0),[('best' if b else ''),('avoid' if a else '')]
def sig(away,home,hs,R=.5,S=.5):
    rh,_=role(home,True,hs,away); ra,_=role(away,False,hs,home)
    return R*(rh-ra)+S*(A[home]['c']-A[away]['c'])/100
if __name__=='__main__':
    s=open('index.html').read()
    i=s.index('const TRACK=')+12; T,_=json.JSONDecoder().raw_decode(s[i:])
    g=[x for x in T['nfl'] if x.get('final')]
    def rec(fn):
        w=l=p=0
        for x in g:
            m=fn(x); act=x['final']['h']-x['final']['a']; c=act+x['mkt_hs']
            if c==0: p+=1; continue
            pickH=(m+x['mkt_hs'])>0
            if pickH==(c>0): w+=1
            else: l+=1
        return w,l,p
    print('base',rec(lambda x:x['model_margin']))
    for R,S in [(.5,.5),(.5,0),(0,.5),(1,1)]:
        print(R,S,rec(lambda x:x['model_margin']+sig(x['away'],x['home'],x['mkt_hs'],R,S)))
    print('signal alone',rec(lambda x:-x['mkt_hs']+sig(x['away'],x['home'],x['mkt_hs'])*100))
    flips=0
    for x in g:
        a=x['model_margin']+x['mkt_hs']; b=a+sig(x['away'],x['home'],x['mkt_hs'])
        if (a>0)!=(b>0): flips+=1
    print('flips',flips,len(g))
