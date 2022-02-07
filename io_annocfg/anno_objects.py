
from __future__ import annotations
import bpy
from bpy.types import Object as BlenderObject
import xml.etree.ElementTree as ET
import os
import re
import subprocess
from pathlib import Path
from typing import Tuple, List, NewType, Any, Union, Dict, Optional, TypeVar, Type
from abc import ABC, abstractmethod
from bpy.props import EnumProperty, BoolProperty, PointerProperty, IntProperty, FloatProperty, CollectionProperty, StringProperty, FloatVectorProperty
from bpy.types import PropertyGroup, Panel, Operator, UIList
import bmesh
import sys
def str_to_class(classname):
    return getattr(sys.modules[__name__], classname)


from .prefs import IO_AnnocfgPreferences
from .utils import data_path_to_absolute_path, to_data_path
from .feedback_ui import FeedbackConfigItem, GUIDVariationListItem, FeedbackSequenceListItem
from . import feedback_enums

def parse_float_node(node, query, default_value = 0.0):
    value = default_value
    if node.find(query) is not None:
        value = float(node.find(query).text)
    return value

def get_float(node, query, default_value = 0.0):
    value = default_value
    if node.find(query) is not None:
        value = float(node.find(query).text)
    return value



class Transform:
    """
    Parses an xml tree node for transform operations, stores them and can apply them to a blender object.
    """
    def __init__(self, loc = [0,0,0], rot = [1,0,0,0], sca = [1,1,1], anno_coords = True):
        self.location = loc
        self.rotation = rot
        self.rotation_euler = [0,0,0]
        self.euler_rotation = False
        self.scale = sca
        self.anno_coords = anno_coords
        
    def get_component_value(self, component_name: str) -> float:
        component_by_name = {
            "location.x": self.location[0],
            "location.y": self.location[1],
            "location.z": self.location[2],
            
            "rotation.w": self.rotation[0],
            "rotation.x": self.rotation[1],
            "rotation.y": self.rotation[2],
            "rotation.z": self.rotation[3],
            
            "rotation_euler.x": self.rotation_euler[0],
            "rotation_euler.y": self.rotation_euler[1],
            "rotation_euler.z": self.rotation_euler[2],
            
            "scale.x": self.scale[0],
            "scale.y": self.scale[1],
            "scale.z": self.scale[2],
        }
        return component_by_name[component_name]
        
    def get_component_from_node(self, node: ET.Element, transform_paths: Dict[str, str], component: str, default = 0.0) -> float:
        query = transform_paths.get(component, None)
        if not query:
            return default
        value = float(get_text_and_delete(node, query, str(default)))
        return value
        
    @classmethod
    def from_node(cls, node: ET.Element, transform_paths, enforce_equal_scale: bool, euler_rotation: bool = False) -> Transform:
        instance = cls()
        instance.location[0] = instance.get_component_from_node(node, transform_paths, "location.x")
        instance.location[1] = instance.get_component_from_node(node, transform_paths, "location.y")
        instance.location[2] = instance.get_component_from_node(node, transform_paths, "location.z")
        
        instance.scale[0] = instance.get_component_from_node(node, transform_paths, "scale.x", 1.0)
        instance.scale[1] = instance.get_component_from_node(node, transform_paths, "scale.y", 1.0)
        instance.scale[2] = instance.get_component_from_node(node, transform_paths, "scale.z", 1.0)
        if enforce_equal_scale:
            instance.scale[1] = instance.scale[0]
            instance.scale[2] = instance.scale[1]
        
        if not euler_rotation:        
            instance.rotation[0] = instance.get_component_from_node(node, transform_paths, "rotation.w", 1.0)
            instance.rotation[1] = instance.get_component_from_node(node, transform_paths, "rotation.x")
            instance.rotation[2] = instance.get_component_from_node(node, transform_paths, "rotation.y")
            instance.rotation[3] = instance.get_component_from_node(node, transform_paths, "rotation.z")
        else:
            instance.rotation_euler[0] = instance.get_component_from_node(node, transform_paths, "rotation_euler.x")
            instance.rotation_euler[1] = instance.get_component_from_node(node, transform_paths, "rotation_euler.y")
            instance.rotation_euler[2] = instance.get_component_from_node(node, transform_paths, "rotation_euler.z")
            instance.euler_rotation = True
            
        instance.anno_coords = True
        return instance
        
    @classmethod
    def from_blender_object(cls, obj, enforce_equal_scale: bool, euler_rotation: bool = False) -> Transform:
        if enforce_equal_scale:
            if len(set([obj.scale[0], obj.scale[1], obj.scale[2]])) > 1:
                print(obj.name, "Cannot have different scale values on xyz")
        instance = cls(obj.location, [1,0,0,0], obj.scale, False)
        if not euler_rotation:
            obj.rotation_mode = "QUATERNION"
            instance.rotation = list(obj.rotation_quaternion)
            return instance
        obj.rotation_mode = "XYZ"
        instance.rotation_euler = [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z]
        return instance
    
    def convert_to_blender_coords(self):
        if not self.anno_coords:
            return
        self.location = (-self.location[0], -self.location[2], self.location[1])
        self.rotation = (self.rotation[0], self.rotation[1], self.rotation[3], -self.rotation[2])
        self.rotation_euler = (self.rotation_euler[0], self.rotation_euler[2], self.rotation_euler[1])
        self.scale = (self.scale[0], self.scale[2], self.scale[1])
        self.anno_coords = False

    def convert_to_anno_coords(self):
        if self.anno_coords:
            return
        self.location = (-self.location[0], self.location[2], -self.location[1])
        self.rotation = (self.rotation[0], self.rotation[1], -self.rotation[3], self.rotation[2])
        self.rotation_euler = (self.rotation_euler[0], self.rotation_euler[2], self.rotation_euler[1])
        self.scale = (self.scale[0], self.scale[2], self.scale[1])
        self.anno_coords
    
    def mirror_mesh(self, object):
        if not object.data or not hasattr(object.data, "vertices"):
            return
        for v in object.data.vertices:
            v.co.x *= -1.0
            
        #Inverting normals for import AND Export they are wrong because of scaling on the x axis.
        #Warn people that this will break exports from .blend files made with an earlier version!!!
        mesh = object.data
        bm = bmesh.new()
        bm.from_mesh(mesh) # load bmesh
        for f in bm.faces:
             f.normal_flip()
        bm.normal_update() # not sure if req'd
        bm.to_mesh(mesh)
        mesh.update()
        bm.clear() #.. clear before load next
    
    def apply_to(self, object):
        if self.anno_coords:
            self.convert_to_blender_coords()
        self.mirror_mesh(object)
        object.location = self.location
        if not self.euler_rotation:
            object.rotation_mode = "QUATERNION"
            object.rotation_quaternion = self.rotation
        else:
            object.rotation_mode = "XYZ"
            object.rotation_euler = self.rotation_euler
        object.scale = self.scale

class BoolPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeBool")
    value : BoolProperty(name = "", default = False)

class FeedbackSequencePropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeSequence")
    value : EnumProperty(
        name='',
        description='Animation Sequence',
        items= feedback_enums.animation_sequences,
        default='idle01'
    )

class IntPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeInt")
    value : IntProperty(name = "", default = 0)
class StringPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeString")
    value : StringProperty(name = "", default = "")

class FilenamePropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeString")
    value : StringProperty(name = "", default = "", subtype = "FILE_PATH")
class FloatPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeFloat")
    value : FloatProperty(name = "", default = 0.0)
    
class ColorPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "SomeFloat")
    value : FloatVectorProperty(name = "", default = [0.0, 0.0, 0.0], subtype = "COLOR", min= 0.0, max = 1.0)

class Converter(ABC):
    @classmethod
    @abstractmethod
    def data_type(cls):
        pass
    @classmethod
    def from_string(cls, s):
        """Convert the string s from the input xml node into a blender representation of type data_type()

        Args:
            s (str): xml_node.text

        Returns:
            data_type(): Blender representation
        """
        value = cls.data_type()
        try:
            value = cls.data_type()(s)
        except:
            print(f"Error: failed to convert {s} to {cls.data_type()}")
        return cls.data_type()(s)
    @classmethod
    def to_string(cls, value):
        """Convert the blender representation value into a string for the xml node.
        Args:
            value (daty_type()): Blender representation

        Returns:
            str: XML text string
        """  
        return str(value)

class StringConverter(Converter):
    @classmethod
    def data_type(cls):
        return str

class BoolConverter(Converter):
    @classmethod
    def data_type(cls):
        return bool
    @classmethod
    def from_string(cls, s):
        return bool(int(s))
    @classmethod
    def to_string(cls, value):
        return str(int(value))
        
class IntConverter(Converter):
    @classmethod
    def data_type(cls):
        return int

class FloatConverter(Converter):
    @classmethod
    def data_type(cls):
        return float
    @classmethod
    def to_string(cls, value):
        return format_float(value)
class FeedbackSequenceConverter(Converter):
    @classmethod
    def data_type(cls):
        return string
    @classmethod
    def from_string(cls, s): 
        seq_id = int(s)
        return feedback_enums.NAME_BY_SEQUENCE_ID.get(seq_id, "none")
    @classmethod
    def to_string(cls, value): 
        seq_id = feedback_enums.SEQUENCE_ID_BY_NAME.get(value, -1)
        return str(seq_id)

class ColorConverter(Converter):
    @classmethod
    def data_type(cls):
        return str
    @classmethod
    def from_string(cls, s): #f.e. COLOR[1.0, 0.5, 0.3]
        values = s.replace(" ", "").replace("_COLOR[", "").replace("]", "").split(",")
        assert len(values) == 3
        return [format_float(value) for value in values]
    @classmethod
    def to_string(cls, value): #f.e. [1.0, 0.5, 0.3]
        assert len(value) == 3
        return f"_COLOR[{', '.join([str(val) for val in value])}]"

