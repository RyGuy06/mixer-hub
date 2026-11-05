"""The same four-fader artwork for the EXE, Windows title bar and tray."""
from PIL import Image, ImageDraw

from app_paths import resource_path


def render_icon(size=256):
    # Supersample the geometry so the small ICO frames retain clean edges.
    factor = 4
    image = Image.new("RGBA", (256 * factor, 256 * factor), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def box(values):
        return tuple(value * factor for value in values)

    draw.rounded_rectangle(box((8, 8, 248, 248)), radius=44 * factor, fill="#1C1C21")
    for x, y in [(50, 92), (102, 160), (154, 72), (206, 128)]:
        draw.line(box((x, 52, x, 204)), fill="#34343D", width=10 * factor)
        draw.line(box((x, y, x, 204)), fill="#91BFFF", width=10 * factor)
        draw.rounded_rectangle(box((x - 15, y - 9, x + 15, y + 9)),
                               radius=3 * factor, fill="#F1F1F3")
    return image.resize((size, size), Image.Resampling.LANCZOS)


def icon_image(size=64):
    try:
        with Image.open(resource_path("assets/app_icon.png")) as source:
            return source.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    except OSError:
        return render_icon(size)
