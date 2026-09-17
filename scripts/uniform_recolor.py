from PIL import Image, ImageFilter
import numpy as np

def rgb2hsv(a):
    r,g,b=a[...,0],a[...,1],a[...,2]
    mx=a.max(-1); mn=a.min(-1); d=mx-mn+1e-6
    h=np.zeros_like(mx)
    m=(mx==r); h[m]=((g-b)[m]/d[m])%6
    m=(mx==g); h[m]=((b-r)[m]/d[m])+2
    m=(mx==b); h[m]=((r-g)[m]/d[m])+4
    return h/6.0, d/(mx+1e-6), mx

def hsv2rgb(h,s,v):
    i=np.floor(h*6.0); f=h*6.0-i
    p=v*(1-s); q=v*(1-f*s); t=v*(1-(1-f)*s)
    i=(i%6).astype(int)
    out=np.zeros(h.shape+(3,),np.float32)
    for k,(R,G,B) in enumerate([(v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q)]):
        m=(i==k); out[...,0][m]=R[m]; out[...,1][m]=G[m]; out[...,2][m]=B[m]
    return out

def recolor_uniform(path, navy_h=0.615, sat=0.62, val_scale=0.66,
                    hue_hi=0.90, hue_lo=0.03, smin=0.35, vmin=0.28, feather=2.0):
    im=Image.open(path).convert('RGB')
    a=np.asarray(im).astype(np.float32)/255.
    h,s,v=rgb2hsv(a)
    m=(((h>hue_hi)|(h<hue_lo)) & (s>smin) & (v>vmin)).astype(np.float32)
    # despeckle: open (min then max) via PIL, then feather
    mi=Image.fromarray((m*255).astype(np.uint8))
    mi=mi.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(7))
    mi=mi.filter(ImageFilter.GaussianBlur(feather))
    m=np.asarray(mi).astype(np.float32)/255.
    h2=np.full_like(h, navy_h)
    s2=np.clip(s*0.0+sat, 0, 1)
    v2=np.clip(v*val_scale, 0, 1)
    new=hsv2rgb(h2,s2,v2)
    out=a*(1-m[...,None]) + new*m[...,None]
    return Image.fromarray((np.clip(out,0,1)*255).astype(np.uint8)), m


# 施術者のエンジ色の制服を、自社サイトに合わせた紺色に置き換える。
#
#   python3 -c "
#   import sys; sys.path.insert(0,'scripts')
#   from uniform_recolor import recolor_uniform
#   recolor_uniform('in.jpg', smin=0.45, hue_lo=0.01)[0].save('out.jpg', quality=92)
#   "
#
# パラメータの勘所(2026-09-17に実写4枚で調整):
# - smin=0.45 が要。0.35 まで下げると爪や指先のピンクを拾って青くなる。
#   0.52 まで上げると制服に赤の取り残しが出る。
# - 完成済みバナー(文字入り)に使う場合は、ピンクの見出し文字が同じ色域に入るため、
#   制服のある範囲だけを矩形で切って mask に掛け合わせること。
#   funiki_03 では y:3〜45%, x:2〜42.5% に限定して「気」の字を巻き込むのを回避した。