converter_by_tag = {
    "ConfigType": StringConverter,
    "FileName" : StringConverter,
    "Name" : StringConverter,
    "AdaptTerrainHeight" : BoolConverter,
    "HeightAdaptationMode" : BoolConverter,
    "DIFFUSE_ENABLED" : BoolConverter,
    "NORMAL_ENABLED" : BoolConverter,
    "METALLIC_TEX_ENABLED" : BoolConverter,
    "SEPARATE_AO_TEXTURE" : BoolConverter, 
    "HEIGHT_MAP_ENABLED" : BoolConverter,
    "NIGHT_GLOW_ENABLED" : BoolConverter,
    "DYE_MASK_ENABLED" : BoolConverter,
    "cUseTerrainTinting" : BoolConverter,
    "SELF_SHADOWING_ENABLED" : BoolConverter, 
    "WATER_CUTOUT_ENABLED" : BoolConverter,
    "ADJUST_TO_TERRAIN_HEIGHT" : BoolConverter, 
    "GLOW_ENABLED": BoolConverter,
    "SequenceID": FeedbackSequenceConverter,
    "m_IdleSequenceID": FeedbackSequenceConverter,
}

def get_converter_for(tag, value_string):
    if tag in converter_by_tag:
        return converter_by_tag[tag]
    if value_string.startswith("_COLOR["):
        return ColorConverter
    if value_string.isnumeric():
        return IntConverter
    if is_type(float, value_string):
        return FloatConverter

    #TODO: CDATA Converter, mIdleSequenceConverter, etc
    return StringConverter

class XMLPropertyGroup(PropertyGroup):
    tag : StringProperty(name = "", default = "")
    
    config_type : StringProperty(name = "", default = "")
    
    feedback_sequence_properties : CollectionProperty(name = "FeedbackSequences", type = FeedbackSequencePropertyGroup)
    boolean_properties : CollectionProperty(name = "Bools", type = BoolPropertyGroup)
    filename_properties : CollectionProperty(name = "Filenames", type = FilenamePropertyGroup)
    string_properties : CollectionProperty(name = "Strings", type = StringPropertyGroup)
    int_properties : CollectionProperty(name = "Ints", type = IntPropertyGroup)
    float_properties : CollectionProperty(name = "Floats", type = FloatPropertyGroup)
    color_properties : CollectionProperty(name = "Colors", type = ColorPropertyGroup)
    dynamic_properties : CollectionProperty(name = "DynamicProperties", type = XMLPropertyGroup)
    
    
    hidden : BoolProperty(name = "Hide", default = False)
    
    def get_string(self, tag, default = None):
        for item in self.string_properties:
            if item.tag == tag:
                return item.value
        for item in self.filename_properties:
            if item.tag == tag:
                return item.value
        return default
    def set(self, tag, value_string, replace = False):
        converter = get_converter_for(tag, value_string)
        value = converter.from_string(value_string)
        
        # Special fields
        if tag == "ConfigType":
            self.config_type = value
            return
            
        properties_by_converter = {
            BoolConverter: self.boolean_properties,
            StringConverter: self.string_properties,
            IntConverter: self.int_properties,
            FloatConverter: self.float_properties,
            ColorConverter: self.color_properties,
            FeedbackSequenceConverter: self.feedback_sequence_properties,
        }
        
        properties = properties_by_converter[converter]
        if tag == "FileName":
            properties = self.filename_properties
        if replace:
            for item in properties:
                if item.tag == tag:
                    item.value = value
                    return
        properties.add()
        properties[-1].tag = tag
        properties[-1].value = value
        
    def from_node(self, node):
        self.tag = node.tag
        for child_node in list(node):
            if len(list(child_node)) == 0:
                value = child_node.text
                if value is None:
                    value = ""
                self.set(child_node.tag, value)
            else:
                self.dynamic_properties.add()
                self.dynamic_properties[-1].from_node(child_node)
        return self

    def to_node(self, target_node):
        target_node.tag = self.tag
        if self.config_type:
            find_or_create(target_node, "ConfigType").text = self.config_type
        for property_group, converter in [
                            (self.feedback_sequence_properties, FeedbackSequenceConverter),
                            (self.string_properties, StringConverter),
                            (self.int_properties, IntConverter),
                            (self.filename_properties, StringConverter),
                            (self.float_properties, FloatConverter),
                            (self.boolean_properties, BoolConverter),
                        ]:
            for prop in property_group:
                value_string = converter.to_string(prop.value)
                #It is better to always create a new subelement - otherwise there can only be one of each tag.
                #Or does this create any problems?
                #find_or_create(target_node, prop.tag).text = value_string
                ET.SubElement(target_node, prop.tag).text = value_string
        for dyn_prop in self.dynamic_properties:
            subnode = ET.SubElement(target_node, dyn_prop.tag)
            dyn_prop.to_node(subnode)
        return target_node
    
    def draw(self, layout, split_ratio = 0.3):
        col = layout.column()
        header = col.row()
        split = header.split(factor=0.8)
        split.label(text = f"{self.tag}: {self.config_type}")
        split.prop(self, "hidden")
        if self.hidden:
            return
        col.separator(factor = 1.0)
        for kw_properties in [self.feedback_sequence_properties, self.filename_properties,self.boolean_properties,
                              self.int_properties, self.float_properties, self.string_properties, self.color_properties]:
            for item in kw_properties:
                row = col.row()
                split = row.split(factor=split_ratio)
                split.alignment = "RIGHT"
                split.label(text = item.tag)
                split.prop(item, "value")
        
        for item in self.dynamic_properties:
            box = col.box()
            item.draw(box, split_ratio)
    

class PT_AnnoScenePropertyPanel(Panel):
    bl_label = "Anno Scene"
    bl_idname = "VIEW_3D_PT_AnnoScene"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Anno Object' 
    #bl_context = "object"
    
    @classmethod
    def poll(cls, context):
        return True
            
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        
        col.prop(context.scene, "anno_mod_folder")

class ConvertCf7DummyToDummy(Operator):
    bl_idname = "object.convertcf7dummy"
    bl_label = "Convert to SAFE Dummy"

    def execute(self, context):
        obj = context.active_object
        obj.anno_object_class_str = obj.anno_object_class_str.replace("Cf7", "")
        obj.name = obj.name.replace("Cf7", "")
        return {'FINISHED'}

class PT_AnnoObjectPropertyPanel(Panel):
    bl_label = "Anno Object"
    bl_idname = "VIEW_3D_PT_AnnoObject"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Anno Object' 
    #bl_context = "object"
    
    @classmethod
    def poll(cls, context):
        return True
            
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        if not obj:
            return
        col = layout.column()
        row = col.row()
        
        row.prop(obj, "anno_object_class_str")
        row.enabled = False
        if "Cf7" in obj.anno_object_class_str:
            col.operator(ConvertCf7DummyToDummy.bl_idname, text = "Convert to SimpleAnnoFeedback")
        dyn = obj.dynamic_properties
        dyn.draw(col)

class PT_AnnoMaterialObjectPropertyPanel(Panel):
    bl_label = "Anno Material"
    bl_idname = "WINDOW_PT_AnnoMaterialObject"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_category = 'Anno Material' 
    bl_context = "material"
        
    def draw(self, context):
            layout = self.layout
            obj = context.active_object.active_material
 
            if not obj:
                return
            col = layout.column()
            dyn = obj.dynamic_properties
            dyn.draw(col, 0.5)
class AnnoImageTextureProperties(PropertyGroup):
    enabled : BoolProperty( #type: ignore
            name='Enabled',
            description='',
            default=True)
    original_file_extension: EnumProperty( #type: ignore
            name='Extension',
            description='Some textures are stored as .png (for example default masks). Use .psd for your own textures (saved as .dds).',
            items = [
                (".psd", ".psd", ".psd or .dds"),
                (".png", ".png", ".psd or .dds"),
            ],
            default='.psd'
            )        

class PT_AnnoImageTexture(Panel):
    bl_label = "Anno Texture"
    bl_idname = "SCENE_PT_AnnoTexture"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Anno Texture' 
    #bl_context = "object"
    
    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.tree_type == 'ShaderNodeTree' and type(context.active_node) == bpy.types.ShaderNodeTexImage)

    def draw(self, context):
        layout = self.layout
        node = context.active_node.anno_properties
        col = layout.column()
        col.prop(node, "enabled")
        col.prop(node, "original_file_extension")

