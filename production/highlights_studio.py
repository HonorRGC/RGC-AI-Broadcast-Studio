"""Small Studio workflow for preparing and playing Streamlabs highlights."""
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk


def import_graphic(value, root):
    value = str(value or "").strip()
    if not value or value.startswith(("/assets/", "/static/")):
        return value
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise ValueError("Choose a PNG, JPG, WebP, or GIF graphic.")
    name = "highlight_" + hashlib.sha256(path.read_bytes()).hexdigest()[:16] + path.suffix.lower()
    destination = Path(root) / "production" / "static" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path != destination.resolve():
        shutil.copy2(path, destination)
    return "/static/" + name


def save_highlights_title(job_path, title, visual_options=None):
    from production.highlights import save_job
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    job.setdefault("options", {})["title"] = str(title or "").strip()[:160]
    if visual_options:
        for key in ("transition", "transition_graphic", "full_screen_graphic", "transition_sponsor", "sponsor", "sponsor_logo", "recap_sponsor", "recap_sponsor_logo"):
            if key in visual_options:
                job["options"][key] = visual_options[key]
    save_job(job_path, job)


def open_highlights_window(parent, values):
    import studio_launcher as studio
    window = tk.Toplevel(parent)
    window.transient(parent)
    window.title("Race Highlights · Streamlabs")
    window.geometry("900x850")
    window.minsize(780, 680)
    window.configure(bg="#101b29")
    def bring_to_front():
        if window.winfo_exists():
            window.lift()
            window.focus_set()
    window.after_idle(bring_to_front)
    frame = ttk.Frame(window, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Race Highlights", font=("Segoe UI", 19, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Prepare the story and voices first. Streamlabs records the playback and overlays.", wraplength=770).pack(anchor="w", pady=(5, 14))
    capture = tk.StringVar(value=values.get("RECORDED_BROADCAST_FILE", ""))
    title = tk.StringVar()
    transition = tk.StringVar(value="Cycle: fade, slide, wipe")
    graphic, sponsor_logo, sponsor = tk.StringVar(), tk.StringVar(), tk.StringVar(value="None")
    transition_sponsor = tk.StringVar()
    recap_sponsor, recap_sponsor_logo = tk.StringVar(), tk.StringVar()
    full_screen_graphic = tk.StringVar()
    progress = tk.StringVar(value="Choose the telemetry capture for the saved iRacing replay.")
    replay_loaded = tk.BooleanVar(value=False)
    scan_incidents = tk.BooleanVar(value=True)
    state = {"process": None, "job": None, "log": None, "play_process": None, "cancelled": False}

    def select_file(variable, capture_file=False):
        path = filedialog.askopenfilename(parent=window,
            initialdir=str(studio.ROOT / "recordings" if capture_file else studio.STATIC_ASSET_DIR),
            filetypes=(("Broadcast capture", "*.jsonl"),) if capture_file else (("Images", "*.png *.jpg *.jpeg *.webp *.gif"),))
        if path:
            variable.set(path)

    def file_row(label, variable, capture_file=False):
        ttk.Label(frame, text=label).pack(anchor="w", pady=(8, 2))
        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Choose…", command=lambda: select_file(variable, capture_file)).pack(side="left", padx=(6, 0))

    ttk.Label(frame, text="Highlights title (shown across the top)").pack(anchor="w", pady=(0, 2))
    ttk.Entry(frame, textvariable=title).pack(fill="x", pady=(0, 6))
    file_row("Race capture (.jsonl)", capture, True)
    ttk.Label(frame, text="Transition style").pack(anchor="w", pady=(10, 2))
    ttk.Combobox(frame, textvariable=transition, values=("Cycle: fade, slide, wipe", "Fade", "Slide", "Wipe"), state="readonly").pack(anchor="w")
    names = {"None": ""}
    for index in range(1, 6):
        name = values.get(f"RACE_SPONSOR_{index}_NAME", "").strip()
        if name:
            names[name] = values.get(f"RACE_SPONSOR_{index}_LOGO", "")
    sponsor_groups = ttk.Frame(frame)
    sponsor_groups.pack(fill="x", pady=10)
    sponsor_groups.columnconfigure((0, 1, 2), weight=1, uniform="sponsors")
    def sponsor_group(column, heading, name_var, logo_var):
        group = ttk.LabelFrame(sponsor_groups, text=heading, padding=8)
        group.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (0, 0))
        ttk.Label(group, text="Sponsor name — type your own or select", wraplength=220).pack(anchor="w")
        combo = ttk.Combobox(group, textvariable=name_var, values=tuple(names), width=18)
        combo.pack(fill="x", pady=(3, 8))
        combo.bind("<<ComboboxSelected>>", lambda event: logo_var.set(names.get(name_var.get(), "")))
        ttk.Label(group, text="Graphic (optional)").pack(anchor="w")
        row = ttk.Frame(group)
        row.pack(fill="x", pady=3)
        ttk.Entry(row, textvariable=logo_var, width=16).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Choose…", command=lambda: select_file(logo_var)).pack(side="left", padx=(5, 0))
    sponsor_group(0, "Center transition sponsor", transition_sponsor, graphic)
    sponsor_group(1, "Upper-right clip sponsor", sponsor, sponsor_logo)
    sponsor_group(2, "Left recap sponsor", recap_sponsor, recap_sponsor_logo)
    file_row("Full-screen transition artwork (optional; 1920 × 1080 recommended)", full_screen_graphic)
    ttk.Checkbutton(frame, text="Scan saved replay incident markers (may include incidents with unknown point values)", variable=scan_incidents).pack(anchor="w", pady=(8, 0))
    ttk.Checkbutton(frame, text="I have loaded the matching saved .rpy in iRacing; I am not racing live.", variable=replay_loaded).pack(anchor="w", pady=12)
    ttk.Label(frame, textvariable=progress, wraplength=770).pack(anchor="w", pady=8)
    preview = tk.Text(frame, height=8, wrap="word", bg="#0c1420", fg="#dce5ef")
    preview.pack(fill="both", expand=True, pady=8)
    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=8)

    def show_job(job):
        capture.set(job.get("source", capture.get()))
        options = job.get("options", {})
        title.set(options.get("title", ""))
        style = options.get("transition", "cycle")
        transition.set("Cycle: fade, slide, wipe" if style == "cycle" else style.title())
        graphic.set(options.get("transition_graphic", ""))
        full_screen_graphic.set(options.get("full_screen_graphic", ""))
        transition_sponsor.set(options.get("transition_sponsor", ""))
        sponsor.set(options.get("sponsor") or "None")
        sponsor_logo.set(options.get("sponsor_logo", ""))
        recap_sponsor.set(options.get("recap_sponsor", ""))
        recap_sponsor_logo.set(options.get("recap_sponsor_logo", ""))
        scan_incidents.set(bool(options.get("scan_incidents")))
        preview.delete("1.0", "end")
        for warning in job.get("warnings", []):
            preview.insert("end", "Note: " + warning + "\n\n")
        from production.highlights import programme_seconds
        duration = programme_seconds(job)
        for index, segment in enumerate(job.get("segments", []), 1):
            preview.insert("end", f"{index}. {segment['title']}\n{segment.get('narration') or segment.get('facts', '')}\n\n")
        if job.get("status") == "ready":
            progress.set(f"Ready · approximately {duration / 60:.1f} minutes (15–20 minute target; shorter races can be shorter). Start the player, then use Producer Assist to begin recording playback.")

    def poll():
        process, path = state["process"], state["job"]
        if not window.winfo_exists():
            return
        if path and path.exists():
            try:
                job = json.loads(path.read_text(encoding="utf-8"))
                progress.set(job.get("progress", job.get("status", "Preparing…")))
            except (OSError, ValueError):
                job = {}
        else:
            job = {}
        if process and process.poll() is None:
            window.after(500, poll)
            return
        if state["cancelled"]:
            job.update(status="cancelled", progress="Preparation cancelled. Prepare Highlights can resume completed narration for this job.")
            if path:
                from production.highlights import save_job
                save_job(path, job)
            state["cancelled"] = False
        if state["log"]:
            state["log"].close()
            state["log"] = None
        state["process"] = None
        prepare_button.configure(state="normal")
        if job.get("status") == "ready":
            show_job(job)
            play_button.configure(state="normal")
        else:
            progress.set(job.get("progress") or "Preparation stopped. See the preparation log in the highlight job folder.")

    def prepare():
        if studio.has_running_preparation():
            messagebox.showinfo("Highlights preparing", "Another highlights preparation is already running. Let it finish or cancel it in its highlights window.", parent=window)
            return
        if studio.has_running_broadcast():
            messagebox.showinfo("Broadcast active", "Stop the normal broadcast before preparing highlights.", parent=window)
            return
        if scan_incidents.get() and not replay_loaded.get():
            messagebox.showinfo("Saved replay required", "Load the matching saved .rpy and tick the replay checkbox before scanning incidents, or turn off the marker scan.", parent=window)
            return
        path = Path(capture.get()).expanduser()
        if not path.is_file() or path.name.endswith(".events.jsonl"):
            messagebox.showerror("Race capture", "Choose the main broadcast telemetry .jsonl file.", parent=window)
            return
        try:
            options = {"scan_incidents": scan_incidents.get(), "transition": "cycle" if transition.get().startswith("Cycle") else transition.get().lower(),
                       "title": title.get().strip()[:160],
                       "transition_sponsor": "" if transition_sponsor.get().strip() == "None" else transition_sponsor.get().strip()[:160],
                       "transition_graphic": import_graphic(graphic.get(), studio.ROOT),
                       "full_screen_graphic": import_graphic(full_screen_graphic.get(), studio.ROOT),
                       "sponsor": "" if sponsor.get().strip() == "None" else sponsor.get().strip()[:160],
                       "sponsor_logo": import_graphic(sponsor_logo.get(), studio.ROOT),
                       "recap_sponsor": "" if recap_sponsor.get().strip() == "None" else recap_sponsor.get().strip()[:160],
                       "recap_sponsor_logo": import_graphic(recap_sponsor_logo.get(), studio.ROOT)}
        except (OSError, ValueError) as error:
            messagebox.showerror("Highlight graphic", str(error), parent=window)
            return
        job = studio.ROOT / "highlights" / (path.stem + "_" + uuid.uuid4().hex[:8]) / "programme.json"
        existing_job = state["job"]
        if existing_job and existing_job.exists():
            try:
                saved = json.loads(existing_job.read_text(encoding="utf-8"))
                if saved.get("source") == str(path.resolve()) and saved.get("options") == options:
                    job = existing_job
            except (OSError, ValueError):
                pass
        state["cancelled"] = False
        job.parent.mkdir(parents=True, exist_ok=True)
        state["job"] = job
        state["log"] = (job.parent / "prepare.log").open("w", encoding="utf-8")
        command = [sys.executable, str(studio.ROOT / "app.py"), "--prepare-highlights", str(path.resolve()),
                   "--highlights-job", str(job), "--highlights-options", json.dumps(options)]
        try:
            state["process"] = subprocess.Popen(command, cwd=studio.ROOT, stdout=state["log"], stderr=subprocess.STDOUT,
                                                 creationflags=studio.broadcast_creation_flags())
        except OSError as error:
            state["log"].close()
            state["log"] = None
            progress.set(str(error))
            return
        prepare_button.configure(state="disabled")
        play_button.configure(state="disabled")
        progress.set("Reading the capture and preparing OpenAI / ElevenLabs narration. API usage applies.")
        window.after(500, poll)

    def load_job():
        if state["process"] and state["process"].poll() is None:
            return
        path = filedialog.askopenfilename(parent=window, initialdir=str(studio.ROOT / "highlights"), filetypes=(("Prepared highlights", "programme.json"),))
        if not path:
            return
        try:
            job = json.loads(Path(path).read_text(encoding="utf-8"))
            if job.get("schema_version") != 1 or not job.get("segments") or not job.get("source"):
                raise ValueError("This file is not a saved highlight programme.")
            state["job"] = Path(path)
            capture.set(job["source"])
            show_job(job)
            play_button.configure(state="normal" if job.get("status") == "ready" else "disabled")
            if job.get("status") != "ready":
                progress.set("Incomplete programme loaded. Prepare Highlights resumes completed narration for this job.")
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("Prepared highlights", str(error), parent=window)

    def play():
        if studio.has_running_preparation():
            messagebox.showinfo("Highlights preparing", "Let highlight preparation finish before opening the player.", parent=window)
            return
        if studio.has_running_broadcast():
            messagebox.showinfo("Broadcast active", "Stop the current broadcast or highlights player first.", parent=window)
            return
        if not replay_loaded.get():
            messagebox.showinfo("Saved replay required", "Load the matching saved .rpy in iRacing and tick the replay checkbox first.", parent=window)
            return
        try:
            visual_options = {"transition": "cycle" if transition.get().startswith("Cycle") else transition.get().lower(),
                              "transition_sponsor": "" if transition_sponsor.get().strip() == "None" else transition_sponsor.get().strip()[:160],
                              "transition_graphic": import_graphic(graphic.get(), studio.ROOT),
                              "full_screen_graphic": import_graphic(full_screen_graphic.get(), studio.ROOT),
                              "sponsor": "" if sponsor.get().strip() == "None" else sponsor.get().strip()[:160],
                              "sponsor_logo": import_graphic(sponsor_logo.get(), studio.ROOT),
                              "recap_sponsor": "" if recap_sponsor.get().strip() == "None" else recap_sponsor.get().strip()[:160],
                              "recap_sponsor_logo": import_graphic(recap_sponsor_logo.get(), studio.ROOT)}
            save_highlights_title(state["job"], title.get(), visual_options)
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror("Highlights title", str(error), parent=window)
            return
        command = [sys.executable, str(studio.ROOT / "app.py"), "--play-highlights", str(state["job"])]
        state["play_process"] = studio.launch_broadcast(command=command)
        window.after(1000, monitor_player)
        progress.set("Player starting. Use the normal overlay in Streamlabs. Start recording, then Start Highlights in Producer Assist.")
        window.after(1500, lambda: studio.open_external_link(studio.producer_assist_launch_url()))

    def monitor_player():
        if not window.winfo_exists():
            return
        process = state["play_process"]
        if process and process.poll() is None:
            window.after(1000, monitor_player)
        elif process and process.returncode:
            try:
                details = studio.BROADCAST_LOG_PATH.read_text(encoding="utf-8")[-2000:]
            except OSError:
                details = "See logs/broadcast_latest.log."
            progress.set("Highlights player stopped with an error. Check the replay and the message below.")
            preview.insert("end", "\nPlayback error:\n" + details)
            state["play_process"] = None

    def cancel():
        process = state["process"]
        if process and process.poll() is None:
            state["cancelled"] = True
            process.terminate()
            progress.set("Cancelling preparation. Completed job files are retained.")

    def close():
        if state["process"] and state["process"].poll() is None:
            cancel()
            window.after(500, close)
            return
        if state["log"]:
            state["log"].close()
        window.destroy()

    prepare_button = ttk.Button(actions, text="Prepare Highlights", command=prepare)
    prepare_button.pack(side="left")
    ttk.Button(actions, text="Load Prepared", command=load_job).pack(side="left", padx=6)
    play_button = ttk.Button(actions, text="Open Highlights Player", command=play, state="disabled")
    play_button.pack(side="left", padx=6)
    ttk.Button(actions, text="Cancel Preparation", command=cancel).pack(side="right")
    window.protocol("WM_DELETE_WINDOW", close)
    return window
