from __future__ import annotations

import json
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any


DATA_FILE = Path(__file__).with_name("tasks.json")
DATE_FORMAT = "%Y-%m-%d"
PRIORITIES = ("高", "中", "低")
STATUSES = ("未完成", "已完成")
SORT_OPTIONS = ("建立時間", "截止日期", "優先順序", "完成狀態")


@dataclass
class Task:
    id: int
    title: str
    subject: str
    due_date: str
    priority: str
    status: str
    note: str
    created_at: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Task":
        return cls(
            id=int(raw["id"]),
            title=str(raw["title"]),
            subject=str(raw.get("subject", "")),
            due_date=str(raw["due_date"]),
            priority=str(raw.get("priority", "中")),
            status=str(raw.get("status", "未完成")),
            note=str(raw.get("note", "")),
            created_at=str(raw.get("created_at", date.today().strftime(DATE_FORMAT))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "subject": self.subject,
            "due_date": self.due_date,
            "priority": self.priority,
            "status": self.status,
            "note": self.note,
            "created_at": self.created_at,
        }


class TaskStore:
    def __init__(self, path: Path = DATA_FILE) -> None:
        self.path = path
        self.tasks: list[Task] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.tasks = []
            return

        try:
            raw_tasks = json.loads(self.path.read_text(encoding="utf-8"))
            self.tasks = [Task.from_dict(item) for item in raw_tasks]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"無法讀取任務資料：{exc}") from exc

    def save(self) -> None:
        payload = [task.to_dict() for task in self.tasks]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def next_id(self) -> int:
        return max((task.id for task in self.tasks), default=0) + 1

    def add(self, title: str, subject: str, due_date: str, priority: str, note: str) -> Task:
        validate_task_input(title, due_date, priority)
        task = Task(
            id=self.next_id(),
            title=title.strip(),
            subject=subject.strip(),
            due_date=due_date.strip(),
            priority=priority,
            status="未完成",
            note=note.strip(),
            created_at=date.today().strftime(DATE_FORMAT),
        )
        self.tasks.append(task)
        self.save()
        return task

    def update(
        self,
        task_id: int,
        title: str,
        subject: str,
        due_date: str,
        priority: str,
        note: str,
    ) -> Task:
        validate_task_input(title, due_date, priority)
        task = self.get(task_id)
        task.title = title.strip()
        task.subject = subject.strip()
        task.due_date = due_date.strip()
        task.priority = priority
        task.note = note.strip()
        self.save()
        return task

    def delete(self, task_id: int) -> None:
        original_count = len(self.tasks)
        self.tasks = [task for task in self.tasks if task.id != task_id]
        if len(self.tasks) == original_count:
            raise KeyError(f"找不到任務 ID：{task_id}")
        self.save()

    def toggle_status(self, task_id: int) -> Task:
        task = self.get(task_id)
        task.status = "已完成" if task.status == "未完成" else "未完成"
        self.save()
        return task

    def get(self, task_id: int) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"找不到任務 ID：{task_id}")

    def filtered_sorted(self, keyword: str = "", sort_by: str = "建立時間") -> list[Task]:
        keyword = keyword.strip().lower()
        tasks = self.tasks
        if keyword:
            tasks = [
                task
                for task in tasks
                if keyword in task.title.lower()
                or keyword in task.subject.lower()
                or keyword in task.note.lower()
            ]

        priority_rank = {"高": 0, "中": 1, "低": 2}
        status_rank = {"未完成": 0, "已完成": 1}

        if sort_by == "截止日期":
            return sorted(tasks, key=lambda task: parse_date(task.due_date))
        if sort_by == "優先順序":
            return sorted(tasks, key=lambda task: priority_rank.get(task.priority, 99))
        if sort_by == "完成狀態":
            return sorted(tasks, key=lambda task: status_rank.get(task.status, 99))
        return sorted(tasks, key=lambda task: (task.created_at, task.id))

    def stats(self) -> dict[str, int | float]:
        total = len(self.tasks)
        completed = sum(1 for task in self.tasks if task.status == "已完成")
        pending = total - completed
        overdue = sum(1 for task in self.tasks if is_overdue(task))
        completion_rate = round((completed / total) * 100, 1) if total else 0.0
        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
            "completion_rate": completion_rate,
        }


def parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FORMAT).date()


def validate_task_input(title: str, due_date: str, priority: str) -> None:
    if not title.strip():
        raise ValueError("任務名稱不能空白。")
    if priority not in PRIORITIES:
        raise ValueError("優先順序必須是高、中或低。")
    try:
        parse_date(due_date.strip())
    except ValueError as exc:
        raise ValueError("截止日期格式必須是 YYYY-MM-DD，例如 2026-06-10。") from exc


def is_overdue(task: Task) -> bool:
    return task.status == "未完成" and parse_date(task.due_date) < date.today()


class TaskManagerApp:
    def __init__(self, root: tk.Tk, store: TaskStore) -> None:
        self.root = root
        self.store = store
        self.selected_task_id: int | None = None

        self.title_var = tk.StringVar()
        self.subject_var = tk.StringVar()
        self.due_date_var = tk.StringVar(value=date.today().strftime(DATE_FORMAT))
        self.priority_var = tk.StringVar(value="中")
        self.search_var = tk.StringVar()
        self.sort_var = tk.StringVar(value="建立時間")
        self.stats_var = tk.StringVar()

        self.setup_window()
        self.build_ui()
        self.refresh_list()

    def setup_window(self) -> None:
        self.root.title("學生讀書任務管理器")
        self.root.geometry("1040x680")
        self.root.minsize(920, 600)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Microsoft JhengHei", 18, "bold"))
        style.configure("Section.TLabel", font=("Microsoft JhengHei", 11, "bold"))
        style.configure("Treeview", rowheight=30, font=("Microsoft JhengHei", 10))
        style.configure("Treeview.Heading", font=("Microsoft JhengHei", 10, "bold"))

    def build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main)
        header.pack(fill=tk.X)
        ttk.Label(header, text="學生讀書任務管理器", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self.stats_var).pack(side=tk.RIGHT)

        form = ttk.LabelFrame(main, text="任務內容", padding=12)
        form.pack(fill=tk.X, pady=(14, 10))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="任務名稱").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=self.title_var).grid(row=0, column=1, sticky=tk.EW, pady=4)

        ttk.Label(form, text="科目").grid(row=0, column=2, sticky=tk.W, padx=(16, 8), pady=4)
        ttk.Entry(form, textvariable=self.subject_var).grid(row=0, column=3, sticky=tk.EW, pady=4)

        ttk.Label(form, text="截止日期").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=self.due_date_var).grid(row=1, column=1, sticky=tk.EW, pady=4)

        ttk.Label(form, text="優先順序").grid(row=1, column=2, sticky=tk.W, padx=(16, 8), pady=4)
        ttk.Combobox(
            form,
            textvariable=self.priority_var,
            values=PRIORITIES,
            state="readonly",
        ).grid(row=1, column=3, sticky=tk.EW, pady=4)

        ttk.Label(form, text="備註").grid(row=2, column=0, sticky=tk.NW, padx=(0, 8), pady=4)
        self.note_text = tk.Text(form, height=3, wrap=tk.WORD, font=("Microsoft JhengHei", 10))
        self.note_text.grid(row=2, column=1, columnspan=3, sticky=tk.EW, pady=4)

        button_row = ttk.Frame(form)
        button_row.grid(row=3, column=0, columnspan=4, sticky=tk.E, pady=(8, 0))
        ttk.Button(button_row, text="新增任務", command=self.add_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="更新任務", command=self.update_task).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="清空欄位", command=self.clear_form).pack(side=tk.LEFT, padx=4)

        tools = ttk.Frame(main)
        tools.pack(fill=tk.X, pady=(4, 8))
        ttk.Label(tools, text="搜尋").pack(side=tk.LEFT)
        search_entry = ttk.Entry(tools, textvariable=self.search_var, width=28)
        search_entry.pack(side=tk.LEFT, padx=(8, 16))
        search_entry.bind("<KeyRelease>", lambda _event: self.refresh_list())

        ttk.Label(tools, text="排序").pack(side=tk.LEFT)
        sort_box = ttk.Combobox(
            tools,
            textvariable=self.sort_var,
            values=SORT_OPTIONS,
            state="readonly",
            width=12,
        )
        sort_box.pack(side=tk.LEFT, padx=(8, 0))
        sort_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_list())

        table_frame = ttk.Frame(main)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("title", "subject", "due_date", "priority", "status", "note")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "title": "任務名稱",
            "subject": "科目",
            "due_date": "截止日期",
            "priority": "優先",
            "status": "狀態",
            "note": "備註",
        }
        widths = {
            "title": 230,
            "subject": 130,
            "due_date": 110,
            "priority": 70,
            "status": 90,
            "note": 330,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor=tk.W)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        action_row = ttk.Frame(main)
        action_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(action_row, text="切換完成狀態", command=self.toggle_selected_status).pack(
            side=tk.LEFT,
            padx=(0, 8),
        )
        ttk.Button(action_row, text="刪除任務", command=self.delete_selected_task).pack(side=tk.LEFT)

    def get_note(self) -> str:
        return self.note_text.get("1.0", tk.END).strip()

    def set_note(self, text: str) -> None:
        self.note_text.delete("1.0", tk.END)
        self.note_text.insert("1.0", text)

    def add_task(self) -> None:
        try:
            self.store.add(
                self.title_var.get(),
                self.subject_var.get(),
                self.due_date_var.get(),
                self.priority_var.get(),
                self.get_note(),
            )
        except ValueError as exc:
            messagebox.showerror("輸入錯誤", str(exc))
            return
        self.clear_form()
        self.refresh_list()

    def update_task(self) -> None:
        if self.selected_task_id is None:
            messagebox.showinfo("尚未選取任務", "請先在列表中選取要更新的任務。")
            return
        try:
            self.store.update(
                self.selected_task_id,
                self.title_var.get(),
                self.subject_var.get(),
                self.due_date_var.get(),
                self.priority_var.get(),
                self.get_note(),
            )
        except (KeyError, ValueError) as exc:
            messagebox.showerror("更新失敗", str(exc))
            return
        self.refresh_list()

    def delete_selected_task(self) -> None:
        if self.selected_task_id is None:
            messagebox.showinfo("尚未選取任務", "請先在列表中選取要刪除的任務。")
            return
        if not messagebox.askyesno("確認刪除", "確定要刪除這個任務嗎？"):
            return
        try:
            self.store.delete(self.selected_task_id)
        except KeyError as exc:
            messagebox.showerror("刪除失敗", str(exc))
            return
        self.clear_form()
        self.refresh_list()

    def toggle_selected_status(self) -> None:
        if self.selected_task_id is None:
            messagebox.showinfo("尚未選取任務", "請先在列表中選取任務。")
            return
        try:
            self.store.toggle_status(self.selected_task_id)
        except KeyError as exc:
            messagebox.showerror("狀態切換失敗", str(exc))
            return
        self.refresh_list()

    def on_select(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        task_id = int(selected[0])
        task = self.store.get(task_id)
        self.selected_task_id = task.id
        self.title_var.set(task.title)
        self.subject_var.set(task.subject)
        self.due_date_var.set(task.due_date)
        self.priority_var.set(task.priority)
        self.set_note(task.note)

    def clear_form(self) -> None:
        self.selected_task_id = None
        self.title_var.set("")
        self.subject_var.set("")
        self.due_date_var.set(date.today().strftime(DATE_FORMAT))
        self.priority_var.set("中")
        self.set_note("")
        self.tree.selection_remove(self.tree.selection())

    def refresh_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for task in self.store.filtered_sorted(self.search_var.get(), self.sort_var.get()):
            title = f"{task.title}（逾期）" if is_overdue(task) else task.title
            self.tree.insert(
                "",
                tk.END,
                iid=str(task.id),
                values=(title, task.subject, task.due_date, task.priority, task.status, task.note),
            )

        stats = self.store.stats()
        self.stats_var.set(
            f"總數 {stats['total']}｜已完成 {stats['completed']}｜未完成 {stats['pending']}｜"
            f"逾期 {stats['overdue']}｜完成率 {stats['completion_rate']}%"
        )


def main() -> None:
    try:
        store = TaskStore()
    except ValueError as exc:
        messagebox.showerror("資料讀取失敗", str(exc))
        return

    root = tk.Tk()
    TaskManagerApp(root, store)
    root.mainloop()


if __name__ == "__main__":
    main()
