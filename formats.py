"""Download format catalog, request validation and yt-dlp configuration."""
from pathlib import Path

VERSION = "2.0.0"
FORMATS = [
    {"id": "mp4", "kind": "video", "label": "MP4", "description": "Video + Audio · vielseitig abspielbar"},
    {"id": "mkv", "kind": "video", "label": "MKV", "description": "Video + Audio · flexibel für moderne Codecs"},
    {"id": "webm", "kind": "video", "label": "WebM", "description": "Video + Audio · aus verfügbaren WebM-Spuren"},
    {"id": "mp3", "kind": "audio", "label": "MP3", "description": "Kompakt und mit fast jedem Player kompatibel", "qualities": ["320", "256", "192", "128", "96"], "default_quality": "320"},
    {"id": "m4a", "kind": "audio", "label": "M4A / AAC", "description": "AAC-Originalspur, wenn verfügbar; sonst Konvertierung", "qualities": ["best"], "default_quality": "best"},
    {"id": "opus", "kind": "audio", "label": "Opus", "description": "Effizienter Codec · Originalspur, wenn verfügbar", "qualities": ["best"], "default_quality": "best"},
    {"id": "wav", "kind": "audio", "label": "WAV", "description": "Unkomprimierte Ausgabe · ideal zur Weiterverarbeitung", "qualities": ["best"], "default_quality": "best"},
    {"id": "flac", "kind": "audio", "label": "FLAC", "description": "Verlustfrei kodierte Ausgabe · größer als die Quelle", "qualities": ["best"], "default_quality": "best"},
]
FORMAT_MAP = {item["id"]: item for item in FORMATS}


def validate_options(data):
    container = data.get("container", "mp4")
    if not isinstance(container, str) or container not in FORMAT_MAP:
        raise ValueError("Bitte wähle ein unterstütztes Datei- oder Audioformat.")
    kind = FORMAT_MAP[container]["kind"]
    if data.get("mode", kind) != kind:
        raise ValueError("Das Dateiformat passt nicht zum gewählten Download-Typ.")
    quality = str(data.get("quality", "best"))
    if kind == "video" and quality != "best" and (not quality.isdigit() or not 1 <= int(quality) <= 10000):
        raise ValueError("Bitte wähle eine gültige Videoauflösung.")
    audio_quality = str(data.get("audio_quality", FORMAT_MAP[container].get("default_quality", "best")))
    if kind == "audio" and audio_quality not in FORMAT_MAP[container]["qualities"]:
        raise ValueError("Bitte wähle eine unterstützte Audioqualität.")
    return {"mode": kind, "container": container, "quality": quality if kind == "video" else "best",
            "audio_quality": audio_quality if kind == "audio" else "best"}


def download_options(payload, directory):
    selected = validate_options(payload)
    container = selected["container"]
    opts = {"outtmpl": str(Path(directory) / "%(title).140B [%(id)s].%(ext)s"), "overwrites": False}
    if selected["mode"] == "audio":
        selector = {"m4a": "ba[ext=m4a]/ba/b", "opus": "ba[acodec^=opus]/ba/b"}.get(container, "ba/b")
        processor = {"key": "FFmpegExtractAudio", "preferredcodec": container}
        if selected["audio_quality"] != "best":
            processor["preferredquality"] = selected["audio_quality"]
        elif container == "m4a":
            processor["preferredquality"] = "0"
        opts.update(format=selector, postprocessors=[processor])
    else:
        cap = "" if selected["quality"] == "best" else f"[height<={int(selected['quality'])}]"
        ext = "[ext=webm]" if container == "webm" else ""
        opts.update(format=f"bv*{ext}{cap}+ba{ext}/b{ext}{cap}", merge_output_format=container,
                    postprocessors=[{"key": "FFmpegVideoRemuxer", "preferedformat": container}])
    return opts
