#!/usr/bin/env python3
"""
SceneDetect for Final Cut Pro
─────────────────────────────
App desktop (CustomTkinter) que detecta cenas em vídeos
e gera um .fcpxml pronto para importar no Final Cut Pro X.

Dependências:
    pip install "scenedetect[opencv]" customtkinter
"""

import hashlib
import os
import sys
import threading
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox
from xml.etree import ElementTree as ET

try:
    import customtkinter as ctk
except ImportError:
    print("❌  customtkinter não encontrado.")
    print("    Instale com:  pip install customtkinter")
    sys.exit(1)

try:
    from scenedetect.detectors import ContentDetector, ThresholdDetector

    from scenedetect import SceneManager, open_video
except ImportError:
    print("❌  PySceneDetect não encontrado.")
    print('    Instale com:  pip install "scenedetect[opencv]"')
    sys.exit(1)


# ═══════════════════════════════════════════════════════════
#  CORE
# ═══════════════════════════════════════════════════════════


def parse_frame_duration(fd_str):
    s = fd_str.rstrip("s")
    if "/" in s:
        n, d = s.split("/")
        return int(n), int(d)
    return 1, int(float(s))


def make_time_formatter(frame_num, frame_den):
    frame_sec = frame_num / frame_den

    def fmt(seconds):
        frames = round(seconds / frame_sec)
        n = frames * frame_num
        if n == 0:
            return "0s"
        return f"{n}/{frame_den}s"

    return fmt


def detect_scenes(video_path, threshold, min_scene_len, method, progress_cb=None):
    video = open_video(video_path)
    manager = SceneManager()
    if method == "threshold":
        manager.add_detector(ThresholdDetector(threshold=threshold))
    else:
        manager.add_detector(
            ContentDetector(
                threshold=threshold, min_scene_len=int(min_scene_len * video.frame_rate)
            )
        )
    manager.detect_scenes(video, show_progress=False)
    scene_list = manager.get_scene_list()
    scenes = []
    total = len(scene_list)
    for i, (start, end) in enumerate(scene_list):
        scenes.append((start.get_seconds(), end.get_seconds()))
        if progress_cb:
            progress_cb(i + 1, total)
    return scenes


def build_fcpxml(
    template_path, video_path, scenes, output_path, project_name=None, event_name=None
):
    tree = ET.parse(template_path)
    root = tree.getroot()
    resources = root.find("resources")
    asset = resources.find("asset")
    library = root.find("library")
    event = library.find("event")
    project = event.find("project")
    sequence = project.find("sequence")
    spine = sequence.find("spine")

    seq_fmt_id = sequence.get("format")
    seq_fmt = resources.find(f"format[@id='{seq_fmt_id}']")
    tl_num, tl_den = parse_frame_duration(seq_fmt.get("frameDuration"))

    asset_fmt_id = asset.get("format")
    asset_fmt = resources.find(f"format[@id='{asset_fmt_id}']")
    as_num, as_den = parse_frame_duration(asset_fmt.get("frameDuration"))

    tl_fmt = make_time_formatter(tl_num, tl_den)
    asset_fmt_fn = make_time_formatter(as_num, as_den)
    asset_id = asset.get("id")
    video_stem = Path(video_path).stem

    first_clip = spine.find("asset-clip")
    conform_attribs = {}
    if first_clip is not None:
        cr = first_clip.find("conform-rate")
        if cr is not None:
            conform_attribs = dict(cr.attrib)

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

    if project_name:
        project.set("name", project_name)
    if event_name:
        event.set("name", event_name)
    project.set("uid", str(uuid.uuid4()).upper())
    event.set("uid", str(uuid.uuid4()).upper())

    for clip in list(spine):
        spine.remove(clip)

    tl_frame_sec = tl_num / tl_den
    total_frames = 0

    for i, (start_sec, end_sec) in enumerate(scenes):
        dur_frames = round((end_sec - start_sec) / tl_frame_sec)
        if dur_frames <= 0:
            dur_frames = 1
        clip = ET.SubElement(spine, "asset-clip")
        clip.set("ref", asset_id)
        clip.set("offset", tl_fmt(total_frames * tl_frame_sec))
        clip.set("name", f"{video_stem} — Cena {i + 1:03d}")
        clip.set("start", asset_fmt_fn(start_sec))
        clip.set("duration", tl_fmt(dur_frames * tl_frame_sec))
        clip.set("format", asset_fmt_id)
        clip.set("tcFormat", "NDF")
        clip.set("audioRole", "dialogue")
        if conform_attribs:
            cr = ET.SubElement(clip, "conform-rate")
            for k, v in conform_attribs.items():
                cr.set(k, v)
        total_frames += dur_frames

    sequence.set("duration", tl_fmt(total_frames * tl_frame_sec))

    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass

    xml_path = Path(output_path)
    if xml_path.suffix != ".fcpxml":
        xml_path = xml_path.with_suffix(".fcpxml")

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write("<!DOCTYPE fcpxml>\n\n")
        f.write(ET.tostring(root, encoding="unicode"))

    return xml_path, len(scenes), total_frames * tl_frame_sec


