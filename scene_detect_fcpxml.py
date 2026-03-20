#!/usr/bin/env python3
"""
scene_detect_fcpxml.py
──────────────────────
Detecta cenas em um vídeo e gera um .fcpxmld pronto para importar no Final Cut Pro X.
Baseado na estrutura real exportada pelo FCPX (FCPXML 1.14).

Dependências:
    pip install "scenedetect[opencv]"
    brew install ffmpeg

Uso:
    python scene_detect_fcpxml.py --video meu_video.mov --template Info.fcpxmld/Info.fcpxml

Opções:
    --video         Caminho para o arquivo de vídeo (obrigatório)
    --template      Caminho para o .fcpxml dentro do bundle exportado do FCPX (obrigatório)
    --output        Nome do bundle de saída (padrão: <video>_scenes.fcpxmld)
    --threshold     Sensibilidade da detecção (padrão: 27.0 — menor = mais cortes)
    --min-scene     Duração mínima de cena em segundos (padrão: 1.0)
    --method        Método de detecção: content | threshold (padrão: content)
    --project-name  Nome do projeto no FCPX
    --event-name    Nome do evento no FCPX

Exemplos:
    python scene_detect_fcpxml.py --video file-cut.mov --template Info.fcpxmld/Info.fcpxml
    python scene_detect_fcpxml.py --video file-cut.mov --template Info.fcpxmld/Info.fcpxml --threshold 15
    python scene_detect_fcpxml.py --video file-cut.mov --template Info.fcpxmld/Info.fcpxml --threshold 40 --min-scene 2.0
"""

import argparse
import hashlib
import os
import sys
import uuid
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector, ThresholdDetector
except ImportError:
    print("❌  PySceneDetect não encontrado.")
    print("    Instale com:  pip install \"scenedetect[opencv]\"")
    sys.exit(1)


# ─── Parse de frameDuration ───────────────────────────────────────────────────

def parse_frame_duration(fd_str: str):
    """'100/3000s' → (100, 3000)  |  '1001/30000s' → (1001, 30000)"""
    s = fd_str.rstrip("s")
    if "/" in s:
        n, d = s.split("/")
        return int(n), int(d)
    return 1, int(float(s))


# ─── Conversão de tempo ───────────────────────────────────────────────────────

def make_time_formatter(frame_num: int, frame_den: int):
    """
    Retorna uma função que converte segundos (float) para string FCPXML
    snapped ao frame mais próximo, usando denominador FIXO (sem simplificar).

    Para offset= e duration= usar frameDuration da TIMELINE (ex: 100/3000s).
    Para start= usar frameDuration do ASSET (ex: 1001/30000s).
    """
    frame_sec = frame_num / frame_den

    def fmt(seconds: float) -> str:
        frames = round(seconds / frame_sec)
        n = frames * frame_num
        d = frame_den
        if n == 0:
            return "0s"
        return f"{n}/{d}s"

    return fmt


# ─── Detecção de cenas ────────────────────────────────────────────────────────

def detect_scenes(video_path: str, threshold: float, min_scene_len: float, method: str):
    print(f"\n🎬  Analisando vídeo: {video_path}")
    print(f"    Método: {method}  |  Threshold: {threshold}  |  Mínimo: {min_scene_len}s\n")

    video = open_video(video_path)
    manager = SceneManager()

    if method == "threshold":
        manager.add_detector(ThresholdDetector(threshold=threshold))
    else:
        manager.add_detector(ContentDetector(
            threshold=threshold,
            min_scene_len=int(min_scene_len * video.frame_rate)
        ))

    manager.detect_scenes(video, show_progress=True)
    scene_list = manager.get_scene_list()

    if not scene_list:
        print("\n⚠️   Nenhuma cena detectada. Tente reduzir o --threshold.")
        sys.exit(1)

    scenes = []
    for i, (start, end) in enumerate(scene_list):
        s = start.get_seconds()
        e = end.get_seconds()
        scenes.append((s, e))
        print(f"    Cena {i+1:>3}: {s:>8.3f}s → {e:>8.3f}s  ({e-s:.3f}s)")

    print(f"\n✅  {len(scenes)} cenas detectadas.")
    return scenes


# ─── Geração do FCPXML ────────────────────────────────────────────────────────

