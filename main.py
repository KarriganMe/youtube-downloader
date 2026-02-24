# ---------------------------------------------------------
#  main.py  –  YouTube downloader  (auto FFmpeg + progress pop-up)
#  GUI unchanged, first-run download visible to user
# ---------------------------------------------------------
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading, os, logging, sys, zipfile, requests, shutil
from datetime import datetime
import yt_dlp
from pathlib import Path

# ---------------------------------------------------------
# Logging: redirect everything to the GUI console widget
# ---------------------------------------------------------
class ConsoleHandler(logging.Handler):
    def __init__(self, console_widget):
        super().__init__()
        self.console_widget = console_widget

    def emit(self, record):
        msg = self.format(record)
        self.console_widget.after(0, self._append, msg)

    def _append(self, msg):
        self.console_widget.configure(state="normal")
        self.console_widget.insert("end", msg + "\n")
        self.console_widget.see("end")
        self.console_widget.configure(state="disabled")


# ---------------------------------------------------------
# FFmpeg auto-downloader  –  with pop-up progress bar
# ---------------------------------------------------------
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_EXE = Path(sys.executable).parent / "ffmpeg.exe"   # beside the exe


class FFmpegDownloaderDialog(tk.Toplevel):
    """Modal progress window while ffmpeg is downloaded (one-time)."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Downloading FFmpeg …")
        self.geometry("380x140")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="One-time download of FFmpeg (~80 MB)", font=("Segoe UI", 10)).pack(pady=12)
        self.bar = ttk.Progressbar(self, length=340, mode='indeterminate')
        self.bar.pack(pady=10)
        self.bar.start(12)

        ttk.Label(self, text="Please wait – this will only happen once.", font=("Segoe UI", 9)).pack()

        self.success = False
        # download in background thread so GUI stays alive
        threading.Thread(target=self._download, daemon=True).start()
        parent.wait_window(self)          # block caller until closed

    def _download(self):
        """Perform the download + extraction."""
        try:
            zip_tmp = FFMPEG_EXE.with_suffix(".zip.tmp")
            with requests.get(FFMPEG_URL, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                with open(zip_tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            # extract only ffmpeg.exe
            with zipfile.ZipFile(zip_tmp) as z:
                for info in z.infolist():
                    if info.filename.endswith("bin/ffmpeg.exe"):
                        info.filename = "ffmpeg.exe"
                        z.extract(info, FFMPEG_EXE.parent)
                        break
            zip_tmp.unlink(missing_ok=True)
            self.success = True
            logging.getLogger("ytdl").info("FFmpeg ready.")
        except Exception as e:
            logging.getLogger("ytdl").error(f"FFmpeg download failed: {e}")
        finally:
            self.bar.stop()
            self.destroy()


def download_ffmpeg(parent):
    """Download ffmpeg.exe beside the exe (one-time) with GUI progress."""
    if FFMPEG_EXE.exists():
        return True
    FFmpegDownloaderDialog(parent)
    return FFMPEG_EXE.exists()


# ---------------------------------------------------------
# Main application
# ---------------------------------------------------------
class YouTubeDownloader:
    def __init__(self):
        self.download_path = os.path.expanduser("~/Downloads")
        self.setup_gui()
        self.setup_logging()
        # one-time FFmpeg download with pop-up
        self.root.after(50, self._first_run_ffmpeg_check)
        self.add_console_message("INFO", "YouTube Downloader ready!")

    def _first_run_ffmpeg_check(self):
        self.ffmpeg_ready = download_ffmpeg(self.root)
    # -----------------------------------------------------
    # GUI – identical + permanent warning label
    # -----------------------------------------------------
    def setup_gui(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("YouTube Video Downloader")
        self.root.geometry("800x700")
        self.root.minsize(600, 500)

        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # ⚠  permanent warning
        warn = ctk.CTkLabel(main_frame,
                            text="⚠  1080p / 1440p / 2K / 4K  require  FFmpeg.exe  (auto-downloaded on 1st run)",
                            font=ctk.CTkFont(size=12), text_color="orange")
        warn.pack(pady=(5, 0))

        title = ctk.CTkLabel(main_frame, text="YouTube Video Downloader",
                             font=ctk.CTkFont(size=24, weight="bold"))
        title.pack(pady=(10, 30))

        # URL
        url_frame = ctk.CTkFrame(main_frame)
        url_frame.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkLabel(url_frame, text="YouTube URL:").pack(anchor="w", padx=20, pady=(20, 5))
        self.url_entry = ctk.CTkEntry(url_frame, placeholder_text="https://www.youtube.com/watch?v=...")
        self.url_entry.pack(fill="x", padx=20, pady=(0, 20))

        # Options
        opt_frame = ctk.CTkFrame(main_frame)
        opt_frame.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkLabel(opt_frame, text="Download Options:").pack(anchor="w", padx=20, pady=(20, 10))

        self.audio_var = ctk.StringVar(value="video")
        radio_frame = ctk.CTkFrame(opt_frame)
        radio_frame.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkRadioButton(radio_frame, text="Video with Audio", variable=self.audio_var, value="video").pack(side="left", padx=20)
        ctk.CTkRadioButton(radio_frame, text="Audio Only", variable=self.audio_var, value="audio").pack(side="left", padx=20)
        ctk.CTkRadioButton(radio_frame, text="Video Only", variable=self.audio_var, value="video_only").pack(side="left", padx=20)

        qual_frame = ctk.CTkFrame(opt_frame)
        qual_frame.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkLabel(qual_frame, text="Quality:").pack(side="left", padx=20)
        self.quality_var = ctk.StringVar(value="720p")
        self.quality_menu = ctk.CTkOptionMenu(qual_frame, variable=self.quality_var,
                                              values=["144p", "240p", "360p", "480p", "720p",
                                                      "1080p", "1440p", "2K", "4K", "highest", "lowest"])
        self.quality_menu.pack(side="left", padx=10)

        # Path
        path_frame = ctk.CTkFrame(main_frame)
        path_frame.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkLabel(path_frame, text="Download Location:").pack(anchor="w", padx=20, pady=(20, 5))
        path_input = ctk.CTkFrame(path_frame)
        path_input.pack(fill="x", padx=20, pady=(0, 20))
        self.path_entry = ctk.CTkEntry(path_input)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.path_entry.insert(0, self.download_path)
        ctk.CTkButton(path_input, text="Browse", width=80, command=self.browse_folder).pack(side="right")

        # Download button + progress
        down_frame = ctk.CTkFrame(main_frame)
        down_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.download_btn = ctk.CTkButton(down_frame, text="Download", height=40,
                                          font=ctk.CTkFont(size=16, weight="bold"),
                                          command=self.start_download)
        self.download_btn.pack(pady=20)
        self.progress_bar = ctk.CTkProgressBar(down_frame)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 20))
        self.progress_bar.set(0)

        # Console
        con_frame = ctk.CTkFrame(main_frame)
        con_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        ctk.CTkLabel(con_frame, text="Console Output:").pack(anchor="w", padx=20, pady=(20, 5))
        con_container = ctk.CTkFrame(con_frame)
        con_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.console_text = ctk.CTkTextbox(con_container, height=150,
                                           font=ctk.CTkFont(family="Consolas", size=10),
                                           state="disabled")
        self.console_text.pack(fill="both", expand=True, pady=10)

    # -----------------------------------------------------
    # Logging setup
    # -----------------------------------------------------
    def setup_logging(self):
        self.logger = logging.getLogger("ytdl")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        self.logger.propagate = False

        console_handler = ConsoleHandler(self.console_text)
        console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))
        self.logger.addHandler(console_handler)

        file_handler = logging.FileHandler("youtube_downloader.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S"))
        self.logger.addHandler(file_handler)

    def add_console_message(self, level, msg):
        self.logger.log(getattr(logging, level.upper()), msg)

    # -----------------------------------------------------
    # Browse folder
    # -----------------------------------------------------
    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.download_path)
        if folder:
            self.download_path = folder
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)
            self.logger.info(f"Download path changed to: {folder}")

    # -----------------------------------------------------
    #  quick FFmpeg test
    # -----------------------------------------------------
    def _ffmpeg_exists(self):
        return FFMPEG_EXE.is_file()

    # -----------------------------------------------------
    # Download starter
    # -----------------------------------------------------
    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self.logger.error("Please enter a YouTube URL")
            return
        self.download_btn.configure(state="disabled", text="Downloading…")
        self.progress_bar.set(0)
        threading.Thread(target=self.download_video, args=(url,), daemon=True).start()

    # -----------------------------------------------------
    # yt-dlp progress hook
    # -----------------------------------------------------
    def _progress_hook(self, d):
        if d["status"] == "downloading":
            pct = d.get("_percent_str", "0%").strip().replace("%", "")
            try:
                pct = float(pct) / 100.0
            except:
                pct = 0
            self.root.after(0, lambda: self.progress_bar.set(pct))
        elif d["status"] == "finished":
            self.root.after(0, lambda: self.progress_bar.set(1.0))

    # -----------------------------------------------------
    # Build yt-dlp options  –  MP4 + loss-less merge
    # -----------------------------------------------------
    def _build_opts(self, download_path, audio_opt, quality):
        outtmpl = str(Path(download_path) / "%(title)s.%(ext)s")
        opts = {
            "outtmpl": outtmpl,
            "noplaylist": True,
            "progress_hooks": [self._progress_hook],
            "logger": self.logger,
        }
        if self._ffmpeg_exists():
            opts["ffmpeg_location"] = str(FFMPEG_EXE)

        # friendly names → pixel
        height_map = {"2K": "1440", "1440p": "1440", "4K": "2160"}
        height = height_map.get(quality, quality.replace("p", ""))

        if audio_opt == "audio":
            opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            })
            return opts

        # ---  video cases  ---
        if audio_opt == "video_only":
            if quality in ("highest", "lowest"):
                opts["format"] = "bestvideo" if quality == "highest" else "worstvideo"
            else:
                opts["format"] = f"bestvideo[height<=?{height}]/bestvideo"

        else:  # video + audio
            if quality in ("highest", "lowest"):
                opts["format"] = "best" if quality == "highest" else "worst"
            elif self._ffmpeg_exists():        # can merge → MP4 + copy codecs
                opts["format"] = f"bv[height<=?{height}]+ba/b[height<=?{height}]"
                opts["merge_output_format"] = "mp4"
                opts["postprocessor_args"] = {"ffmpeg": ["-c:v", "copy", "-c:a", "copy"]}
            else:                              # no merge → best progressive
                self.logger.info("FFmpeg not found – using highest progressive stream (≤ 720p).")
                opts["format"] = "best[height<=?720][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]"
        return opts

    # -----------------------------------------------------
    # Actual download
    # -----------------------------------------------------
    def download_video(self, url):
        try:
            download_path = self.path_entry.get().strip() or self.download_path
            os.makedirs(download_path, exist_ok=True)
            audio_opt = self.audio_var.get()
            quality = self.quality_var.get()

            self.logger.info(f"Starting download for URL: {url}")
            opts = self._build_opts(download_path, audio_opt, quality)

            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            self.logger.info("Download completed successfully!")
        except Exception as e:
            self.logger.error(f"Download failed: {e}")
        finally:
            self.root.after(0, lambda: self.download_btn.configure(state="normal", text="Download"))
            self.root.after(0, lambda: self.progress_bar.set(0))

    # -----------------------------------------------------
    # Run
    # -----------------------------------------------------
    def run(self):
        self.logger.info("Starting YouTube Downloader GUI")
        self.root.mainloop()


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------
if __name__ == "__main__":
    YouTubeDownloader().run()