# ═══════════════════════════════════════════════════════════
#  UI
# ═══════════════════════════════════════════════════════════

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

ACCENT = "#0A84FF"
GRAY = "#636366"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SceneDetect for Final Cut Pro")
        self.geometry("580x560")
        self.resizable(False, False)

        self._video_path = tk.StringVar()
        self._template_path = tk.StringVar()
        self._threshold = tk.DoubleVar(value=27.0)
        self._min_scene = tk.DoubleVar(value=1.0)
        self._method = tk.StringVar(value="content")
        self._running = False

        self._build_ui()

    def _build_ui(self):
        P = 24  # padding lateral padrão

        # ── Header ────────────────────────────────────────
        ctk.CTkLabel(
            self, text="SceneDetect", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", padx=P, pady=(24, 0))
        ctk.CTkLabel(
            self,
            text="Detecção automática de cenas para Final Cut Pro",
            font=ctk.CTkFont(size=12),
            text_color=GRAY,
        ).pack(anchor="w", padx=P, pady=(2, 16))

        # ── Arquivos (numa linha só) ───────────────────────
        self._divider("Arquivos")

        files = ctk.CTkFrame(self, fg_color="transparent")
        files.pack(fill="x", padx=P, pady=(8, 16))
        files.columnconfigure(0, weight=1)
        files.columnconfigure(1, weight=1)

        # Vídeo
        v_col = ctk.CTkFrame(files, fg_color="transparent")
        v_col.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(
            v_col, text="Vídeo", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 4))
        v_row = ctk.CTkFrame(v_col, fg_color="transparent")
        v_row.pack(fill="x")
        v_row.columnconfigure(0, weight=1)
        self._v_entry = ctk.CTkEntry(
            v_row,
            textvariable=self._video_path,
            placeholder_text="nenhum selecionado",
            font=ctk.CTkFont(size=11),
        )
        self._v_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            v_row,
            text="Selecionar",
            width=90,
            fg_color=("gray85", "gray25"),
            text_color=("black", "white"),
            hover_color=("gray75", "gray35"),
            command=self._pick_video,
        ).grid(row=0, column=1)

        # Template
        t_col = ctk.CTkFrame(files, fg_color="transparent")
        t_col.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(
            t_col, text="Template FCPXML", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 4))
        t_row = ctk.CTkFrame(t_col, fg_color="transparent")
        t_row.pack(fill="x")
        t_row.columnconfigure(0, weight=1)
        self._t_entry = ctk.CTkEntry(
            t_row,
            textvariable=self._template_path,
            placeholder_text="nenhum selecionado",
            font=ctk.CTkFont(size=11),
        )
        self._t_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            t_row,
            text="Selecionar",
            width=90,
            fg_color=("gray85", "gray25"),
            text_color=("black", "white"),
            hover_color=("gray75", "gray35"),
            command=self._pick_template,
        ).grid(row=0, column=1)

        # ── Configurações ─────────────────────────────────
        self._divider("Configurações")

        cfg = ctk.CTkFrame(self, fg_color="transparent")
        cfg.pack(fill="x", padx=P, pady=(8, 16))
        cfg.columnconfigure(0, weight=3)
        cfg.columnconfigure(1, weight=1)
        cfg.columnconfigure(2, weight=2)

        # Threshold (coluna 0)
        t_cfg = ctk.CTkFrame(cfg, fg_color="transparent")
        t_cfg.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        lbl_row = ctk.CTkFrame(t_cfg, fg_color="transparent")
        lbl_row.pack(fill="x")
        ctk.CTkLabel(
            lbl_row, text="Sensibilidade", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left")
        self._thresh_lbl = ctk.CTkLabel(
            lbl_row, text="27.0", font=ctk.CTkFont(size=12), text_color=ACCENT
        )
        self._thresh_lbl.pack(side="right")

        ctk.CTkLabel(
            t_cfg,
            text="↓ mais cenas   ↑ menos cenas",
            font=ctk.CTkFont(size=10),
            text_color=GRAY,
        ).pack(anchor="w", pady=(1, 4))
        ctk.CTkSlider(
            t_cfg,
            from_=5,
            to=60,
            variable=self._threshold,
            command=lambda v: self._thresh_lbl.configure(text=f"{float(v):.1f}"),
            button_color=ACCENT,
            progress_color=ACCENT,
        ).pack(fill="x")

        # Duração mínima (coluna 1)
        d_cfg = ctk.CTkFrame(cfg, fg_color="transparent")
        d_cfg.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ctk.CTkLabel(
            d_cfg, text="Mín. (s)", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            d_cfg, text="duração mínima", font=ctk.CTkFont(size=10), text_color=GRAY
        ).pack(anchor="w", pady=(1, 4))
        spin = ctk.CTkFrame(d_cfg, fg_color="transparent")
        spin.pack(anchor="w")
        ctk.CTkButton(
            spin,
            text="−",
            width=28,
            fg_color=("gray85", "gray25"),
            text_color=("black", "white"),
            hover_color=("gray75", "gray35"),
            command=lambda: self._adj_min(-0.5),
        ).pack(side="left")
        self._min_lbl = ctk.CTkLabel(
            spin, text="1.0s", font=ctk.CTkFont(size=12), width=40
        )
        self._min_lbl.pack(side="left", padx=4)
        ctk.CTkButton(
            spin,
            text="+",
            width=28,
            fg_color=("gray85", "gray25"),
            text_color=("black", "white"),
            hover_color=("gray75", "gray35"),
            command=lambda: self._adj_min(0.5),
        ).pack(side="left")

        # Método (coluna 2)
        m_cfg = ctk.CTkFrame(cfg, fg_color="transparent")
        m_cfg.grid(row=0, column=2, sticky="ew")
        ctk.CTkLabel(
            m_cfg, text="Método", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            m_cfg, text="visual / brilho", font=ctk.CTkFont(size=10), text_color=GRAY
        ).pack(anchor="w", pady=(1, 4))
        ctk.CTkSegmentedButton(
            m_cfg, values=["content", "threshold"], variable=self._method
        ).pack(fill="x")

        # ── Botão ──────────────────────────────────────────
        self._run_btn = ctk.CTkButton(
            self,
            text="🎬  Detectar Cenas e Gerar FCPXML",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            fg_color=ACCENT,
            hover_color="#0060CC",
            command=self._run,
        )
        self._run_btn.pack(fill="x", padx=P, pady=(0, 16))

        # ── Progress ───────────────────────────────────────
        self._progress = ctk.CTkProgressBar(
            self, mode="determinate", progress_color=ACCENT
        )
        self._progress.pack(fill="x", padx=P, pady=(0, 2))
        self._progress.set(0)
        self._progress_lbl = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11), text_color=GRAY
        )
        self._progress_lbl.pack(pady=(0, 8))

        # ── Log ────────────────────────────────────────────
        self._divider("Log")
        self._log = ctk.CTkTextbox(
            self, height=140, font=ctk.CTkFont(family="Menlo", size=11)
        )
        self._log.pack(fill="x", padx=P, pady=(8, 20))
        self._log.configure(state="disabled")

    def _divider(self, title):
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="x", padx=24, pady=(0, 0))
        ctk.CTkLabel(
            f,
            text=title.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=GRAY,
        ).pack(anchor="w")
        ctk.CTkFrame(f, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", pady=(2, 0)
        )

    def _pick_video(self):
        path = filedialog.askopenfilename(
            title="Selecione o vídeo",
            filetypes=[("Vídeos", "*.mov *.mp4 *.m4v *.avi *.mkv"), ("Todos", "*.*")],
        )
        if path:
            self._video_path.set(path)

    def _pick_template(self):
        path = filedialog.askopenfilename(
            title="Selecione o FCPXML",
            filetypes=[("FCPXML", "*.fcpxml"), ("Todos", "*.*")],
        )
        if path:
            self._template_path.set(path)

    def _adj_min(self, delta):
        val = max(0.5, round(self._min_scene.get() + delta, 1))
        self._min_scene.set(val)
        self._min_lbl.configure(text=f"{val:.1f}s")

    def _log_write(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _log_clear(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _set_progress(self, value, label=""):
        self._progress.set(value)
        self._progress_lbl.configure(text=label)

    def _run(self):
        if self._running:
            return
        video = self._video_path.get().strip()
        template = self._template_path.get().strip()
        if not video or not os.path.exists(video):
            messagebox.showerror("Erro", "Selecione um arquivo de vídeo válido.")
            return
        if not template or not os.path.exists(template):
            messagebox.showerror(
                "Erro", "Selecione o template FCPXML do Final Cut Pro."
            )
            return
        self._running = True
        self._run_btn.configure(state="disabled", text="⏳  Processando…")
        self._log_clear()
        self._set_progress(0, "")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        video = self._video_path.get().strip()
        template = self._template_path.get().strip()
        threshold = self._threshold.get()
        min_scene = self._min_scene.get()
        method = self._method.get()
        output = str(Path(video).parent / (Path(video).stem + "_scenes.fcpxml"))

        try:
            self._ui(self._log_write, f"🎬  {Path(video).name}")
            self._ui(self._log_write, f"📄  {Path(template).name}")
            self._ui(
                self._log_write,
                f"⚙️   threshold={threshold:.1f}  min={min_scene:.1f}s  método={method}\n",
            )
            self._ui(self._set_progress, 0.05, "Iniciando análise…")

            def on_progress(current, total):
                self._ui(
                    self._set_progress,
                    0.05 + (current / total) * 0.80,
                    f"Analisando… {current}/{total} cenas",
                )

            scenes = detect_scenes(video, threshold, min_scene, method, on_progress)

            if not scenes:
                self._ui(
                    self._log_write,
                    "⚠️  Nenhuma cena detectada. Tente reduzir a sensibilidade.",
                )
                self._ui(self._set_progress, 0, "")
                return

            self._ui(self._log_write, f"✅  {len(scenes)} cenas detectadas:\n")
            for i, (s, e) in enumerate(scenes):
                self._ui(
                    self._log_write,
                    f"   Cena {i + 1:>3}: {s:>8.3f}s → {e:>8.3f}s  ({e - s:.3f}s)",
                )

            self._ui(self._set_progress, 0.88, "Gerando FCPXML…")

            xml_path, n_scenes, total_sec = build_fcpxml(
                template_path=template,
                video_path=video,
                scenes=scenes,
                output_path=output,
            )

            self._ui(
                self._set_progress, 1.0, f"{n_scenes} cenas • {total_sec:.1f}s total"
            )
            self._ui(self._log_write, f"\n✅  Gerado: {xml_path.name}")
            self._ui(self._log_write, "💡  File → Import → XML… no Final Cut Pro")
            os.system(f'open -R "{xml_path}"')

        except Exception as e:
            self._ui(self._log_write, f"\n❌  Erro: {e}")
            self._ui(self._set_progress, 0, "Erro durante o processamento")
        finally:
            self._running = False
            self._ui(
                self._run_btn.configure,
                state="normal",
                text="🎬  Detectar Cenas e Gerar FCPXML",
            )

    def _ui(self, fn, *args, **kwargs):
        self.after(0, lambda: fn(*args, **kwargs))


if __name__ == "__main__":
    app = App()
    app.mainloop()
