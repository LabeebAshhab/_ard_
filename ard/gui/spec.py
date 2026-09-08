"""Declarative description of each editable table, driving the generic CRUD tabs.

kind: text | textarea | int | time | bool | choice | fk
"""

from dataclasses import dataclass, field


@dataclass
class Field:
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    choices: tuple = ()
    lookup: str = ""          # for kind="fk": the table to pull (id, label) from
    default: object = None
    width: int = 22           # column width in the grid


@dataclass
class TableSpec:
    table: str
    pk: str
    title: str
    fields: list[Field] = field(default_factory=list)

    @property
    def columns(self) -> list[str]:
        return [self.pk] + [f.name for f in self.fields]


TASK = TableSpec(
    table="task", pk="task_id", title="1. Task",
    fields=[
        Field("task_name", "Task name", required=True, width=26),
        Field("description", "Description", width=34),
        Field("is_active", "Active", kind="bool", default=True, width=8),
    ],
)

QUERY = TableSpec(
    table="query", pk="query_id", title="2. Query",
    fields=[
        Field("task_id", "Task", kind="fk", lookup="task", required=True, width=22),
        Field("query_text", "SQL", kind="textarea", required=True, width=60),
        Field("output_name", "Output name (file prefix)", width=22),
        Field("db_target", "DB target", required=True, default="core_db", width=16),
        Field("version_no", "Version", kind="int", default=1, width=8),
        Field("is_active", "Active", kind="bool", default=True, width=8),
    ],
)

SCHEDULE = TableSpec(
    table="schedule", pk="schedule_id", title="3. Schedule",
    fields=[
        Field("task_id", "Task", kind="fk", lookup="task", required=True, width=22),
        Field("schedule_time", "Time (HH:MM)", kind="time", required=True, width=14),
        Field("frequency", "Frequency", kind="choice",
              choices=("DAILY", "WEEKLY", "MONTHLY"), default="DAILY", width=12),
        Field("day_spec", "Day spec", width=16),
        Field("is_active", "Active", kind="bool", default=True, width=8),
    ],
)

EMAIL_CONFIG = TableSpec(
    table="email_config", pk="config_id", title="4. Email config",
    fields=[
        Field("task_id", "Task", kind="fk", lookup="task", required=True, width=22),
        Field("subject", "Subject", required=True, width=34),
        Field("body", "Body", kind="textarea", width=44),
        Field("signature", "Signature", kind="textarea", width=24),
    ],
)

RECIPIENT = TableSpec(
    table="recipient", pk="recipient_id", title="5. Recipient",
    fields=[
        Field("config_id", "Email config", kind="fk", lookup="email_config",
              required=True, width=24),
        Field("email_address", "Address", required=True, width=30),
        Field("recipient_type", "Type", kind="choice", choices=("TO", "CC", "BCC"),
              default="TO", width=8),
        Field("display_name", "Display name", width=20),
        Field("is_active", "Active", kind="bool", default=True, width=8),
    ],
)

SPECS = [TASK, QUERY, SCHEDULE, EMAIL_CONFIG, RECIPIENT]