class Material:
    """
    Can be created from an xml material node. Stores with diffuse, normal and metal texture paths and can create a corresponding blender material from them.
    Uses a cache to avoid creating the exact same blender material multiple times when loading just one .cfg 
    """
    
    texture_definitions = {
        "cModelDiffTex":"DIFFUSE_ENABLED",
        "cModelNormalTex":"NORMAL_ENABLED",
        "cModelMetallicTex":"METALLIC_TEX_ENABLED",
        "cSeparateAOTex":"SEPARATE_AO_TEXTURE",
        "cHeightMap":"HEIGHT_MAP_ENABLED",
        "cNightGlowMap":"NIGHT_GLOW_ENABLED", 
        "cDyeMask":"DYE_MASK_ENABLED"
    }
    texture_names = {
        "diffuse":"cModelDiffTex",
        "normal":"cModelNormalTex",
        "metallic":"cModelMetallicTex",
        "ambient":"cSeparateAOTex",
        "height":"cHeightMap",
        "night_glow":"cNightGlowMap",
        "dye":"cDyeMask",
    }
    # color_definitions = {
    #     "cDiffuseColor":("cDiffuseColor.r", "cDiffuseColor.g", "cDiffuseColor.b"),
    #     "cEmissiveColor":("cEmissiveColor.r", "cEmissiveColor.g", "cEmissiveColor.b"),
    # }         "":"",
    

    color_definitions = ["cDiffuseColor", "cEmissiveColor"]
    custom_property_default_value = {
        "ShaderID":"", "VertexFormat":"", "NumBonesPerVertex":"", "cUseTerrainTinting":"", "Common":"", \
        "cTexScrollSpeed":"", "cParallaxScale":"", "PARALLAX_MAPPING_ENABLED":"", \
        "SELF_SHADOWING_ENABLED":"", "WATER_CUTOUT_ENABLED":"", "TerrainAdaption":"", "ADJUST_TO_TERRAIN_HEIGHT":"", "VERTEX_COLORED_TERRAIN_ADAPTION":"", \
        "ABSOLUTE_TERRAIN_ADAPTION":"", "Environment":"", "cUseLocalEnvironmentBox":"", "cEnvironmentBoundingBox.x":"", "cEnvironmentBoundingBox.y":"", "cEnvironmentBoundingBox.z":"", \
        "cEnvironmentBoundingBox.w":"", "Glow":"", "GLOW_ENABLED":"", \
        "WindRipples":"", "WIND_RIPPLES_ENABLED":"", "cWindRippleTex":"", "cWindRippleTiling":"", "cWindRippleSpeed":"", "cWindRippleNormalIntensity":"", \
        "cWindRippleMeshIntensity":"", "DisableReviveDistance":"", "cGlossinessFactor":"", "cOpacity":"",
    }
    materialCache: Dict[Tuple[Any,...], Material] = {}

    def __init__(self):
        self.textures: Dict[str, str] = {}
        self.texture_enabled: Dict[str, bool] = {}
        self.colors: Dict[str, List[float]] = {}
        self.custom_properties: Dict[str, Any] = {}
        self.name: str = "Unnamed Material"
        self.node = None
    @classmethod
    def from_material_node(cls, material_node: ET.Element) -> Material:
        instance = cls()
        instance.name = get_text_and_delete(material_node, "Name", "Unnamed Material")
        for texture_name, texture_enabled_flag in cls.texture_definitions.items():
            texture_path = get_text_and_delete(material_node, texture_name)
            instance.textures[texture_name] = texture_path
            instance.texture_enabled[texture_name] = bool(int(get_text(material_node, texture_enabled_flag, "0")))
        for color_name in cls.color_definitions:
            color = [1.0, 1.0, 1.0]
            color[0] = float(get_text_and_delete(material_node, color_name + ".r", 1.0))
            color[1] = float(get_text_and_delete(material_node, color_name + ".g", 1.0))
            color[2] = float(get_text_and_delete(material_node, color_name + ".b", 1.0))
            instance.colors[color_name] = color
        #for prop, default_value in cls.custom_property_default_value.items():
            #value = string_to_fitting_type(get_text(material_node, prop, default_value))
            #if value is not None:
            #    instance.custom_properties[prop] = value
        instance.node = material_node
        return instance
    
    @classmethod
    def from_filepaths(cls, name: str, diff_path: str, norm_path: str, metal_path: str) -> Material:
        element = ET.fromstring(f"""
            <Config>
                <Name>{name}</Name>
                <cModelDiffTex>{diff_path}</cModelDiffTex>
                <cModelNormalTex>{metal_path}</cModelNormalTex>
                <cModelMetallicTex>{metal_path}</cModelMetallicTex>
            </Config>                        
        """)
        return cls.from_material_node(element)
    
    
    @classmethod
    def from_default(cls) -> Material:
        element = ET.fromstring(f"""
            <Config>
                <Name>NEW_MATERIAL<Name>
            </Config>                        
        """)
        return cls.from_material_node(element)
         
    @classmethod
    def from_blender_material(cls, blender_material) -> Material:
        instance = cls()
        instance.node = blender_material.dynamic_properties.to_node(ET.Element("Material"))
        instance.name = blender_material.name
        for texture_name in cls.texture_definitions.keys():
            shader_node = blender_material.node_tree.nodes[texture_name] #Assumes that the nodes collection allows this lookup
            if not shader_node.image:
                instance.textures[texture_name] = ""
                instance.texture_enabled[texture_name] = shader_node.anno_properties.enabled
                continue
            filepath_full = bpy.path.abspath(shader_node.image.filepath, library=shader_node.image.library)
            texture_path = to_data_path(filepath_full)
            #Rename "data/.../some_diff_0.png" to "data/.../some_diff.psd"
            extension = shader_node.anno_properties.original_file_extension
            texture_path = Path(texture_path.as_posix().replace(instance.texture_quality_suffix()+".", ".")).with_suffix(extension)
            instance.textures[texture_name] = texture_path.as_posix()
            instance.texture_enabled[texture_name] = shader_node.anno_properties.enabled
        for color_name in cls.color_definitions:
            color = [1.0, 1.0, 1.0]
            shader_node = blender_material.node_tree.nodes.get(color_name, None)
            if shader_node:
                inputs = shader_node.inputs
                color = [inputs[0].default_value, inputs[1].default_value, inputs[2].default_value]
            instance.colors[color_name] = color
        for prop, default_value in cls.custom_property_default_value.items():
            if prop not in blender_material:
                if default_value:
                    instance.custom_properties[prop] = default_value
                continue
            instance.custom_properties[prop] = blender_material[prop]
        return instance
    
    def texture_quality_suffix(self):
        return "_"+IO_AnnocfgPreferences.get_texture_quality()
    
    def to_xml_node(self, parent: ET.Element) -> ET.Element:
        node = self.node
        if not parent is None:
            parent.append(node)
        # node = ET.SubElement(parent, "Config")
        #ET.SubElement(node, "ConfigType").text = "MATERIAL"
        ET.SubElement(node, "Name").text = self.name
        for texture_name in self.texture_definitions.keys():
            texture_path = self.textures[texture_name]
            if texture_path != "":
                ET.SubElement(node, texture_name).text = texture_path
        for color_name in self.color_definitions:
            ET.SubElement(node, color_name + ".r").text = format_float(self.colors[color_name][0])
            ET.SubElement(node, color_name + ".g").text = format_float(self.colors[color_name][1])
            ET.SubElement(node, color_name + ".b").text = format_float(self.colors[color_name][2])
        for texture_name, texture_enabled_flag in self.texture_definitions.items():
            used_value = self.texture_enabled[texture_name]
            find_or_create(node, texture_enabled_flag).text = str(int(used_value))
        for prop, value in self.custom_properties.items():
            if value == "":
                continue
            if type(value) == float:
                value = format_float(value)
            ET.SubElement(node, prop).text = str(value)
        return node
    
    def convert_to_png(self, fullpath: Path) -> bool:
        """Converts the .dds file to .png. Returns True if successful, False otherwise.

        Args:
            fullpath (str): .dds file

        Returns:
            bool: Successful
        """
        if not IO_AnnocfgPreferences.get_path_to_texconv().exists():
            return False
        if not fullpath.exists():
            return False
        try:
            subprocess.call(f"\"{IO_AnnocfgPreferences.get_path_to_texconv()}\" -ft PNG -sepalpha -y -o \"{fullpath.parent}\" \"{fullpath}\"")
        except:
            return False
        return fullpath.with_suffix(".png").exists()
    
    def get_texture(self, texture_path: Path):
        """Tries to find the texture texture_path with ending "_0.png" (quality setting can be changed) in the list of loaded textures.
        Otherwise loads it. If it is not existing but the corresponding .dds exists, converts it first.

        Args:
            texture_path (str): f.e. "data/.../texture_diffuse.psd"

        Returns:
            [type]: The texture or None.
        """
        if texture_path == Path(""):
            return None
        texture_path = Path(texture_path)
        texture_path = Path(texture_path.parent, texture_path.stem + self.texture_quality_suffix()+".dds")
        png_file = texture_path.with_suffix(".png")
        image = bpy.data.images.get(str(png_file.name), None)
        if image is not None:
            return image
        fullpath = data_path_to_absolute_path(texture_path)
        png_fullpath = data_path_to_absolute_path(png_file)
        if not png_fullpath.exists():
            success = self.convert_to_png(fullpath)
            if not success:
                print("Failed to convert texture", fullpath)
                return None
        image = bpy.data.images.load(str(png_fullpath))
        return image

    

    def get_material_cache_key(self):
        attribute_list = tuple([self.name] + list(self.textures.items()) + list([(a, tuple(b)) for a, b in self.colors.items()]) + list(self.custom_properties.items()))
        return hash(attribute_list)
    
    def create_anno_shader(self):
        anno_shader = bpy.data.node_groups.new('AnnoShader', 'ShaderNodeTree')
        
        anno_shader.inputs.new("NodeSocketColor", "cDiffuse")
        anno_shader.inputs.new("NodeSocketColor", "cDiffuseMultiplier")
        anno_shader.inputs.new("NodeSocketFloat", "Alpha")
        anno_shader.inputs.new("NodeSocketColor", "cNormal")
        anno_shader.inputs.new("NodeSocketFloat", "Glossiness")
        anno_shader.inputs.new("NodeSocketColor", "cMetallic")
        anno_shader.inputs.new("NodeSocketColor", "cHeight")
        anno_shader.inputs.new("NodeSocketColor", "cNightGlow")
        anno_shader.inputs.new("NodeSocketColor", "cEmissiveColor")
        anno_shader.inputs.new("NodeSocketFloat", "EmissionStrength")
        anno_shader.inputs.new("NodeSocketColor", "cDyeMask")
        
        
        anno_shader.outputs.new("NodeSocketShader", "Shader")
        
        inputs = self.add_shader_node(anno_shader, "NodeGroupInput", 
                                        position = (0, 0), 
                                    ).outputs
        mix_c_diffuse = self.add_shader_node(anno_shader, "ShaderNodeMixRGB",
                                        position = (1, 4),
                                        default_inputs = {
                                            0 : 1.0,
                                        },
                                        inputs = {
                                            "Color1" : inputs["cDiffuseMultiplier"],
                                            "Color2" : inputs["cDiffuse"],
                                        },
                                        blend_type = "MULTIPLY",
                                    )
        dye_mask = self.add_shader_node(anno_shader, "ShaderNodeRGBToBW",
                                        position = (1, 3),
                                        inputs = {
                                            "Color" : inputs["cDyeMask"],
                                        },
                                    )
        final_diffuse = self.add_shader_node(anno_shader, "ShaderNodeMixRGB",
                                        position = (2, 3),
                                        default_inputs = {
                                            "Color2" : (1.0, 0.0, 0.0, 1.0),
                                        },
                                        inputs = {
                                            "Fac" : dye_mask.outputs["Val"],
                                            "Color1" : mix_c_diffuse.outputs["Color"],
                                        },
                                        blend_type = "MULTIPLY",
                                    )
        #Normals
        separate_normal = self.add_shader_node(anno_shader, "ShaderNodeSeparateRGB",
                                        position = (1, 2),
                                        inputs = {
                                            "Image" : inputs["cNormal"],
                                        },
                                    )
        #Calc normal blue
        square_x = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (2, 1.5),
                                        operation = "POWER",
                                        inputs = {
                                            0 : separate_normal.outputs["R"],
                                        },
                                        default_inputs = {
                                            1 : 2.0
                                        },
                                    )
        square_y = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (2, 2.5),
                                        operation = "POWER",
                                        inputs = {
                                            0 : separate_normal.outputs["G"],
                                        },
                                        default_inputs = {
                                            1 : 2.0
                                        },
                                    )
        add_squares = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (2.5, 2),
                                        operation = "ADD",
                                        inputs = {
                                            0 : square_x.outputs["Value"],
                                            1 : square_y.outputs["Value"],
                                        },
                                    )
        inverted_add_squares = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (3, 2),
                                        operation = "SUBTRACT",
                                        inputs = {
                                            1 : add_squares.outputs["Value"],
                                        },
                                        default_inputs = {
                                            0 : 1.0
                                        },
                                    )
        normal_blue = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                        position = (3.5, 2),
                                        operation = "SQRT",
                                        inputs = {
                                            0 : inverted_add_squares.outputs["Value"],
                                        },
                                    )
        
        combine_normal = self.add_shader_node(anno_shader, "ShaderNodeCombineRGB",
                                        position = (4, 2),
                                        inputs = {
                                            "R" : separate_normal.outputs["R"],
                                            "G" : separate_normal.outputs["G"],
                                            "B" : normal_blue.outputs["Value"],
                                        },
                                    )
        normal_map = self.add_shader_node(anno_shader, "ShaderNodeNormalMap",
                                        position = (5, 2),
                                        default_inputs = {
                                            0 : 0.5,
                                        },
                                        inputs = {
                                            "Color" : combine_normal.outputs["Image"],
                                        },
                                    )
        height_bw = self.add_shader_node(anno_shader, "ShaderNodeRGBToBW",
                                        position = (5, 3),
                                        inputs = {
                                            "Color" : inputs["cHeight"],
                                        },
                                    )
        bump_map = self.add_shader_node(anno_shader, "ShaderNodeBump",
                                        position = (6, 2),
                                        default_inputs = {
                                            0 : 0.5,
                                        },
                                        inputs = {
                                            "Height" : height_bw.outputs["Val"],
                                            "Normal" : normal_map.outputs["Normal"],
                                        },
                                    )
        #Roughness
        roughness = self.add_shader_node(anno_shader, "ShaderNodeMath",
                                position = (3, 0),
                                operation = "SUBTRACT",
                                inputs = {
                                    1 : inputs["Glossiness"],
                                },
                                default_inputs = {
                                    0 : 1.0
                                },
                            )
        #Metallic
        metallic = self.add_shader_node(anno_shader, "ShaderNodeRGBToBW",
                                        position = (1, 3),
                                        inputs = {
                                            "Color" : inputs["cMetallic"],
                                        },
                                    )
        #Emission
        scaled_emissive_color = self.add_shader_node(anno_shader, "ShaderNodeVectorMath",         
                            operation = "SCALE",
                            name = "EmissionScale",
                            position = (1, -1),
                            default_inputs = {
                                "Scale": 10,
                            },
                            inputs = {
                                "Vector" : inputs["cEmissiveColor"],
                            }
        )
        combined_emissive_color = self.add_shader_node(anno_shader, "ShaderNodeVectorMath",         
                            operation = "MULTIPLY",
                            position = (2, -1),
                            inputs = {
                                0 : final_diffuse.outputs["Color"],
                                1 : scaled_emissive_color.outputs["Vector"],
                            }
        )
        object_info = self.add_shader_node(anno_shader, "ShaderNodeObjectInfo",         
                            position = (1, -2),
        )
        random_0_1 = self.add_shader_node(anno_shader, "ShaderNodeMath",  
                            operation = "FRACT",   
                            position = (2, -2),
                            inputs = {
                                "Value" : object_info.outputs["Location"],
                            }
        )
        color_ramp_node = self.add_shader_node(anno_shader, "ShaderNodeValToRGB",  
                            position = (3, -2),
                            inputs = {
                                "Fac" : random_0_1.outputs["Value"],
                            }
        )

        color_ramp = color_ramp_node.color_ramp
        color_ramp.elements[0].color = (1.0, 0.0, 0.0,1)
        color_ramp.elements[1].position = (2.0/3.0)
        color_ramp.elements[1].color = (0.0, 0.0, 1.0,1)
        
        color_ramp.elements.new(1.0/3.0)
        color_ramp.elements[1].color = (0.0, 1.0, 0.0,1)
        color_ramp.interpolation = "CONSTANT"
        
        location_masked_emission = self.add_shader_node(anno_shader, "ShaderNodeVectorMath",         
                            operation = "MULTIPLY",
                            position = (4, -2),
                            inputs = {
                                0 : color_ramp_node.outputs["Color"],
                                1 : inputs["cNightGlow"],
                            }
        )
        
        final_emission_color = self.add_shader_node(anno_shader, "ShaderNodeMixRGB",         
                            blend_type = "MIX",
                            position = (5, -1),
                            default_inputs = {
                                "Color1" : (0.0, 0.0 ,0.0, 1.0)
                            },
                            inputs = {
                                "Fac" : location_masked_emission.outputs["Vector"],
                                "Color2" : combined_emissive_color.outputs["Vector"],
                            }
        )
        
        bsdf = self.add_shader_node(anno_shader, "ShaderNodeBsdfPrincipled", 
                                        position = (4, 0), 
                                        inputs = {
                                            "Alpha" : inputs["Alpha"],
                                            "Roughness" : roughness.outputs["Value"],
                                            "Normal" : bump_map.outputs["Normal"],
                                            "Base Color" : final_diffuse.outputs["Color"],
                                            "Metallic" : metallic.outputs["Val"],
                                            "Emission Strength" : inputs["EmissionStrength"],
                                            "Emission" : final_emission_color.outputs["Color"],
                                            
                                            
                                        },
                                    )
        outputs = self.add_shader_node(anno_shader, "NodeGroupOutput", 
                                        position = (5, 0), 
                                        inputs = {
                                            "Shader" : bsdf.outputs["BSDF"]
                                        },
                                    )

    
    def add_anno_shader(self, nodes):
        group = nodes.new(type='ShaderNodeGroup')
        if not "AnnoShader" in bpy.data.node_groups:
            self.create_anno_shader()            
        group.node_tree = bpy.data.node_groups["AnnoShader"]
        return group
        
    def as_blender_material(self):

        if self.get_material_cache_key() in Material.materialCache:
            return Material.materialCache[self.get_material_cache_key()]
        
        material = bpy.data.materials.new(name=self.name)
        
        material.dynamic_properties.from_node(self.node)
        material.use_nodes = True
        
        positioning_unit = (300, 300)
        positioning_offset = (0, 3 * positioning_unit[1])
        
        
        for i, texture_name in enumerate(self.texture_definitions.keys()):
            texture_node = material.node_tree.nodes.new('ShaderNodeTexImage')
            texture_path = Path(self.textures[texture_name])
            texture = self.get_texture(texture_path)
            if texture is not None:
                texture_node.image = texture
                if "Norm" in texture_name or "Metal" in texture_name or "Height" in texture_name:
                    texture_node.image.colorspace_settings.name = 'Non-Color'
            texture_node.name = texture_name
            texture_node.label = texture_name
            texture_node.location.x -= 4 * positioning_unit[0] - positioning_offset[0]
            texture_node.location.y -= i * positioning_unit[1] - positioning_offset[1]

            texture_node.anno_properties.enabled = self.texture_enabled[texture_name]
            extension = texture_path.suffix
            if extension not in [".png", ".psd"]:
                if texture_path != Path(""):
                    print("Warning: Unsupported texture file extension", extension, texture_path)
                extension = ".psd"
            texture_node.anno_properties.original_file_extension = extension
        
        node_tree = material.node_tree
        links = node_tree.links
        nodes = node_tree.nodes
        
        anno_shader = self.add_anno_shader(nodes)
        material.node_tree.nodes.remove(nodes["Principled BSDF"])
        
        emissive_color = self.add_shader_node(node_tree, "ShaderNodeCombineRGB",
                            name = "cEmissiveColor",
                            position = (3, 6.5),
                            default_inputs = {
                                "R": self.colors["cEmissiveColor"][0],
                                "G": self.colors["cEmissiveColor"][1],
                                "B": self.colors["cEmissiveColor"][2],
                            },
                            inputs = {}
        )
        c_diffuse_mult = self.add_shader_node(node_tree, "ShaderNodeCombineRGB",
                            name = "cDiffuseColor",
                            position = (2, 6.5),
                            default_inputs = {
                                "R": self.colors["cDiffuseColor"][0],
                                "G": self.colors["cDiffuseColor"][1],
                                "B": self.colors["cDiffuseColor"][2],
                            },
                            inputs = {}
        )
        
        links.new(anno_shader.inputs["cDiffuse"], nodes[self.texture_names["diffuse"]].outputs[0])
        links.new(anno_shader.inputs["cNormal"], nodes[self.texture_names["normal"]].outputs[0])
        links.new(anno_shader.inputs["cMetallic"], nodes[self.texture_names["metallic"]].outputs[0])
        links.new(anno_shader.inputs["cHeight"], nodes[self.texture_names["height"]].outputs[0])
        links.new(anno_shader.inputs["cNightGlow"], nodes[self.texture_names["night_glow"]].outputs[0])
        links.new(anno_shader.inputs["cDyeMask"], nodes[self.texture_names["dye"]].outputs[0])
        
        links.new(anno_shader.inputs["cDiffuseMultiplier"], c_diffuse_mult.outputs[0])
        links.new(anno_shader.inputs["cEmissiveColor"], emissive_color.outputs[0])
        
        links.new(anno_shader.inputs["Alpha"], nodes[self.texture_names["diffuse"]].outputs["Alpha"])
        links.new(anno_shader.inputs["Glossiness"], nodes[self.texture_names["normal"]].outputs["Alpha"])
        
        
        links.new(nodes["Material Output"].inputs["Surface"], anno_shader.outputs["Shader"])
        
        
        
        material.blend_method = "CLIP"

        
        #Store all kinds of properties for export
        for prop, value in self.custom_properties.items():
            material[prop] = value


        Material.materialCache[self.get_material_cache_key()] = material
        return material
    
    def add_shader_node(self, node_tree, node_type, **kwargs):
        node = node_tree.nodes.new(node_type)
        positioning_unit = (300, 300)
        positioning_offset = (0, 3 * positioning_unit[1])
        x,y = kwargs.pop("position", (0,0))
        node.location.x = x* positioning_unit[0] - positioning_offset[0]
        node.location.y = y* positioning_unit[1] - positioning_offset[1]
        if "name" in kwargs and not "label" in kwargs:
            kwargs["label"] = kwargs["name"]
        for input_key, default_value in kwargs.pop("default_inputs", {}).items():
            node.inputs[input_key].default_value = default_value
        for input_key, input_connector in kwargs.pop("inputs", {}).items():
             node_tree.links.new(node.inputs[input_key], input_connector)
        for attr, value in kwargs.items():
            setattr(node, attr, value)
        return node
    
    def add_shader_node_to_material(self, material, node_type, **kwargs):
        nodes = material.node_tree
        return self.add_shader_node(nodes, node_type, **kwargs)
