from PIL import Image, ImageEnhance
import numpy as np

def retouch(path, wb=0.85, lift=0.88, contrast=1.10, sat=1.06, warm=1.012):
    im = Image.open(path).convert('RGB')
    a = np.asarray(im).astype(np.float32)
    # --- white balance: pull each channel's bright end toward a common neutral
    ref = np.percentile(a.reshape(-1,3), 97, axis=0)
    target = ref.mean()
    gain = 1.0 + wb * (target/ref - 1.0)
    a = a * gain
    # --- exposure lift (gamma <1 brightens midtones, keeps highlights)
    a = 255.0 * np.clip(a/255.0, 0, 1) ** lift
    # --- gentle S-curve around mid grey
    n = np.clip(a/255.0, 0, 1)
    n = np.clip((n - 0.5) * contrast + 0.5, 0, 1)
    a = n * 255.0
    # --- slight warmth
    a[...,0] *= warm
    a[...,2] /= warm
    out = Image.fromarray(np.clip(a,0,255).astype(np.uint8))
    out = ImageEnhance.Color(out).enhance(sat)
    return out


# 使い方(HPB特集画像などの軽補正):
#   python3 -c "
#   import sys; sys.path.insert(0,'scripts')
#   from photo_retouch import retouch
#   retouch('data/brand-assets/shinkyu-photos/鍼治療/鍼治療 (17).JPG').save('out.jpg', quality=92)
#   "
#
# 合成や文字入れはしない。色かぶり除去・明るさ・コントラスト・彩度のみを数値で調整する。
# 他社の特集画像も、ゴリゴリの加工ではなくこの程度の色味・ハイライト調整に留めている
# (2026-09-17 栗林さん観察)。強すぎる場合は lift を 1.0 に近づけ、contrast を下げる。
