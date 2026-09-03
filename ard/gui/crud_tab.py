"""A list + form tab that edits one table, built from its TableSpec."""

import tkinter as tk
from datetime import datetime, time
from tkinter import messagebox, ttk

from .. import crud, db
from .spec import Field, TableSpec

TEXTAREA_HEIGHT = 4


class CrudTab(ttk.Frame):
    def __init__(self, master: tk.Misc, spec: TableSpec, on_change=None):
        super().__init__(master, padding=8)
        self.spec = spec
        self.on_change = on_change or (lambda: None)
        self.widgets: dict[str, tk.Widget] = {}
        self.vars: dict[str, tk.Variable] = {}
        self.fk_options: dict[str, list[tuple[int, str]]] = {}
        self.selected_pk: int | None = None

        self._build_list()
        self._build_form()
        self.refresh()

    # ------------------------------------------------------------------ layout

    def _build_list(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True)

        columns = self.spec.columns
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", height=9)
        widths = {self.spec.pk: 70}
        for f in self.spec.fields:
            widths[f.name] = max(70, f.width * 7)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_form(self) -> None:
        form = ttk.LabelFrame(self, text="Details", padding=8)
        form.pack(fill="x", pady=(8, 0))
        form.columnconfigure(1, weight=1)

        for row, f in enumerate(self.spec.fields):
            ttk.Label(form, text=f.label + (" *" if f.required else "")).grid(
                row=row, column=0, sticky="nw", padx=(0, 8), pady=3
            )
            widget = self._make_widget(form, f)
            widget.grid(row=row, column=1, sticky="ew", pady=3)

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", pady=8)
        ttk.Button(buttons, text="New", command=self.clear_form).pack(side="left")
        ttk.Button(buttons, text="Save", command=self.save).pack(side="left", padx=6)
        ttk.Button(buttons, text="Delete", command=self.delete).pack(side="left")
        ttk.Button(buttons, text="Refresh", command=self.refresh).pack(side="right")

    def _make_widget(self, parent: tk.Misc, f: Field) -> tk.Widget:
        if f.kind == "textarea":
            widget = tk.Text(parent, height=TEXTAREA_HEIGHT, wrap="word")
        elif f.kind == "bool":
            var = tk.BooleanVar(value=bool(f.default))
            self.vars[f.name] = var
            widget = ttk.Checkbutton(parent, variable=var)
        elif f.kind in ("choice", "fk"):
            var = tk.StringVar()
            self.vars[f.name] = var
            values = f.choices if f.kind == "choice" else ()
            widget = ttk.Combobox(parent, textvariable=var, values=list(values),
                                  state="readonly")
        else:
            var = tk.StringVar(value="" if f.default is None else str(f.default))
            self.vars[f.name] = var
            widget = ttk.Entry(parent, textvariable=var)
        self.widgets[f.name] = widget
        return widget

    # ------------------------------------------------------------------- data

    def refresh(self) -> None:
        with db.connect() as conn:
            rows = crud.list_rows(conn, self.spec.table, self.spec.columns)
            for f in self.spec.fields:
                if f.kind == "fk":
                    options = crud.options_for(conn, f.lookup)
                    self.fk_options[f.name] = options
                    self.widgets[f.name]["values"] = [label for _, label in options]

        self.tree.delete(*self.tree.get_children())
        for row in rows:
            values = [self._display(row[c]) for c in self.spec.columns]
            self.tree.insert("", "end", iid=str(row[self.spec.pk]), values=values)

    @staticmethod
    def _display(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            # Keep long SQL / bodies on one line in the grid.
            return " ".join(value.split())[:120]
        return str(value)

    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.selected_pk = int(selection[0])
        with db.connect() as conn:
            row = db.fetch_one(
                conn,
                f"SELECT {', '.join(self.spec.columns)} FROM {self.spec.table} "
                f"WHERE {self.spec.pk} = %s",
                (self.selected_pk,),
            )
        if row:
            self._fill_form(row)

    def _fill_form(self, row: dict) -> None:
        for f in self.spec.fields:
            value = row[f.name]
            widget = self.widgets[f.name]
            if f.kind == "textarea":
                widget.delete("1.0", "end")
                widget.insert("1.0", value or "")
            elif f.kind == "bool":
                self.vars[f.name].set(bool(value))
            elif f.kind == "fk":
                label = next((lbl for i, lbl in self.fk_options[f.name] if i == value), "")
                self.vars[f.name].set(label)
            else:
                self.vars[f.name].set("" if value is None else str(value))

    def clear_form(self) -> None:
        self.selected_pk = None
        self.tree.selection_remove(*self.tree.selection())
        for f in self.spec.fields:
            if f.kind == "textarea":
                self.widgets[f.name].delete("1.0", "end")
            elif f.kind == "bool":
                self.vars[f.name].set(bool(f.default))
            else:
                self.vars[f.name].set("" if f.default is None else str(f.default))

    # -------------------------------------------------------------- form <-> db

    def _collect(self) -> dict:
        """Read the form into column values, raising ValueError on bad input."""
        values = {}
        for f in self.spec.fields:
            if f.kind == "textarea":
                raw = self.widgets[f.name].get("1.0", "end").strip()
            elif f.kind == "bool":
                values[f.name] = self.vars[f.name].get()
                continue
            else:
                raw = self.vars[f.name].get().strip()

            if not raw:
                if f.required:
                    raise ValueError(f"{f.label} is required")
                values[f.name] = None
                continue

            if f.kind == "fk":
                values[f.name] = int(raw.split(" - ", 1)[0])
            elif f.kind == "int":
                values[f.name] = int(raw)
            elif f.kind == "time":
                values[f.name] = _parse_time(raw)
            else:
                values[f.name] = raw
        return values

    def save(self) -> None:
        try:
            values = self._collect()
            with db.connect() as conn:
                if self.selected_pk is None:
                    self.selected_pk = crud.insert_row(conn, self.spec.table, values)
                else:
                    crud.update_row(conn, self.spec.table, self.selected_pk, values)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)
            return
        self.refresh()
        self.on_change()

    def delete(self) -> None:
        if self.selected_pk is None:
            messagebox.showinfo("Delete", "Select a row first.", parent=self)
            return
        if not messagebox.askyesno(
            "Delete", f"Delete {self.spec.table} {self.selected_pk}?\n"
                      "Rows that depend on it are removed too.", parent=self):
            return
        try:
            with db.connect() as conn:
                crud.delete_row(conn, self.spec.table, self.selected_pk)
        except Exception as exc:
            messagebox.showerror("Delete failed", str(exc), parent=self)
            return
        self.clear_form()
        self.refresh()
        self.on_change()


def _parse_time(raw: str) -> time:
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"'{raw}' is not a time - use HH:MM")