###################################################################################################################

class ClothMaterial(Material):
    texture_definitions = {
        "cClothDiffuseTex":"DIFFUSE_ENABLED",
        "cClothNormalTex":"NORMAL_ENABLED",
        "cClothMetallicTex":"METALLIC_TEX_ENABLED",
        "cSeparateAOTex":"SEPARATE_AO_TEXTURE",
        "cHeightMap":"HEIGHT_MAP_ENABLED",
        "cNightGlowMap":"NIGHT_GLOW_ENABLED", 
        "cClothDyeMask":"DYE_MASK_ENABLED"
    }
    texture_names = {
        "diffuse":"cClothDiffuseTex",
        "normal":"cClothNormalTex",
        "metallic":"cClothMetallicTex",
        "ambient":"cSeparateAOTex",
        "height":"cHeightMap",
        "night_glow":"cNightGlowMap",
        "dye":"cClothDyeMask",
    }

def is_type(T: type, s: str) -> bool:
    try:
        T(s)
        return True
    except:
        return False

def string_to_fitting_type(s: str):
    if is_type(int, s) and s.isnumeric():
        return int(s)
    if is_type(float, s):
        return float(s)
    return s
    
def get_first_or_none(list):
    if list:
        return list[0]
    return None


def get_text(node: ET.Element, query: str, default_value = "") -> str:
    if node.find(query) is None:
        return str(default_value)
    if node.find(query).text is None:
        return str(default_value)
    return node.find(query).text