def build_fcpxml(template_path, video_path, scenes, output_path, project_name, event_name):
    tree = ET.parse(template_path)
    root = tree.getroot()

    resources  = root.find("resources")
    asset      = resources.find("asset")
    library    = root.find("library")
    event      = library.find("event")
    project    = event.find("project")
    sequence   = project.find("sequence")
    spine      = sequence.find("spine")

    # ── Lê frameDurations ─────────────────────────────────────────────────────
    # Timeline (r1): usada para offset= e duration= dos clips na spine
    seq_fmt_id  = sequence.get("format")
    seq_fmt     = resources.find(f"format[@id='{seq_fmt_id}']")
    tl_num, tl_den = parse_frame_duration(seq_fmt.get("frameDuration"))

    # Asset (r3): usada para start= dos clips (ponto de entrada no arquivo)
    asset_fmt_id = asset.get("format")
    asset_fmt    = resources.find(f"format[@id='{asset_fmt_id}']")
    as_num, as_den = parse_frame_duration(asset_fmt.get("frameDuration"))

    # Formatadores — denominador FIXO, sem simplificação
    tl_fmt    = make_time_formatter(tl_num, tl_den)    # offset, duration
    asset_fmt_fn = make_time_formatter(as_num, as_den) # start

    asset_id   = asset.get("id")
    video_stem = Path(video_path).stem

    # Pega conform-rate do primeiro clip como modelo
    first_clip = spine.find("asset-clip")
    conform_attribs = {}
    if first_clip is not None:
        cr = first_clip.find("conform-rate")
        if cr is not None:
            conform_attribs = dict(cr.attrib)

    # ── Atualiza src do asset ─────────────────────────────────────────────────
    video_abs = str(Path(video_path).resolve())
    video_uri = "file://" + video_abs.replace(" ", "%20")
    media_rep = asset.find("media-rep")
    media_rep.set("src", video_uri)
    new_uid = hashlib.md5(video_abs.encode()).hexdigest().upper()
    media_rep.set("sig", new_uid)
    asset.set("uid", new_uid)
    asset.set("name", video_stem)
    bookmark = media_rep.find("bookmark")
    if bookmark is not None:
        media_rep.remove(bookmark)

    # ── Atualiza nomes e UIDs ─────────────────────────────────────────────────
    if project_name:
        project.set("name", project_name)
    if event_name:
        event.set("name", event_name)
    project.set("uid", str(uuid.uuid4()).upper())
    event.set("uid", str(uuid.uuid4()).upper())

    # ── Reconstrói spine ──────────────────────────────────────────────────────
    for clip in list(spine):
        spine.remove(clip)

    tl_frame_sec  = tl_num / tl_den   # duração de 1 frame na timeline
    total_frames  = 0                  # offset acumulado em frames da timeline

    for i, (start_sec, end_sec) in enumerate(scenes):
        duration_sec = end_sec - start_sec

        # Snap de duração ao frame da timeline
        dur_frames = round(duration_sec / tl_frame_sec)
        if dur_frames <= 0:
            dur_frames = 1

        offset_str   = tl_fmt(total_frames * tl_frame_sec)
        duration_str = tl_fmt(dur_frames * tl_frame_sec)
        start_str    = asset_fmt_fn(start_sec)

        clip = ET.SubElement(spine, "asset-clip")
        clip.set("ref",      asset_id)
        clip.set("offset",   offset_str)
        clip.set("name",     f"{video_stem} — Cena {i+1:03d}")
        clip.set("start",    start_str)
        clip.set("duration", duration_str)
        clip.set("format",   asset_fmt_id)
        clip.set("tcFormat", "NDF")
        clip.set("audioRole","dialogue")

        if conform_attribs:
            cr = ET.SubElement(clip, "conform-rate")
            for k, v in conform_attribs.items():
                cr.set(k, v)

        total_frames += dur_frames

    # Duração total da sequence
    sequence.set("duration", tl_fmt(total_frames * tl_frame_sec))

    # ── Salva como bundle .fcpxmld ────────────────────────────────────────────
    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass

    xml_path = Path(output_path)
    if xml_path.suffix != ".fcpxml":
        xml_path = xml_path.with_suffix(".fcpxml")

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE fcpxml>\n\n')
        f.write(ET.tostring(root, encoding="unicode"))

    total_sec = total_frames * tl_frame_sec
    print(f"\n📄  FCPXML gerado:   {xml_path}")
    print(f"    Total de cenas:  {len(scenes)}")
    print(f"    Duração total:   {total_sec:.2f}s")
    print(f"\n💡  No Final Cut Pro: File → Import → XML…  e selecione o arquivo gerado.\n")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Detecta cenas e gera FCPXML para o Final Cut Pro X.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--video",        required=True)
    parser.add_argument("--template",     required=True)
    parser.add_argument("--output",       default=None)
    parser.add_argument("--threshold",    type=float, default=27.0)
    parser.add_argument("--min-scene",    type=float, default=1.0)
    parser.add_argument("--method",       choices=["content", "threshold"], default="content")
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--event-name",   default=None)
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"❌  Vídeo não encontrado: {args.video}")
        sys.exit(1)
    if not os.path.exists(args.template):
        print(f"❌  Template FCPXML não encontrado: {args.template}")
        sys.exit(1)

    if args.output is None:
        stem = Path(args.video).stem
        args.output = str(Path(args.video).parent / f"{stem}_scenes.fcpxml")

    scenes = detect_scenes(args.video, args.threshold, args.min_scene, args.method)

    build_fcpxml(
        template_path=args.template,
        video_path=args.video,
        scenes=scenes,
        output_path=args.output,
        project_name=args.project_name,
        event_name=args.event_name,
    )


if __name__ == "__main__":
    main()
