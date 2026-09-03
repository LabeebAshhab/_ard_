"""Scheduler controls, live log output and the EXECUTION_LOG viewer."""

import logging
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .. import crud, db
from ..config import config
from ..runner import run_task_by_id
from ..scheduler import poll_once, run_forever


class QueueHandler(logging.Handler):
    """Pipes log records to the Tk thread, which drains the queue on a timer."""

    def __init__(self, target: queue.Queue):
        super().__init__()
        self.target = target

    def emit(self, record: logging.LogRecord) -> None:
        self.target.put(self.format(record))


class RunTab(ttk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=8)
        self.log_queue: queue.Queue[str] = queue.Queue()
        # Worker threads must not touch Tk directly, so they raise this flag and the
        # main thread picks it up on its timer.
        self.refresh_flag = threading.Event()
        self.stop_event: threading.Event | None = None
        self.worker: threading.Thread | None = None

        self._build_controls()
        self._build_log_view()
        self._build_output()
        self._attach_log_handler()

        self.refresh()
        self.after(200, self._drain_log)

    # --------------------------------------------------------------- controls

    def _build_controls(self) -> None:
        bar = ttk.LabelFrame(self, text="Automated report delivery", padding=8)
        bar.pack(fill="x")

        self.status = tk.StringVar(value="scheduler stopped")
        self.start_btn = ttk.Button(bar, text="Start scheduler", command=self.start)
        self.stop_btn = ttk.Button(bar, text="Stop scheduler", command=self.stop,
                                   state="disabled")
        self.start_btn.pack(side="left")
        self.stop_btn.pack(side="left", padx=6)
        ttk.Button(bar, text="Check now (one tick)", command=self.poll_now).pack(side="left")

        ttk.Label(bar, textvariable=self.status).pack(side="right")

        manual = ttk.LabelFrame(self, text="Run one task now (ignores the schedule time)",
                                padding=8)
        manual.pack(fill="x", pady=8)
        self.task_var = tk.StringVar()
        self.task_box = ttk.Combobox(manual, textvariable=self.task_var, state="readonly",
                                     width=40)
        self.task_box.pack(side="left")
        ttk.Button(manual, text="Run task", command=self.run_selected).pack(side="left", padx=6)
        ttk.Label(manual, text=f"poll interval: {config.poll_interval_minutes} min | "
                               f"dry-run mail: {config.smtp_dry_run}").pack(side="right")

    def _build_log_view(self) -> None:
        frame = ttk.LabelFrame(self, text="Execution log", padding=8)
        frame.pack(fill="both", expand=True)

        columns = ("log_id", "task", "run_started_at", "status", "row_count",
                   "csv_file_path", "delivered_at", "error_message")
        widths = (60, 170, 150, 80, 70, 260, 150, 240)
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        for col, width in zip(columns, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        ttk.Button(self, text="Refresh log", command=self.refresh).pack(anchor="e", pady=6)

    def _build_output(self) -> None:
        frame = ttk.LabelFrame(self, text="Program output", padding=8)
        frame.pack(fill="both", expand=True)
        self.output = tk.Text(frame, height=8, wrap="none", state="disabled")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=scroll.set)
        self.output.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _attach_log_handler(self) -> None:
        handler = QueueHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                                               datefmt="%H:%M:%S"))
        ard_logger = logging.getLogger("ard")
        ard_logger.setLevel(logging.INFO)
        ard_logger.addHandler(handler)

    # ------------------------------------------------------------------ actions

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.stop_event = threading.Event()
        self.worker = threading.Thread(
            target=run_forever, kwargs={"stop_event": self.stop_event,
                                        "on_tick": self._after_tick},
            daemon=True,
        )
        self.worker.start()
        self.status.set(f"scheduler running - every {config.poll_interval_minutes} min")
        self.start_btn.state(["disabled"])
        self.stop_btn.state(["!disabled"])

    def stop(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        self.status.set("scheduler stopping...")
        self.start_btn.state(["!disabled"])
        self.stop_btn.state(["disabled"])
        self.after(500, lambda: self.status.set("scheduler stopped"))

    def poll_now(self) -> None:
        self._run_in_thread(poll_once)

    def run_selected(self) -> None:
        raw = self.task_var.get()
        if not raw:
            messagebox.showinfo("Run task", "Pick a task first.", parent=self)
            return
        task_id = int(raw.split(" - ", 1)[0])
        self._run_in_thread(run_task_by_id_wrapper, task_id)

    def _run_in_thread(self, func, *args) -> None:
        """Keeps the window responsive while a query / send is in flight."""
        def work():
            try:
                func(*args)
            except Exception as exc:
                self.log_queue.put(f"ERROR: {exc}")
            self.refresh_flag.set()

        threading.Thread(target=work, daemon=True).start()

    def _after_tick(self, ran: int) -> None:
        self.refresh_flag.set()

    # -------------------------------------------------------------------- views

    def refresh(self) -> None:
        with db.connect() as conn:
            rows = db.fetch_all(
                conn,
                """
                SELECT l.log_id, t.task_name, l.run_started_at, l.status, l.row_count,
                       l.csv_file_path, l.delivered_at, l.error_message
                FROM execution_log l
                JOIN task t ON t.task_id = l.task_id
                ORDER BY l.log_id DESC
                LIMIT 200
                """,
            )
            tasks = crud.options_for(conn, "task")

        self.task_box["values"] = [label for _, label in tasks]
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", values=(
                r["log_id"], r["task_name"],
                r["run_started_at"].strftime("%Y-%m-%d %H:%M:%S"),
                r["status"], "" if r["row_count"] is None else r["row_count"],
                r["csv_file_path"] or "",
                r["delivered_at"].strftime("%Y-%m-%d %H:%M:%S") if r["delivered_at"] else "",
                " ".join((r["error_message"] or "").split()),
            ))

    def _drain_log(self) -> None:
        lines = []
        while True:
            try:
                lines.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        if self.refresh_flag.is_set():
            self.refresh_flag.clear()
            self.refresh()
        if lines:
            self.output.configure(state="normal")
            self.output.insert("end", "\n".join(lines) + "\n")
            self.output.see("end")
            self.output.configure(state="disabled")
        self.after(200, self._drain_log)


def run_task_by_id_wrapper(task_id: int) -> None:
    with db.connect() as conn:
        run_task_by_id(conn, task_id)