def get_text_and_delete(node: ET.Element, query: str, default_value = "") -> str:
    if node.find(query) is None:
        return str(default_value)
    subnode = node.find(query)
    parent = node
    if "/" in query:
        query = query.rsplit("/", maxsplit=1)[0]
        parent = node.find(query)
    parent.remove(subnode)
    while len(list(parent)) == 0 and parent != node:
        elements = query.rsplit("/", maxsplit=1)
        query = elements[0]
        parents_parent = node
        if len(elements) > 1:
            parents_parent = node.find(query)
        parents_parent.remove(parent)
        parent = parents_parent
    if subnode.text is None:
        return default_value
    return subnode.text

def format_float(value: Union[float, int]):
    return "{:.6f}".format(value)

def find_or_create(parent: ET.Element, simple_query: str) -> ET.Element:
    """Finds or creates the subnode corresponding to the simple query.
    

    Args:
        parent (ET.Element): root node
        simple_query (str): Only supports queries like "Config[ConfigType="ORIENTATION_TRANSFORM"]/Position/x", no advanced xpath.

    Returns:
        ET.Element: The node.
    """
    parts = simple_query.split("/", maxsplit = 1)
    query = parts[0]
    queried_node = parent.find(query)
    if queried_node is None:
        tag = query.split("[")[0]
        queried_node = ET.SubElement(parent, tag)
        if "[" in query:
            condition = query.split("[")[1].replace("]", "")
            subnode_tag = condition.split("=")[0].strip()
            subnode_value = condition.split("=")[1].strip().replace('"', '').replace("'", "")
            ET.SubElement(queried_node, subnode_tag).text = subnode_value
    if len(parts) > 1:
        return find_or_create(queried_node, parts[1])
    return queried_node

def convert_to_glb(fullpath: Path):
    rdm4_path = IO_AnnocfgPreferences.get_path_to_rdm4()
    if rdm4_path.exists() and fullpath.exists():
        subprocess.call(f"\"{rdm4_path}\" --input \"{fullpath}\" -n --outdst \"{fullpath.parent}\"", shell = True)

def convert_to_glb_if_required(data_path: Union[str, Path]):
    if data_path is None:
        return None
    fullpath = data_path_to_absolute_path(data_path)
    glb_fullpath = fullpath.with_suffix(".glb")
    if fullpath.exists() and not glb_fullpath.exists():
        convert_to_glb(fullpath)

def import_model_to_scene(data_path: Union[str, Path, None]) -> BlenderObject:
    if not data_path:
        return add_empty_to_scene()
    fullpath = data_path_to_absolute_path(data_path)
    convert_to_glb_if_required(fullpath)
    if fullpath is None:
        #self.report({'INFO'}, f"Missing file: Cannot find rmd model {data_path}.")
        return None
    fullpath = fullpath.with_suffix(".glb")
    if not fullpath.exists():
        #self.report({'INFO'}, f"Missing file: Cannot find glb model {data_path}.")
        return None
    ret = bpy.ops.import_scene.gltf(filepath=str(fullpath))
    obj = bpy.context.active_object
    return obj

def add_empty_to_scene(empty_type: str = "SINGLE_ARROW") -> BlenderObject:
    """Adds an empty of empty_type to the scene.

    Args:
        empty_type (str, optional): Possible values
            ['PLAIN_AXES', 'ARROWS', 'SINGLE_ARROW', 'CIRCLE', 'CUBE', 'SPHERE', 'CONE', 'IMAGE'].
            Defaults to "SINGLE_ARROW".

    Returns:
        BlenderObject: The empty object.
    """
    bpy.ops.object.empty_add(type=empty_type, align='WORLD', location = (0,0,0), scale = (1,1,1))
    obj = bpy.context.active_object
    return obj
    
    
T = TypeVar('T', bound='AnnoObject')


class AnnoObject(ABC):
    """Abstract base class of an intermediate representation of an entity
    from a .cfg, .ifo, etc file, f.e. a Model, Prop or Dummy.
    Can be created from an xml node using .from_node or from a blender object using from_blender_object.
    Can be converted to a node using to_node and to an blender object using to_blender_object.
    """
    has_transform: bool = False
    has_euler_rotation: bool = False
    has_name: bool = True
    transform_paths: Dict[str, str] = {}
    enforce_equal_scale: bool = False #scale.x, .y and .z must be equal
    has_materials: bool = False
    material_class = Material
    
    child_anno_object_types: Dict[str, type] = {}
    

    
    def __init__(self):
        self.custom_properties: Dict[str, Any] = {}
        self.transform: Transform = Transform()
        self.transform_condition = 0
        self.visibility_condition = 0
        self.name: str = ""
        self.materials: List[Material] = []
        self.node = None
        self.children_by_type: Dict[type, List[AnnoObject]] = {}
    
    @classmethod 
    def default_node(cls):
        return ET.Element("EmptyNode")

    @classmethod
    def from_default(cls: Type[T]) -> BlenderObject:
        node = cls.default_node()
        return cls.xml_to_blender(node)
    
    @classmethod
    def node_to_property_node(self, node, obj):
        return node
    @classmethod
    def property_node_to_node(self, property_node, obj):
        return property_node
    
    @classmethod
    def add_children_from_xml(cls, node, obj):
        for subnode_name, subcls in cls.child_anno_object_types.items():
            subnodes = node.find(subnode_name)
            if subnodes is not None:
                for subnode in list(subnodes):
                    child_obj = subcls.xml_to_blender(subnode, obj)
                node.remove(subnodes)
        
    @classmethod
    def xml_to_blender(cls: Type[T], node: ET.Element, parent_object = None) -> BlenderObject:
        obj = cls().add_blender_object_to_scene(node)
        set_anno_object_class(obj, cls)
        
        obj.name = cls.blender_name_from_node(node)
        if cls.has_name:
            get_text_and_delete(node, "Name")
        
        if parent_object is not None:
            obj.parent = parent_object
            
        if cls.has_transform:
            transform_node = node
            if "base_path" in cls.transform_paths and node.find(cls.transform_paths["base_path"]) is not None:
                transform_node = node.find(cls.transform_paths["base_path"])
            transform = Transform.from_node(transform_node, cls.transform_paths, cls.enforce_equal_scale, cls.has_euler_rotation)
            transform.apply_to(obj)

        if cls.has_materials:
            materials = []
            if node.find("Materials") is not None:
                materials_node = node.find("Materials")
                for material_node in list(materials_node):
                    material = cls.material_class.from_material_node(material_node)
                    materials.append(material)
                node.remove(materials_node)
            cls.apply_materials_to_object(obj, materials)
        
        cls.add_children_from_xml(node, obj)
        node = cls.node_to_property_node(node, obj)
        obj.dynamic_properties.from_node(node)
        return obj
    
    @classmethod
    def add_children_from_obj(cls, obj, node, child_map):
        container_name_by_subclass = {subcls : container_name for container_name, subcls in cls.child_anno_object_types.items()}
        for child_obj in child_map.get(obj.name, []):
            subcls = get_anno_object_class(child_obj)
            if subcls == NoAnnoObject:
                continue
            if subcls not in container_name_by_subclass:
                continue
            container_name = container_name_by_subclass[subcls]
            container_subnode = find_or_create(node, container_name)
            subnode = subcls.blender_to_xml(child_obj, container_subnode, child_map)

    @classmethod
    def blender_to_xml(cls, obj: BlenderObject, parent_node: ET.Element, child_map: Dict[str, BlenderObject]) -> ET.Element:
        node = ET.Element("AnnoObject")
        if parent_node is not None:
            parent_node.append(node)
        node = obj.dynamic_properties.to_node(node)
        node = cls.property_node_to_node(node, obj)
        
        if cls.has_name:
            name = cls.anno_name_from_blender_object(obj)
            find_or_create(node, "Name").text = name
        if cls.has_transform:
            transform_node = node
            transform = Transform.from_blender_object(obj, cls.enforce_equal_scale, cls.has_euler_rotation)
            transform.convert_to_anno_coords()
            if "base_path" in cls.transform_paths:
                transform_node = find_or_create(node, cls.transform_paths["base_path"])
            for transform_component, xml_path in cls.transform_paths.items():
                if transform_component == "base_path":
                    continue
                value = transform.get_component_value(transform_component)
                find_or_create(transform_node, xml_path).text = format_float(value)
        if cls.has_materials:
            materials_node = find_or_create(node, "Materials")
            if obj.data and obj.data.materials:
                for blender_material in obj.data.materials:
                    material = cls.material_class.from_blender_material(blender_material)
                    material.to_xml_node(parent = materials_node)
                
        cls.add_children_from_obj(obj, node, child_map) 

        return node
    
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        """Subclass specific method to add a representing blender object to the scene.

        Returns:
            BlenderObject: The added object
        """
        return add_empty_to_scene()
    
    @classmethod
    def blender_name_from_node(cls, node):
        config_type = get_text(node, "ConfigType", node.tag)
        if config_type == "i":
            config_type = cls.__name__
        file_name = Path(get_text(node, "FileName", "")).stem
        name = get_text(node, "Name", file_name)
        return config_type + "_" + name
    
    
    @classmethod
    def anno_name_from_blender_object(cls, obj):
        split = obj.name.split("_", maxsplit = 1)
        if len(split) > 1:
            return split[1]
        return obj.name
    
    def blender_name_from_anno_name(self, name: str) -> str:
        return name
    
    def anno_name_from_blender_name(self, name: str) -> str:
        return name
    
    @classmethod
    def apply_materials_to_object(cls, obj: BlenderObject, materials: List[Optional[Material]]):
        """Apply the materials to the object.

        Args:
            obj (BlenderObject): The object
            materials (List[Material]): The materials.
        """
        
        if not obj.data or not obj.data.materials:
            return
        for i, material in enumerate(materials):
            if not material:
                continue
            if i < len(obj.data.materials):
                old_material = obj.data.materials[i]
                obj.data.materials[i] = material.as_blender_material()
                old_material.user_clear()
                bpy.data.materials.remove(old_material)
            else:
                obj.data.materials.append(material.as_blender_material())
        


