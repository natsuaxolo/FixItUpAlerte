"""Crée logo.ico à partir de logo.png (n'importe quelle image, carrée ou non)."""
from PIL import Image

im = Image.open("logo.png").convert("RGBA")
side = max(im.size)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
resample = getattr(Image, "Resampling", Image).LANCZOS
canvas = canvas.resize((256, 256), resample)
canvas.save("logo.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("logo.ico cree")
