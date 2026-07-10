bl_info = {
    "name": "AutoRemesher Bridge",
    "author": "Adriflex",
    "version": (0, 1, 3),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > AutoRemesher",
    "description": "Run AutoRemesher on the active mesh and import the result as a copy",
    "category": "Object",
}

import os
from pathlib import Path
import subprocess
import tempfile

import bpy

from .bridge_helpers import (
    ENV_EXECUTABLE,
    build_autoremesher_command,
    resolve_executable_path,
    validate_executable,
)

AUTHOR_URL = "https://adriflex.github.io/"
AUTOREMESHER_RELEASES_URL = "https://github.com/huxingyi/autoremesher/releases"


class AUTOREMESHERBRIDGE_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    executable_path: bpy.props.StringProperty(
        name="AutoRemesher Executable",
        description=f"Leave empty to use the {ENV_EXECUTABLE} environment variable or PATH",
        subtype="FILE_PATH",
        default="",
    )

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "executable_path")
        layout.separator()
        layout.operator(
            "wm.url_open",
            text="Download AutoRemesher",
            icon="IMPORT",
        ).url = AUTOREMESHER_RELEASES_URL
        layout.operator("wm.url_open", text="Adriflex Blog", icon="URL").url = AUTHOR_URL


class AUTOREMESHERBRIDGE_Settings(bpy.types.PropertyGroup):
    target_quads: bpy.props.IntProperty(
        name="Target Quads",
        default=50000,
        min=100,
        soft_max=500000,
    )
    edge_scaling: bpy.props.FloatProperty(
        name="Edge Scaling",
        default=1.0,
        min=1.0,
        max=4.0,
        precision=2,
    )
    sharp_edge: bpy.props.FloatProperty(
        name="Sharp Edge",
        description="Dihedral angle threshold in degrees",
        default=90.0,
        min=30.0,
        max=180.0,
        precision=1,
    )
    smooth_normal: bpy.props.FloatProperty(
        name="Smooth Normal",
        description="Normal smoothing angle in degrees",
        default=0.0,
        min=0.0,
        max=180.0,
        precision=1,
    )
    adaptivity: bpy.props.FloatProperty(
        name="Adaptivity",
        description="Curvature-adaptive quad density",
        default=1.0,
        min=0.0,
        max=1.0,
        precision=2,
    )
    apply_modifiers: bpy.props.BoolProperty(
        name="Apply Modifiers",
        default=True,
    )
    transfer_uvs: bpy.props.BoolProperty(
        name="Transfer UVs",
        default=True,
    )
    hide_original: bpy.props.BoolProperty(
        name="Hide Original",
        default=False,
    )