class Cloth(AnnoObject):
    has_transform = True
    transform_paths = {
        "base_path":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']",
        "location.x":"Position.x",
        "location.y":"Position.y",
        "location.z":"Position.z",
        "rotation.x":"Rotation.x",
        "rotation.y":"Rotation.y",
        "rotation.z":"Rotation.z",
        "rotation.w":"Rotation.w",
        "scale.x":"Scale",
        "scale.y":"Scale",
        "scale.z":"Scale",
    }
    enforce_equal_scale = True #scale.x, .y and .z must be equal
    has_materials = True
    material_class = ClothMaterial
    
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        data_path = get_text(node, "FileName")
        imported_obj = import_model_to_scene(data_path)
        if imported_obj is None:
            return add_empty_to_scene()
        return imported_obj




class Model(AnnoObject):
    has_transform = True
    transform_paths = {
        "base_path":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']",
        "location.x":"Position.x",
        "location.y":"Position.y",
        "location.z":"Position.z",
        "rotation.x":"Rotation.x",
        "rotation.y":"Rotation.y",
        "rotation.z":"Rotation.z",
        "rotation.w":"Rotation.w",
        "scale.x":"Scale",
        "scale.y":"Scale",
        "scale.z":"Scale",
    }
    enforce_equal_scale = True #scale.x, .y and .z must be equal
    has_materials = True


    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        data_path = get_text(node, "FileName")
        imported_obj = import_model_to_scene(data_path)
        if imported_obj is None:
            return add_empty_to_scene()
        return imported_obj
    

class SubFile(AnnoObject):
    has_transform = True
    transform_paths = {
        "base_path":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']",
        "location.x":"Position.x",
        "location.y":"Position.y",
        "location.z":"Position.z",
        "rotation.x":"Rotation.x",
        "rotation.y":"Rotation.y",
        "rotation.z":"Rotation.z",
        "rotation.w":"Rotation.w",
        "scale.x":"Scale",
        "scale.y":"Scale",
        "scale.z":"Scale",
    }
    enforce_equal_scale = True #scale.x, .y and .z must be equal
    has_materials = False
    
    @classmethod 
    def load_subfile(cls, data_path):
        if data_path is None:
            return add_empty_to_scene()
        
        fullpath = data_path_to_absolute_path(data_path)
        if not fullpath.exists():
            return add_empty_to_scene()
        tree = ET.parse(fullpath)
        root = tree.getroot()
        if root is None:
            return add_empty_to_scene()
        
        file_obj = MainFile.xml_to_blender(root)
        file_obj.name = "MAIN_FILE_" + fullpath.name
        return file_obj
        
        
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        subfile_obj = add_empty_to_scene()
        data_path = get_text(node, "FileName", None)
        file_obj = cls.load_subfile(data_path)  
        file_obj.parent = subfile_obj
        return subfile_obj

class Decal(AnnoObject):
    has_transform = True
    transform_paths = {
        "scale.x":"Extents.x",
        "scale.y":"Extents.y",
        "scale.z":"Extents.z",
    }
    enforce_equal_scale = False #scale.x, .y and .z must be equal
    has_materials = True

    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, align='WORLD', location=(0,0,0), scale=(1,1,1))

        obj = bpy.context.active_object
        for v in obj.data.vertices:
            v.co.y *= -1.0
        return obj   
    
    @classmethod
    def apply_materials_to_object(cls, obj: BlenderObject, materials: List[Optional[Material]]):
        for mat in materials:
            obj.data.materials.append(mat.as_blender_material())
 
 
class Prop(AnnoObject):
    has_transform = True
    transform_paths = {
        "location.x":"Position.x",
        "location.y":"Position.y",
        "location.z":"Position.z",
        "rotation.x":"Rotation.x",
        "rotation.y":"Rotation.y",
        "rotation.z":"Rotation.z",
        "rotation.w":"Rotation.w",
        "scale.x":"Scale.x",
        "scale.y":"Scale.y",
        "scale.z":"Scale.z",
    }
    enforce_equal_scale = False #scale.x, .y and .z must be equal
    has_materials = False

    
    prop_data_by_filename: Dict[str, Tuple[Optional[str], Optional[Material]]] = {} #avoids opening the same .prp file multiple times
    
    @classmethod
    def get_prop_data(cls, prop_filename: str) -> Tuple[Optional[str], Optional[Material]]:
        """Caches results in prop_data_by_filename

        Args:
            prop_filename (str): Name of the .prp file. Example: "data/graphics/.../example.prp"

        Returns:
            Tuple[str, Material]: Path to the .rdm file of the prop and its material.
        """
        if prop_filename in cls.prop_data_by_filename:
            return cls.prop_data_by_filename[prop_filename]
        prop_file = data_path_to_absolute_path(prop_filename)
        if not prop_file.exists() or prop_file.suffix != ".prp":
            return (None, None)
        with open(prop_file) as file:
            content = file.read()
            mesh_file_name = re.findall("<MeshFileName>(.*?)<", content, re.I)[0]
            diff_path = get_first_or_none(re.findall("<cModelDiffTex>(.*?)<", content, re.I))
            #Some props (trees) do seem to have a cProp texture. Let's just deal with that.
            if diff_path is None:
                diff_path = get_first_or_none(re.findall("<cPropDiffuseTex>(.*?)<", content, re.I))
            norm_path = get_first_or_none(re.findall("<cModelNormalTex>(.*?)<", content, re.I))
            if norm_path is None:
                norm_path = get_first_or_none(re.findall("<cPropNormalTex>(.*?)<", content, re.I))
            metallic_path = get_first_or_none(re.findall("<cModelMetallicTex>(.*?)<", content, re.I))
            if metallic_path is None:
                metallic_path = get_first_or_none(re.findall("<cPropMetallicTex>(.*?)<", content, re.I))
            material = Material.from_filepaths(prop_filename, diff_path, norm_path, metallic_path)
        prop_data = (mesh_file_name, material)
        cls.prop_data_by_filename[prop_filename] = prop_data
        return prop_data
    
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        prop_filename = get_text(node, "FileName")
        model_filename, material = cls.get_prop_data(prop_filename)
        imported_obj = import_model_to_scene(model_filename)
        if imported_obj is None:
            return add_empty_to_scene()

        
        #materials
        cls.apply_materials_to_object(imported_obj, [material])
        return imported_obj


 
class Propcontainer(AnnoObject):
    has_transform = True
    transform_paths = {
        "base_path":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']",
        "location.x":"Position.x",
        "location.y":"Position.y",
        "location.z":"Position.z",
        "rotation.x":"Rotation.x",
        "rotation.y":"Rotation.y",
        "rotation.z":"Rotation.z",
        "rotation.w":"Rotation.w",
        "scale.x":"Scale.x",
        "scale.y":"Scale.y",
        "scale.z":"Scale.z",
    }
    enforce_equal_scale = True #scale.x, .y and .z must be equal
    has_materials = False
    child_anno_object_types = {
        "Props" : Prop,
    }

class Light(AnnoObject):
    has_transform = True
    has_visibility_transform = False #not sure...
    enforce_equal_scale = True
    transform_paths = {
        "base_path":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']",
        "location.x":"Position.x",
        "location.y":"Position.y",
        "location.z":"Position.z",
        "rotation.x":"Rotation.x",
        "rotation.y":"Rotation.y",
        "rotation.z":"Rotation.z",
        "rotation.w":"Rotation.w",
        "scale.x":"Scale",
        "scale.y":"Scale",
        "scale.z":"Scale",
    }
    @classmethod
    def node_to_property_node(self, node, obj):
        node = super().node_to_property_node(node, obj)
        diffuse_r = float(get_text_and_delete(node, "Diffuse.r", "1.0"))
        diffuse_g = float(get_text_and_delete(node, "Diffuse.g", "1.0"))
        diffuse_b = float(get_text_and_delete(node, "Diffuse.b", "1.0"))
        diffuse_color = [diffuse_r, diffuse_g, diffuse_b]
        obj.data.color = diffuse_color
        return node
    @classmethod
    def property_node_to_node(self, property_node, obj):
        property_node = super().property_node_to_node(property_node, obj)
        diffuse_color = obj.data.color
        ET.SubElement(property_node, "Diffuse.r").text = format_float(diffuse_color[0])
        ET.SubElement(property_node, "Diffuse.g").text = format_float(diffuse_color[1])
        ET.SubElement(property_node, "Diffuse.b").text = format_float(diffuse_color[2])
        return property_node 
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        bpy.ops.object.light_add(type='POINT', radius=1)
        obj = bpy.context.active_object
        return obj
  
    
