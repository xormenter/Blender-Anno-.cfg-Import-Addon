from __future__ import annotations
import bpy

from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy_extras.object_utils import AddObjectHelper, object_data_add
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator, AddonPreferences
from bpy.types import Object as BlenderObject
import xml.etree.ElementTree as ET
import os
import re
import subprocess
import mathutils
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, NewType, Any, Union, Dict, Optional, TypeVar, Type

from .simple_anno_feedback_encoding import SimpleAnnoFeedbackEncoding
from .prefs import IO_AnnocfgPreferences
from .anno_objects import get_anno_object_class, Transform, AnnoObject, MainFile, Model, SimpleAnnoFeedbackEncodingObject, \
    SubFile, Decal, Propcontainer, Prop, Particle, IfoCube, IfoPlane, Sequence, DummyGroup, \
    Dummy, Cf7DummyGroup, Cf7Dummy, FeedbackConfig, Light, IfoFile, Cf7File


from .utils import data_path_to_absolute_path, to_data_path



class ExportAnnoCfg(Operator, ExportHelper):
    """Exports the selected MAIN_FILE into a .cfg Anno file. Check the export ifo box to also create the .ifo/.cf7 file."""
    bl_idname = "export.anno_cfg_files" 
    bl_label = "Export Anno .cfg Files"

    # ImportHelper mixin class uses this
    filename_ext = ".cfg"

    filter_glob: StringProperty( #type: ignore
        default="*.cfg",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    also_export_ifo: BoolProperty( #type: ignore
        name="Export IFO",
        description="Also writes an .ifo file of the same name.",
        default=True,
    )
    also_export_feedback: BoolProperty( #type: ignore
        name="Export Feedback",
        description="Also writes an feedback file of the same name.",
        default=True,
    )
    export_feedback_type: EnumProperty( #type: ignore
        name="Feedback Type",
        description="Either cf7 or simple anno feedback encoding. Use cf7 if you didn't edit the simple anno feedback or just moved a few dummies around. ",
        items = [("cf7", "cf7", "cf7"), ("safe", "Simple Anno Feedback", "Export your custom feedback definition.")],
        default="cf7",
    )
    convert_safe_to_fc: BoolProperty( #type: ignore
        name="Convert s.a.f.e. to .fc",
        description="Auto convert the SimpleAnnoFeedbackEncoding to .cf7 and .fc after exporting it. Only relevant when using FeedbackType SimpleAnnoFeedbackEncoding.",
        default=True,
    )
    
    
    @classmethod
    def poll(cls, context):
        if not context.active_object:
            return False
        return get_anno_object_class(context.active_object) == MainFile
    

    def execute(self, context):
        if not context.active_object:
            self.report({'ERROR'}, f"MAIN_FILE Object needs to be selected. CANCELLED")
            return {'CANCELLED'}
        self.main_obj = context.active_object
        # if not self.main_obj.dynamic_properties.config_type == "MainFile":
        #     self.report({'ERROR'}, f"MAIN_FILE Object needs to be selected. CANCELLED")
        #     return {'CANCELLED'}
        print("EXPORTING", self.main_obj.name, "to", self.filepath)

        self.initialize_child_map()

        self.export_cfg_file()

        if self.also_export_ifo:
            ifo_obj  = self.find_child_of_type(self.main_obj, IfoFile)
            if ifo_obj is not None:
                self.export_ifo(ifo_obj, Path(self.filepath).with_suffix(".ifo"))
                
        if self.also_export_feedback:
            feedback_obj = None
            if self.export_feedback_type == "safe":
                feedback_obj = self.find_child_of_type(self.main_obj, SimpleAnnoFeedbackEncodingObject)
            if self.export_feedback_type == "cf7":
                feedback_obj = self.find_child_of_type(self.main_obj, Cf7File)
            if not feedback_obj is None:
                if self.export_feedback_type == "safe":
                    self.export_safe_file(feedback_obj, Path(self.filepath).with_suffix(".xml"))
                if self.export_feedback_type == "cf7":
                    self.export_cf7_file(feedback_obj, Path(self.filepath).with_suffix(".cf7"))
            else:
                self.report({'ERROR'}, 'No Feedback Object, cannot export Feedback')


        self.report({'INFO'}, 'Export completed!')
        return {'FINISHED'}
    
    def find_child_of_type(self, obj, search_cls):
        for child_obj in self.children_by_object[obj.name]:
            if get_anno_object_class(child_obj) == search_cls:
                return child_obj
        return None
    
    def export_cfg_file(self):
        print("EXPORT MAIN OBJ", self.main_obj.name)
        self.root = MainFile.blender_to_xml(self.main_obj, None, self.children_by_object)
        tree = ET.ElementTree(self.root)
        ET.indent(tree, space="\t", level=0)
        tree.write(self.filepath)
        self.report({'INFO'}, 'cfg export completed')

    def get_text(self, node, query, default = ""):
        if node.find(query) is not None:
            return node.find(query).text
        return default

    def export_ifo(self, ifo_obj, ifo_filepath):
        print("EXPORT IFO", ifo_obj.name)
        root = IfoFile.blender_to_xml(ifo_obj, None, self.children_by_object)
        ifotree = ET.ElementTree(element = root)
        
        ET.indent(ifotree, space="\t", level=0)
        ifotree.write(ifo_filepath)

    def export_cf7_file(self, cf7_object, cf7_filepath): 
        cf7root = Cf7File.blender_to_xml(cf7_object, None, self.children_by_object)
        cf7tree = ET.ElementTree(cf7root)
        ET.indent(cf7tree, space="\t", level=0)
        cf7tree_string = ET.tostring(cf7root, encoding='unicode', method='xml')
        cf7tree_string = cf7tree_string.replace("</cf7_imaginary_root>", "").replace("<cf7_imaginary_root>","")
        with open(cf7_filepath, 'w') as f:
            f.write(cf7tree_string)
        if IO_AnnocfgPreferences.get_path_to_fc_converter().exists():
            subprocess.call(f"\"{IO_AnnocfgPreferences.get_path_to_fc_converter()}\" -w \"{cf7_filepath}\" -y -o \"{cf7_filepath.with_suffix('.fc')}\"")
        return

   

    def export_safe_file(self, feedback_object, safe_filepath): 
        root = SimpleAnnoFeedbackEncodingObject.blender_to_xml(feedback_object, None, self.children_by_object)
        tree = ET.ElementTree(root)

        ET.indent(tree, space="\t", level=0)
        tree.write(safe_filepath)
        if self.convert_safe_to_fc:
            safe = SimpleAnnoFeedbackEncoding(root)
            safe.write_as_cf7(safe_filepath.with_suffix(".cf7"))
            if IO_AnnocfgPreferences.get_path_to_fc_converter().exists():
                subprocess.call(f"\"{IO_AnnocfgPreferences.get_path_to_fc_converter()}\" -w \"{safe_filepath.with_suffix('.cf7')}\" -y -o \"{safe_filepath.with_suffix('.fc')}\"")


    def initialize_child_map(self):
        self.children_by_object = {}
        for obj in bpy.data.objects:
            if obj.parent is not None:
                if obj.parent.name in self.children_by_object:
                    self.children_by_object[obj.parent.name].append(obj)
                else:
                    self.children_by_object[obj.parent.name] = [obj]



class ImportAnnoCfg(Operator, ImportHelper):
    """Parses Anno (1800) .cfg files and automatically imports and positions all models, props, particles and decals in the scene. Can also import .prp files into your scene, but you must select a parent object"""
    bl_idname = "import.anno_cfg_files" 
    bl_label = "Import Anno .cfg Files"

    # ImportHelper mixin class uses this
    filename_ext = ".cfg"

    filter_glob: StringProperty( #type:  ignore
        default="*.cfg",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    also_import_ifo: BoolProperty( #type:  ignore
        name="Import .ifo",
        description="Also import the .ifo file with the same name.",
        default=True,
    )
    also_import_cf7: BoolProperty( #type:  ignore
        name="Import Feedback",
        description="Also import the .cf7/.xml file with the same name.",
        default=True,
    )
    import_feedback_type: EnumProperty( #type: ignore
        name="Feedback Type",
        description="Either cf7 or simple anno feedback encoding.",
        items = [("cf7", "cf7", ".cf7"), ("safe", "Simple Anno Feedback", "Stored in a .xml file.")],
        default="cf7",
    )

    import_as_subfile: BoolProperty( #type:  ignore
        name="Import .cfg as Subfile",
        description="Adds the file as a FILE_ object under the selected MAIN_FILE object. Note: Some .cfgs require specific sequences in the main files ifo in order to show up in game properly.",
        default=False,
    )

    def execute(self, context):
        self.path = Path(self.filepath)
        if self.import_as_subfile:
            return self.import_subfile(context)
        
        if not self.path.suffix == ".cfg" or not self.path.exists():
            self.report({'ERROR_INVALID_INPUT'}, f"Invalid file or extension")
            return {'CANCELLED'}
        
        file_obj = self.import_cfg_file(self.path, "MAIN_FILE_" + self.path.name)
        
        if self.also_import_ifo:
            self.import_ifo_file(self.path.with_suffix(".ifo"), file_obj)
            
        if self.also_import_cf7:
            if self.import_feedback_type == "safe" and self.path.with_suffix(".xml").exists():
                self.import_safe_file(self.path.with_suffix(".xml"), file_obj)
            else:
                self.import_cf7_file(self.path.with_suffix(".cf7"), file_obj)

        self.report({'INFO'}, "Import completed! Version 2.0")
        return {'FINISHED'}
    
    def import_subfile(self, context):
        parent = context.active_object
        if not parent or not get_anno_object_class(parent) == MainFile:
            self.report({'ERROR_INVALID_CONTEXT'}, f"MAIN_FILE_ Object needs to be selected.")
            return {'CANCELLED'}
        file_name = to_data_path(self.path).as_posix()
        node = ET.fromstring(f"""
            <Config>
                <FileName>{file_name}</FileName>
                <AdaptTerrainHeight>1</AdaptTerrainHeight>
                <ConfigType>FILE</ConfigType>
                <Transformer>
                    <Config>
                    <ConfigType>ORIENTATION_TRANSFORM</ConfigType>
                    <Conditions>0</Conditions>
                    </Config>
                </Transformer>
            </Config>
        """)
        blender_obj = SubFile.xml_to_blender(node, parent)
        return {'FINISHED'}
    
    def import_ifo_object(self, node, parent_object):
        name = node.tag + "_" + self.get_text(node, "Name", "IFO")
        if node.tag in ifo_cube_objects():
            self.import_ifo_cube(name, node, parent_object)
        elif node.tag in ifo_plane_objects():
            self.import_ifo_plane(name, node, parent_object)
        elif node.tag in ifo_empty_objects():
            self.import_ifo_empty(name, node, parent_object)
    
    def import_ifo_file(self, fullpath, file_obj): 
        if not fullpath.exists():
            self.report({'INFO'}, f"Missing file {fullpath}")
            return
        tree = ET.parse(fullpath)
        root = tree.getroot()
        
        ifo_obj = IfoFile.xml_to_blender(root, file_obj)
        ifo_obj.name = "IFOFILE"

        return
    
    def import_cf7_file(self, fullpath, file_obj): 
        if not fullpath.exists() and not fullpath.with_suffix(".fc").exists():
            self.report({'INFO'}, f"Missing file: {fullpath.with_suffix('.fc')}")
            return
        if not fullpath.exists() and fullpath.with_suffix(".fc").exists() and IO_AnnocfgPreferences.get_path_to_fc_converter().exists():
            subprocess.call(f"\"{IO_AnnocfgPreferences.get_path_to_fc_converter()}\" -r \"{fullpath.with_suffix('.fc')}\" -o \"{fullpath}\"")
        if not fullpath.exists():
            self.report({'INFO'}, f"Missing file: {fullpath}")
            return
        root = None
        with open(fullpath) as f:
            xml = '<cf7_imaginary_root>' + f.read() + '</cf7_imaginary_root>'
            root = ET.fromstring(xml)
        tree = ET.ElementTree(root)
        cf7_object = Cf7File.xml_to_blender(root, file_obj)
        cf7_object.name = "CF7FILE"

        return

    def import_safe_file(self, fullpath, file_obj): 
        if not fullpath.exists():
            self.report({'INFO'}, f"Missing file: {fullpath}")
            return
        print("importing safexml")
        tree = ET.parse(fullpath)
        root = tree.getroot()
        safe_object = SimpleAnnoFeedbackEncodingObject.xml_to_blender(root, file_obj)
        safe_object.name = "SimpleAnnoFeedbackEncoding"
        return

    def import_cfg_file(self, absolute_path, name): 
        if not absolute_path.exists():
            self.report({'INFO'}, f"Missing file: {absolute_path}")
            return
        tree = ET.parse(absolute_path)
        root = tree.getroot()
        if root is None:
            return
        
        file_obj = MainFile.xml_to_blender(root)
        file_obj.name = name
        
        return file_obj



class ImportAnnoModelOperator(Operator, ImportHelper):
    """Imports the selected .glb/.rdm file as MODEL_."""
    bl_idname = "import.anno_model_files" 
    bl_label = "Import Anno Model (.glb, .rmd)"
    
    filename_ext = ".glb;.rdm"
    filter_glob: StringProperty( #type: ignore
        default="*.rdm;*.glb",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        self.obj = context.active_object
        if not self.obj or not get_anno_object_class(self.obj) == MainFile:
            self.report({'ERROR_INVALID_CONTEXT'}, f"MAIN_FILE_ Object needs to be selected.")
            return {'CANCELLED'}
        
        self.path = Path(self.filepath)
        
        import_helpers = {
            ".rdm": lambda: self.import_rdm(),
            ".glb": lambda: self.import_glb(),
        }
        
        if not self.path.suffix in import_helpers.keys():
            self.report({'ERROR_INVALID_INPUT'}, f"Invalid extension")
            return {'CANCELLED'}
        
        import_helpers[self.path.suffix]()
        
        self.report({'INFO'}, f'Imported {self.obj.name} from {self.filepath}')
        return {'FINISHED'}
    
    def import_rdm(self):
        self.import_glb()  
        
    def import_glb(self):
        data_path = to_data_path(self.path)
        node = ET.fromstring(f"""
            <Config>
                <FileName>{data_path.with_suffix(".rdm").as_posix()}</FileName>
                <Name>MODEL_{self.path.stem}</Name>
                <ConfigType>MODEL</ConfigType>
            </Config>                  
        """)
        blender_obj = Model.xml_to_blender(node, self.obj)
    @classmethod
    def poll(cls, context):
        if not context.active_object:
            return False
        return get_anno_object_class(context.active_object) == MainFile


class ImportAnnoPropOperator(Operator, ImportHelper):
    """Imports the selected .prp file as PROP."""
    bl_idname = "import.anno_prp_files" 
    bl_label = "Import Anno Prop (.prp)"
    
    filename_ext = ".prp"
    filter_glob: StringProperty( #type: ignore
        default="*.prp",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        self.obj = context.active_object
        if not self.obj or not get_anno_object_class(self.obj) == Propcontainer:
            self.report({'ERROR_INVALID_CONTEXT'}, f"PropContainer Object needs to be selected.")
            return {'CANCELLED'}
        
        self.path = Path(self.filepath)
        data_path = to_data_path(self.path).as_posix()
        node = ET.fromstring(f"""
            <Config>
                <ConfigType>PROP</ConfigType>
                <FileName>{data_path}</FileName>
                <Name>PROP_{self.path.stem}</Name>
                <Flags>1</Flags>
            </Config>                  
        """)
        blender_obj = Prop.xml_to_blender(node, self.obj)
        
        self.report({'INFO'}, f'Imported {self.obj.name} from {self.filepath}')
        return {'FINISHED'}

    @classmethod
    def poll(cls, context):
        if not context.active_object:
            return False
        return get_anno_object_class(context.active_object) == Propcontainer


class ExportAnnoModelOperator(Operator, ExportHelper):
    """Exports the selected MODEL as .glb/.rdm. Takes care of applying loc, rot, sca and mirroring the object along the x axis."""
    bl_idname = "export.anno_model_files" 
    bl_label = "Export Anno Model (.glb, .rmd)"
    
    filename_ext = ".rdm"
    check_extension = False
    filter_glob: StringProperty( #type: ignore
        default="*.rdm;*.glb",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )
    vertex_format: EnumProperty( #type: ignore
        default="P4h_N4b_G4b_B4b_T2h",
        items = [
            ("P4h_N4b_G4b_B4b_T2h", "P4h_N4b_G4b_B4b_T2h", "This is probably the right setting."),
            ("P4h_N4b_G4b_B4b_T2h_I4b ", "P4h_N4b_G4b_B4b_T2h_I4b ", ""),
            ("P4h_N4b_G4b_B4b_T2h_I4b_W4b", "P4h_N4b_G4b_B4b_T2h_I4b_W4b", ""),
        ],
        name = "Vertex Format"
    )

    def execute(self, context):
        self.obj = context.active_object
        if not self.obj or not get_anno_object_class(self.obj) == Model:
            self.report({'ERROR_INVALID_CONTEXT'}, f"MODEL_ Object needs to be selected.")
            return {'CANCELLED'}
 
        self.path = Path(self.filepath)
        
        export_helpers = {
            ".rdm": lambda: self.export_wrapper(lambda: self.export_rdm()),
            ".glb": lambda: self.export_wrapper(lambda: self.export_glb()),
        }
        
        if not self.path.suffix in export_helpers.keys():
            self.report({'ERROR_INVALID_INPUT'}, f"Invalid extension.")
            return {'CANCELLED'}
        
        export_helpers[self.path.suffix]()
        try:
            data_path = to_data_path(self.path)
            self.obj.dynamic_properties.set("FileName", data_path.as_posix(), replace = True)
        except ValueError:
            self.report({'INFO'}, f'Warning, export not relative to rda folder, could not adapt FileName')
            pass
        self.report({'INFO'}, f'Exported {self.obj.name} to {self.filepath}')
        return {'FINISHED'}
    
    def export_rdm(self):
        self.export_glb(self.path.with_suffix(".glb"))
        
        rdm4_path = IO_AnnocfgPreferences.get_path_to_rdm4()
        if rdm4_path.exists() and self.path.with_suffix(".glb").exists():
            #Delete the old .rdm file first
            if self.path.exists():
                self.path.unlink()
            print(f"Subprocess: \"{rdm4_path}\" --gltf={self.vertex_format} --input \"{self.path.with_suffix('.glb')}\" -n --outdst \"{self.path.parent}\"")
            subprocess.call(f"\"{rdm4_path}\" --gltf={self.vertex_format} --input \"{self.path.with_suffix('.glb')}\" -n --outdst \"{self.path.parent}\"", shell = True)
    
    def export_glb(self, filepath = None):
        if filepath is None:
            filepath = self.filepath
        bpy.ops.export_scene.gltf(filepath=str(filepath), use_selection = True, check_existing=True, export_format='GLB', export_tangents=True)
    
    def export_wrapper(self, export_function):
        """Applies loc rot sca, mirrors the object, removes the parent, executes the export function and restores the previous state

        Args:
            export_function ([type]): Function to be called.
        """
        parent = self.obj.parent
        self.obj.parent = None
        
        matrix = self.obj.matrix_world.copy()
        for vert in self.obj.data.vertices:
            vert.co = matrix @ vert.co
        self.obj.matrix_world.identity()
        
        Transform().mirror_mesh(self.obj)
        
        self.obj = bpy.context.active_object
        for other_object in bpy.context.selected_objects:
            if other_object != self.obj:
                other_object.select_set(False)
        
        export_function()
        
        Transform().mirror_mesh(self.obj)
    
        inverse = matrix.copy()
        inverse.invert()
        for vert in self.obj.data.vertices:
            vert.co = inverse @ vert.co
        self.obj.matrix_world = matrix
        
        self.obj.parent = parent
        
    @classmethod
    def poll(cls, context):
        if not context.active_object:
            return False
        return get_anno_object_class(context.active_object) == Model
    
    def invoke(self, context, _event):
        import os
        if not self.filepath and context.active_object is not None:
            path = data_path_to_absolute_path(context.active_object.dynamic_properties.get_string("FileName"))
            self.filepath = str(path)
            
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        return super().invoke(context, _event)
            

class OBJECT_OT_add_anno_object(Operator, AddObjectHelper):
    """Create a new Anno Feedback Object"""
    bl_idname = "mesh.add_anno_object"
    bl_label = "Add Anno Feedback Object"
    bl_options = {'REGISTER', 'UNDO'}
    object_type: EnumProperty(
        name='Type',
        description='Object Type',
        items={
            ('DummyGroup', 'DummyGroup', ''),
            ('FeedbackConfig', 'FeedbackConfig', ''),
            ('Dummy', 'Dummy', ''),
            ('SimpleAnnoFeedbackEncoding', 'SimpleAnnoFeedbackEncoding', '')},
            default='Dummy')
    
    
    anno_object_by_enum = {
            "Dummy": Dummy,
            "DummyGroup": DummyGroup,
            "FeedbackConfig": FeedbackConfig,
            "SimpleAnnoFeedbackEncoding": SimpleAnnoFeedbackEncodingObject,
        }
    
    def __init__(self):
        self.filename = ""
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "object_type")
    
    def execute(self, context):
        self.parent = context.active_object
        
        anno_object = self.anno_object_by_enum[self.object_type]
        obj = anno_object.from_default()
        # obj.name = obj.name.split("_")[1] + self.object_type
        if self.parent:
            obj.parent = self.parent

        return {'FINISHED'}

classes = (
    ExportAnnoCfg,
    ImportAnnoCfg,
    ExportAnnoModelOperator,
    ImportAnnoModelOperator,
    ImportAnnoPropOperator,
    OBJECT_OT_add_anno_object,
)

def add_anno_object_button(self, context):
    self.layout.operator(
        OBJECT_OT_add_anno_object.bl_idname,
        text="Add Anno Feedback Object",
        icon='PLUGIN')


def menu_func_import(self, context):
    self.layout.operator(ImportAnnoCfg.bl_idname, text="Anno (.cfg)")

def menu_func_export_cfg(self, context):
    self.layout.operator(ExportAnnoCfg.bl_idname, text="Anno (.cfg)")
    
def menu_func_export_model(self, context):
    self.layout.operator(ExportAnnoModelOperator.bl_idname, text="Anno Model (.rdm/.glb)")
    
def menu_func_import_model(self, context):
    self.layout.operator(ImportAnnoModelOperator.bl_idname, text="Anno Model (.rdm/.glb)")
def menu_func_import_prop(self, context):
    self.layout.operator(ImportAnnoPropOperator.bl_idname, text="Anno Prop (.prp)")



import_funcs = [
    menu_func_import,
    menu_func_import_model,
    menu_func_import_prop,
]
export_funcs = [
    menu_func_export_cfg,
    menu_func_export_model,
]

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    for func in import_funcs:
        bpy.types.TOPBAR_MT_file_import.append(func)
    for func in export_funcs:
        bpy.types.TOPBAR_MT_file_export.append(func)

    bpy.types.VIEW3D_MT_mesh_add.append(add_anno_object_button)

def unregister():
    from bpy.utils import unregister_class
    for cls in classes:
        unregister_class(cls)
    for func in import_funcs:
        bpy.types.TOPBAR_MT_file_import.remove(func)
    for func in export_funcs:
        bpy.types.TOPBAR_MT_file_export.remove(func)
        
    bpy.types.VIEW3D_MT_mesh_add.remove(add_anno_object_button)