class AUTOREMESHERBRIDGE_OT_remesh_active(bpy.types.Operator):
    bl_idname = "object.autoremesher_bridge_remesh_active"
    bl_label = "AutoRemesh Active Mesh"
    bl_description = "Run AutoRemesher on the active mesh and import the result as a new object"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def execute(self, context):
        settings = context.scene.autoremesher_bridge_settings
        prefs = context.preferences.addons[__package__].preferences
        configured_path = bpy.path.abspath(prefs.executable_path)
        executable = resolve_executable_path(configured_path)
        error = validate_executable(executable)
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}

        source_obj = context.active_object
        original_selection = list(context.selected_objects)
        original_active = context.view_layer.objects.active
        finished_import = None

        with tempfile.TemporaryDirectory(prefix="autoremesher_bridge_") as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.obj"
            output_path = temp_path / "output.obj"
            report_path = temp_path / "report.txt"

            try:
                self._export_active_mesh(context, source_obj, input_path, settings)
                command = build_autoremesher_command(
                    executable,
                    input_path,
                    output_path,
                    report_path,
                    target_quads=settings.target_quads,
                    edge_scaling=settings.edge_scaling,
                    sharp_edge=settings.sharp_edge,
                    smooth_normal=settings.smooth_normal,
                    adaptivity=settings.adaptivity,
                )
                result = subprocess.run(
                    command,
                    cwd=str(executable.parent),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode != 0:
                    message = result.stderr.strip() or result.stdout.strip()
                    self.report({"ERROR"}, message or "AutoRemesher failed")
                    return {"CANCELLED"}
                if not output_path.is_file():
                    self.report({"ERROR"}, "AutoRemesher did not create an output OBJ")
                    return {"CANCELLED"}

                imported = self._import_result(context, output_path)
                imported.name = f"{source_obj.name}_autoremesh"
                imported.data.name = f"{source_obj.data.name}_autoremesh"
                self._copy_materials(source_obj, imported)
                if settings.transfer_uvs and source_obj.data.uv_layers:
                    self._transfer_uvs(context, source_obj, imported)
                if settings.hide_original:
                    source_obj.hide_set(True)

                self._select_only(context, imported)
                finished_import = imported
                self._report_stats(report_path)
                return {"FINISHED"}
            finally:
                if finished_import is None:
                    self._restore_selection(context, original_selection, original_active)

    def _export_active_mesh(self, context, source_obj, input_path, settings):
        self._select_only(context, source_obj)
        bpy.ops.wm.obj_export(
            filepath=str(input_path),
            check_existing=False,
            export_selected_objects=True,
            apply_modifiers=settings.apply_modifiers,
            export_normals=True,
            export_uv=True,
            forward_axis="NEGATIVE_Z",
            up_axis="Y",
        )

    def _import_result(self, context, output_path):
        before = set(bpy.data.objects)
        bpy.ops.wm.obj_import(
            filepath=str(output_path),
            use_split_objects=False,
            use_split_groups=False,
            forward_axis="NEGATIVE_Z",
            up_axis="Y",
        )
        created = [obj for obj in bpy.data.objects if obj not in before]
        if not created:
            raise RuntimeError("Blender did not import any object")
        return created[0]

    def _copy_materials(self, source_obj, imported):
        imported.data.materials.clear()
        for material in source_obj.data.materials:
            imported.data.materials.append(material)

    def _transfer_uvs(self, context, source_obj, imported):
        self._select_only(context, imported)
        source_obj.select_set(True)
        context.view_layer.objects.active = source_obj
        try:
            bpy.ops.object.data_transfer(
                data_type="UV",
                use_create=True,
                vert_mapping="NEAREST",
                edge_mapping="NEAREST",
                loop_mapping="NEAREST_POLYNOR",
                poly_mapping="NEAREST",
                use_object_transform=True,
                layers_select_src="ACTIVE",
                layers_select_dst="ACTIVE",
                mix_mode="REPLACE",
                mix_factor=1.0,
            )
        except Exception as exc:
            self.report({"WARNING"}, f"Remesh done, but UV transfer failed: {exc}")

    def _select_only(self, context, obj):
        for scene_obj in context.scene.objects:
            scene_obj.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

    def _restore_selection(self, context, selected_objects, active_object):
        for scene_obj in context.scene.objects:
            scene_obj.select_set(False)
        for obj in selected_objects:
            if context.scene.objects.get(obj.name):
                obj.select_set(True)
        if active_object and context.scene.objects.get(active_object.name):
            context.view_layer.objects.active = active_object

    def _report_stats(self, report_path):
        if not report_path.is_file():
            self.report({"INFO"}, "AutoRemesher finished")
            return
        lines = [
            line.strip()
            for line in report_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
        self.report({"INFO"}, lines[-1] if lines else "AutoRemesher finished")


class AUTOREMESHERBRIDGE_PT_panel(bpy.types.Panel):
    bl_label = "AutoRemesher"
    bl_idname = "AUTOREMESHERBRIDGE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AutoRemesher"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.autoremesher_bridge_settings
        prefs = context.preferences.addons[__package__].preferences

        layout.prop(settings, "target_quads")
        layout.prop(settings, "adaptivity")
        layout.prop(settings, "edge_scaling")
        layout.prop(settings, "sharp_edge")
        layout.prop(settings, "smooth_normal")
        layout.separator()
        layout.prop(settings, "apply_modifiers")
        layout.prop(settings, "transfer_uvs")
        layout.prop(settings, "hide_original")
        layout.separator()
        layout.operator(AUTOREMESHERBRIDGE_OT_remesh_active.bl_idname)

        executable = resolve_executable_path(bpy.path.abspath(prefs.executable_path))
        if not os.path.isfile(executable):
            layout.separator()
            layout.label(text="Set AutoRemesher executable in add-on preferences.", icon="ERROR")


classes = (
    AUTOREMESHERBRIDGE_AddonPreferences,
    AUTOREMESHERBRIDGE_Settings,
    AUTOREMESHERBRIDGE_OT_remesh_active,
    AUTOREMESHERBRIDGE_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.autoremesher_bridge_settings = bpy.props.PointerProperty(
        type=AUTOREMESHERBRIDGE_Settings
    )


def unregister():
    del bpy.types.Scene.autoremesher_bridge_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