class Particle(AnnoObject):
    has_transform = True
    has_visibility_transform = True
    transform_paths = {
        "base_path":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']",
        "location.x":"Position.x",
        "location.y":"Position.y",
        "location.z":"Position.z",
        "rotation.x":"Rotation.x",
        "rotation.y":"Rotation.y",
        "rotation.z":"Rotation.z",
        "rotation.w":"Rotation.w",
        "scale.x":"Scale",
        "scale.y":"Scale",
        "scale.z":"Scale",
    }
    enforce_equal_scale = True
    has_materials = False
    
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        obj = add_empty_to_scene("SPHERE")   
        return obj


class ArbitraryXMLAnnoObject(AnnoObject):
    xml_template = """<T></T>"""
    has_name = False
    
class IfoFile(AnnoObject):
    has_name = False
    @classmethod
    def add_children_from_xml(cls, node, obj):
        ifo_object_by_name = {
            "Sequence":Sequence,
            "BoundingBox":IfoCube,
            "MeshBoundingBox":IfoCube,
            "IntersectBox":IfoCube,
            "Dummy":IfoCube,
            "BuildBlocker":IfoPlane,
            "FeedbackBlocker":IfoPlane,
            "PriorityFeedbackBlocker":IfoPlane,
            "UnevenBlocker":IfoPlane,
            "QuayArea":IfoPlane,
            "InvisibleQuayArea":IfoPlane,
        }
        for child_node in list(node):
            ifo_cls = ifo_object_by_name.get(child_node.tag, None)
            if ifo_cls is None:
                continue
            ifo_obj = ifo_cls.xml_to_blender(child_node, obj)
            node.remove(child_node)
    
    @classmethod
    def add_children_from_obj(cls, obj, node, child_map):
        for child_obj in child_map.get(obj.name, []):
            subcls = get_anno_object_class(child_obj)
            if subcls == NoAnnoObject:
                continue
            subnode = subcls.blender_to_xml(child_obj, node, child_map)



class IfoCube(AnnoObject):
    has_transform = True
    has_name = False
    transform_paths = {
        "location.x":"Position/xf",
        "location.y":"Position/yf",
        "location.z":"Position/zf",
        "rotation.x":"Rotation/xf",
        "rotation.y":"Rotation/yf",
        "rotation.z":"Rotation/zf",
        "rotation.w":"Rotation/wf",
        "scale.x":"Extents/xf",
        "scale.y":"Extents/yf",
        "scale.z":"Extents/zf",
    }
    has_materials = False
    
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        bpy.ops.mesh.primitive_cube_add(location=(0,0,0))
        obj = bpy.context.active_object
        obj.display_type = 'WIRE'
        return obj

class IfoPlane(AnnoObject):
    has_transform = False
    has_materials = False
    has_name = False
    
    @classmethod
    def add_object_from_vertices(self, vertices: List[Tuple[float,float,float]], name) -> BlenderObject:
        """Creates a mesh and blender object to represent a IfoPlane.

        Args:
            vertices (List[Tuple[float,float,float]]): Representing vertices

        Returns:
            BlenderObject: The object.
        """
        edges = [] #type: ignore
        faces = [[i for i,v in enumerate(vertices)]] #leads to double vertices -> bad??? todo: why?
        new_mesh = bpy.data.meshes.new('new_mesh')
        new_mesh.from_pydata(vertices, edges, faces)
        new_mesh.update()
        new_object = bpy.data.objects.new(name, new_mesh)
        bpy.context.scene.collection.objects.link(new_object)
        return new_object
    
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        vertices = []
        for pos_node in list(node.findall("Position")):
            x = - parse_float_node(pos_node, "xf")
            y = - parse_float_node(pos_node, "zf")
            vertices.append((x,y, 0.0))
            node.remove(pos_node)
        obj = cls.add_object_from_vertices(vertices, "IFOPlane")
        obj.display_type = 'WIRE'
        return obj

    @classmethod 
    def blender_to_xml(cls, obj, parent_node, child_map):
        node = super().blender_to_xml(obj, parent_node, child_map)
        for vert in obj.data.vertices:
            x = vert.co.x
            y = vert.co.y
            position_node = ET.SubElement(node, "Position")
            ET.SubElement(position_node, "xf").text = format_float(-x)
            ET.SubElement(position_node, "zf").text = format_float(-y)
        return node

class Sequence(AnnoObject):
    has_transform = False
    has_name = False



class Dummy(AnnoObject):
    has_name = False
    has_transform = True
    has_euler_rotation = True
    transform_paths = {
        "location.x":"Position/x",
        "location.y":"Position/y",
        "location.z":"Position/z",
        "rotation_euler.y":"RotationY",
        "scale.x":"Extents/x",
        "scale.y":"Extents/y",
        "scale.z":"Extents/z",
    }
    has_materials = False
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        file_obj = add_empty_to_scene("ARROWS")  
        return file_obj
    @classmethod
    def default_node(cls: Type[T]):
        node = super().default_node()
        node.tag = "Dummy"
        ET.SubElement(node, "Name")
        ET.SubElement(node, "HeightAdaptationMode").text = "1"
        extents = ET.SubElement(node, "Extents")
        ET.SubElement(extents, "x").text = "0.1"
        ET.SubElement(extents, "y").text = "0.1"
        ET.SubElement(extents, "z").text = "0.1"
        return node
    @classmethod
    def property_node_to_node(self, node, obj):
        """If created from a imported Cf7Object, we can remove a few fields"""
        get_text_and_delete(node, "Id")
        get_text_and_delete(node, "has_value")
        return node

class DummyGroup(AnnoObject):
    has_transform = False
    has_name = False
    @classmethod
    def default_node(cls: Type[T]):
        node = super().default_node()
        node.tag = "DummyGroup"
        ET.SubElement(node, "Name")
        return node
    
    @classmethod
    def add_children_from_xml(cls, node, obj):
        for child_node in list(node):
            if len(list(child_node)) == 0:
                continue
            dummy = Dummy.xml_to_blender(child_node, obj)
            node.remove(child_node)

    @classmethod
    def add_children_from_obj(cls, obj, node, child_map):
        for child_obj in child_map.get(obj.name, []):
            subcls = get_anno_object_class(child_obj)
            if subcls == NoAnnoObject:
                continue
            subnode = Dummy.blender_to_xml(child_obj, node, child_map)

    @classmethod
    def property_node_to_node(self, node, obj):
        """If created from a imported Cf7Object, we can remove a few fields"""
        get_text_and_delete(node, "Id")
        get_text_and_delete(node, "has_value")
        get_text_and_delete(node, "Groups")
        return node




class FeedbackConfig(AnnoObject):
    has_name = False
    has_transform = False 

    def __init__(self):
        super().__init__()

    @classmethod
    def default_node(cls: Type[T]):
        node = super().default_node()
        node.tag = "FeedbackConfig"
        ET.SubElement(node, "GUIDVariationList")
        ET.SubElement(node, "SequenceElements")
        return node
    
    @classmethod
    def node_to_property_node(cls, node, obj):
        for prop in FeedbackConfigItem.__annotations__.keys():
            if get_text(node, prop, "") == "":
                continue
            value = cls.convert_to_blender_datatype(prop, get_text_and_delete(node, prop))
            try:
                setattr(obj.feedback_config_item, prop, value)
            except:
                print("ValueError: simple anno feedback", prop, value, type(value))
                pass
        value = cls.convert_to_blender_datatype("Scale/m_MinScaleFactor", get_text_and_delete(node, "Scale/m_MinScaleFactor", "0.5"))
        setattr(obj.feedback_config_item, "m_MinScaleFactor", value)
        value = cls.convert_to_blender_datatype("Scale/m_MinScaleFactor", get_text_and_delete(node, "Scale/m_MaxScaleFactor", "0.5"))
        setattr(obj.feedback_config_item, "m_MaxScaleFactor", value)
        
        guid_list = obj.feedback_guid_list
        for guid_node in list(node.find("GUIDVariationList")):
            guid = guid_node.text
            guid_list.add()
            guid_list[-1].guid_type = feedback_enums.get_enum_type(guid)
            if guid_list[-1].guid_type != "Custom":
                guid_list[-1].guid = guid
            else:
                guid_list[-1].custom_guid = guid
        get_text_and_delete(node, "GUIDVariationList")
        
        seq_list = obj.feedback_sequence_list
        for seq_node in list(node.find("SequenceElements")):
            tag = seq_node.tag
            seq_list.add()
            seq_item = seq_list[-1]
            seq_item.animation_type = tag
            for subnode in list(seq_node):
                key = subnode.tag
                value = subnode.text
                if key == "Tag":
                    continue
                if key in ["m_IdleSequenceID", "WalkSequence"]:
                    key = "sequence"
                if key == "SpeedFactorF":
                    key = "speed_factor_f"
                if key == "TargetDummy":
                    key = "target_empty"
                if key == "MinPlayCount":
                    key = "min_play_count"
                if key == "MaxPlayCount":
                    key = "max_play_count"
                if key == "MinPlayTime":
                    key = "min_play_time"
                if key == "MaxPlayTime":
                    key = "max_play_time"
                value = cls.convert_to_blender_datatype(key, value)
                try:
                    setattr(seq_item, key, value)
                except:
                    print("Failed other with", key, value,type(value))
                    pass
        get_text_and_delete(node, "SequenceElements")
        return node
    @classmethod
    def property_node_to_node(cls, node, obj):
        for prop in FeedbackConfigItem.__annotations__.keys():
            if prop in ["m_MinScaleFactor", "m_MaxScaleFactor"]:
                continue
            value = getattr(obj.feedback_config_item, prop)
            if value is None:
                value == ""
            if type(value) == float:
                value = format_float(value)
            if type(value) == bpy.types.Object:
                value = value.dynamic_properties.get_string("Name", "UNKNOWN_DUMMY")
            find_or_create(node, prop).text = str(value)
        
        find_or_create(node, "Scale/m_MinScaleFactor").text = format_float(obj.feedback_config_item.m_MinScaleFactor)
        find_or_create(node, "Scale/m_MaxScaleFactor").text = format_float(obj.feedback_config_item.m_MaxScaleFactor) 
        
        guid_list_node = find_or_create(node, "GUIDVariationList")
        guid_list = obj.feedback_guid_list
        for guid_item in guid_list:
            if guid_item.guid_type != "Custom":
                ET.SubElement(guid_list_node, "GUID").text = guid_item.guid
            else: 
                ET.SubElement(guid_list_node, "GUID").text = guid_item.custom_guid
        sequences_node = find_or_create(node, "SequenceElements")
        sequence_list = obj.feedback_sequence_list
        for seq_item in sequence_list:
            sequence = {}
            
            if seq_item.animation_type == "Walk":
                sequence["WalkSequence"] = seq_item.sequence
                sequence["SpeedFactorF"] = seq_item.speed_factor_f
                if seq_item.target_empty:
                    sequence["TargetDummy"] = seq_item.target_empty.dynamic_properties.get_string("Name", "UNKNOWN_DUMMY")
            elif seq_item.animation_type == "IdleAnimation":
                sequence["m_IdleSequenceID"] = seq_item.sequence
                sequence["MinPlayCount"] = seq_item.min_play_count
                sequence["MaxPlayCount"] = seq_item.max_play_count
            elif seq_item.animation_type == "TimedIdleAnimation":
                sequence["m_IdleSequenceID"] = seq_item.sequence
                sequence["MinPlayTime"] = seq_item.min_play_time
                sequence["MaxPlayTime"] = seq_item.max_play_time
            seq_node = ET.SubElement(sequences_node, seq_item.animation_type)
            for key, value in sequence.items():
                if key == "Tag":
                    continue
                ET.SubElement(seq_node, key).text = str(value)
        node.tag = "FeedbackConfig"
        return node
    @classmethod
    def convert_to_blender_datatype(cls, prop, annovalue):
        if annovalue == "True":
            return True
        if annovalue == "False":
            return False
        if prop in ["TargetDummy", "DefaultStateDummy", "target_empty"]:
            name = "Dummy_" + annovalue
            return bpy.data.objects.get(name, None)
        if prop in ["MultiplyActorByDummyCount"]:
            name = "DummyGroup_" + annovalue
            return bpy.data.objects.get(name, None)
        return string_to_fitting_type(annovalue)


