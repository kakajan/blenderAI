import bpy
from bpy.props import StringProperty
from bpy.types import Operator

from .. import log_client


class BLENDERAI_OT_logs_refresh(Operator):
    bl_idname = "blender_ai.logs_refresh"
    bl_label = "Refresh Logs"
    bl_description = "Reload recent logs from the sidecar"
    bl_options = {"REGISTER"}

    def execute(self, context):
        ok, logs, err = log_client.fetch_remote(limit=80)
        wm = context.window_manager
        store = getattr(wm, "blender_ai_log_cache", None)
        if store is None:
            self.report({"WARNING"}, "Log cache unavailable")
            return {"CANCELLED"}
        store.clear()
        if ok:
            for item in logs:
                row = store.add()
                row.level = str(item.get("level") or "")[:32]
                row.source = str(item.get("source") or "")[:32]
                row.component = str(item.get("component") or "")[:64]
                row.message = str(item.get("message") or "")[:512]
                row.ts = str(item.get("ts") or "")[:64]
            self.report({"INFO"}, f"Loaded {len(logs)} log(s)")
        else:
            for item in log_client.local_entries(80):
                row = store.add()
                row.level = str(item.get("level") or "")[:32]
                row.source = str(item.get("source") or "")[:32]
                row.component = str(item.get("component") or "")[:64]
                row.message = str(item.get("message") or "")[:512]
                row.ts = str(item.get("ts") or "")[:64]
            self.report({"WARNING"}, f"Sidecar unreachable — showing local buffer ({err})")
        return {"FINISHED"}


class BLENDERAI_OT_logs_clear(Operator):
    bl_idname = "blender_ai.logs_clear"
    bl_label = "Clear Logs"
    bl_description = "Clear local and sidecar log history"
    bl_options = {"REGISTER"}

    def execute(self, context):
        log_client.clear_local()
        ok, err = log_client.clear_remote()
        store = getattr(context.window_manager, "blender_ai_log_cache", None)
        if store is not None:
            store.clear()
        if ok:
            self.report({"INFO"}, "Logs cleared")
        else:
            self.report({"WARNING"}, f"Local cleared; sidecar: {err}")
        return {"FINISHED"}


class BLENDERAI_OT_send_report(Operator):
    bl_idname = "blender_ai.send_report"
    bl_label = "Send Error Report"
    bl_description = "Save an error/crash report (sidecar + AppData/BlenderAI/reports)"
    bl_options = {"REGISTER"}

    summary: StringProperty(
        name="Summary",
        default="BlenderAI error report from N-Panel",
        maxlen=500,
    )
    note: StringProperty(name="Note", default="", maxlen=1000)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "summary")
        layout.prop(self, "note")

    def execute(self, context):
        ok, report, err = log_client.send_report(
            self.summary or "BlenderAI error report",
            kind="error",
            note=self.note or "",
        )
        if not ok:
            self.report({"ERROR"}, f"Report failed: {err}")
            return {"CANCELLED"}
        path = (report or {}).get("file_path") or ""
        if path:
            self.report({"INFO"}, f"Report saved: {path}")
        else:
            self.report({"INFO"}, "Report saved")
        bpy.ops.blender_ai.logs_refresh()
        return {"FINISHED"}


def register():
    bpy.utils.register_class(BLENDERAI_OT_logs_refresh)
    bpy.utils.register_class(BLENDERAI_OT_logs_clear)
    bpy.utils.register_class(BLENDERAI_OT_send_report)


def unregister():
    bpy.utils.unregister_class(BLENDERAI_OT_send_report)
    bpy.utils.unregister_class(BLENDERAI_OT_logs_clear)
    bpy.utils.unregister_class(BLENDERAI_OT_logs_refresh)