class SimpleAnnoFeedbackEncodingObject(AnnoObject):
    has_name = False
    has_transform = False
    child_anno_object_types = {
        "DummyGroups" : DummyGroup,
        "FeedbackConfigs" : FeedbackConfig,
    }   
    @classmethod
    def property_node_to_node(self, node, obj):
        node.tag = "SimpleAnnoFeedbackEncoding"
        for child in list(node):
            node.remove(child)
        return node
    

class Cf7Dummy(AnnoObject):
    has_name = False
    has_transform = True
    has_euler_rotation = True
    transform_paths = {
        "location.x":"Position/x",
        "location.y":"Position/y",
        "location.z":"Position/z",
        "rotation_euler.y":"RotationY",
        "scale.x":"Extents/x",
        "scale.y":"Extents/y",
        "scale.z":"Extents/z",
    }
    has_materials = False
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        file_obj = add_empty_to_scene("ARROWS")  
        return file_obj

class Cf7DummyGroup(AnnoObject):
    has_transform = False
    has_name = False
    child_anno_object_types = {
        "Dummies" : Cf7Dummy,
    }   


class Cf7File(AnnoObject):
    has_name = False
    child_anno_object_types = {
        "DummyRoot/Groups" : Cf7DummyGroup,
    }   
    @classmethod
    def add_children_from_xml(cls, node, obj):
        if not node.find("DummyRoot/Groups"):
            return
        for group_node in list(node.find("DummyRoot/Groups")):
            Cf7DummyGroup.xml_to_blender(group_node, obj)
            node.find("DummyRoot/Groups").remove(group_node)
        if not IO_AnnocfgPreferences.splines_enabled():
            return
        for spline_data in list(node.findall("SplineData/v")):
            Spline.xml_to_blender(spline_data, obj)
            node.find("SplineData").remove(spline_data)
    @classmethod
    def add_children_from_obj(cls, obj, node, child_map):
        dummy_groups_node = find_or_create(node, "DummyRoot/Groups")
        for child_obj in child_map.get(obj.name, []):
            subcls = get_anno_object_class(child_obj)
            if subcls != Cf7DummyGroup:
                continue
            Cf7DummyGroup.blender_to_xml(child_obj, dummy_groups_node, child_map)
        if not IO_AnnocfgPreferences.splines_enabled():
            return
        spline_data_node = find_or_create(node, "SplineData")
        for spline_obj in child_map.get(obj.name, []):
            subcls = get_anno_object_class(spline_obj)
            if subcls != Spline:
                continue
            splinenode_v = Spline.blender_to_xml(spline_obj, spline_data_node, child_map)
            ET.SubElement(spline_data_node, "k").text = get_text(splinenode_v, "Name", "UNKNOWN_KEY")
    
class NoAnnoObject(AnnoObject):
    pass


class Spline(AnnoObject):
    has_transform = False
    has_name = False
    
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        bpy.ops.curve.primitive_bezier_curve_add()

        obj = bpy.context.active_object
        spline = obj.data.splines[0]
        control_points = node.find("ControlPoints")
        if control_points is None:
            return obj
        spline.bezier_points.add(len(control_points)-2)
        for i, control_point_node in enumerate(control_points):
            x = get_float(control_point_node, "x")
            y = get_float(control_point_node, "y")
            z = get_float(control_point_node, "z")
            transform = Transform(loc = [x,y,z], anno_coords = True)
            transform.convert_to_blender_coords()
            spline.bezier_points[i].co.x = transform.location[0]
            spline.bezier_points[i].co.y = transform.location[1]
            spline.bezier_points[i].co.z = transform.location[2]
            spline.bezier_points[i].handle_left_type = "AUTO"
            spline.bezier_points[i].handle_right_type = "AUTO"
            
        # obj.data.splines.new("BEZIER")
        # spline = obj.data.splines[1]
        # control_points = node.find("ApproximationPoints")
        # if control_points is None:
        #     return obj
        # spline.bezier_points.add(len(control_points))
        # for i, control_point_node in enumerate(control_points):
        #     x = get_float(control_point_node, "x")
        #     y = get_float(control_point_node, "y")
        #     z = get_float(control_point_node, "z")
        #     transform = Transform(loc = [x,y,z], anno_coords = True)
        #     transform.convert_to_blender_coords()
        #     spline.bezier_points[i].co.x = transform.location[0]
        #     spline.bezier_points[i].co.y = transform.location[1]
        #     spline.bezier_points[i].co.z = transform.location[2]
        #     spline.bezier_points[i].handle_left_type = "AUTO"
        #     spline.bezier_points[i].handle_right_type = "AUTO"
            
        return obj   
    
    @classmethod
    def node_to_property_node(self, node, obj):
        node = super().node_to_property_node(node, obj)
        get_text_and_delete(node, "ControlPoints")
        return node
    
    @classmethod
    def property_node_to_node(self, property_node, obj):
        node = super().property_node_to_node(property_node, obj)
        control_points = find_or_create(node, "ControlPoints")
        spline = obj.data.splines[0]
        for i, point in enumerate(spline.bezier_points):
            point_node = ET.SubElement(control_points, "i")
            x = spline.bezier_points[i].co.x
            y = spline.bezier_points[i].co.y
            z = spline.bezier_points[i].co.z
            transform = Transform(loc = [x,y,z], anno_coords = False)
            transform.convert_to_anno_coords()
            ET.SubElement(point_node, "x").text = format_float(transform.location[0])
            ET.SubElement(point_node, "y").text = format_float(transform.location[1])
            ET.SubElement(point_node, "z").text = format_float(transform.location[2])
        return node
 


class MainFile(AnnoObject):
    has_name = False
    has_transform = False
    child_anno_object_types = {
        "Models" : Model,
        "Clothes" : Cloth,
        "Files" : SubFile,
        "PropContainers" : Propcontainer,
        "Particles" : Particle,
        "Lights" : Light,
        "Decals" : Decal,
    }   
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        file_obj = add_empty_to_scene()  
        return file_obj


anno_object_classes = [
    NoAnnoObject, MainFile, Model, Cf7File,
    SubFile, Decal, Propcontainer, Prop, Particle, IfoCube, IfoPlane, Sequence, DummyGroup,
    Dummy, Cf7DummyGroup, Cf7Dummy, FeedbackConfig,SimpleAnnoFeedbackEncodingObject, ArbitraryXMLAnnoObject, Light, Cloth, Material, IfoFile, Spline
]


def get_anno_object_class(obj) -> type:
    return str_to_class(obj.anno_object_class_str)

def set_anno_object_class(obj, cls: type):
     obj.anno_object_class_str = cls.__name__
    
classes = [
    AnnoImageTextureProperties,
    PT_AnnoImageTexture,
    
    BoolPropertyGroup,
    IntPropertyGroup,
    StringPropertyGroup,
    FloatPropertyGroup,
    FilenamePropertyGroup,
    ColorPropertyGroup,
    FeedbackSequencePropertyGroup,
    
    PT_AnnoScenePropertyPanel,
    
    PT_AnnoMaterialObjectPropertyPanel,
    ConvertCf7DummyToDummy,
    
    XMLPropertyGroup,
    PT_AnnoObjectPropertyPanel,
]
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.ShaderNodeTexImage.anno_properties = bpy.props.PointerProperty(type=AnnoImageTextureProperties)
    bpy.types.Object.anno_object_class_str = bpy.props.EnumProperty(name="Anno Object Class", description = "Determines the type of the object.",
                                                                items = [(cls.__name__, cls.__name__, cls.__name__) for cls in anno_object_classes]
                                                                , default = "NoAnnoObject")
    bpy.types.Object.dynamic_properties = bpy.props.PointerProperty(type = XMLPropertyGroup)
    bpy.types.Material.dynamic_properties = bpy.props.PointerProperty(type = XMLPropertyGroup)
    #CollectionProperty(type = AnnoImageTextureProperties)

def unregister():
    del bpy.types.ShaderNodeTexImage.anno_properties
    del bpy.types.Object.dynamic_properties
    del bpy.types.Object.anno_object_class_str
    for cls in classes:
        bpy.utils.unregister_class(cls)

