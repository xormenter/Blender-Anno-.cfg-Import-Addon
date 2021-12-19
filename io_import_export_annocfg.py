
"""
Allows you to import from Anno (1800) .cfg files, make changes and export it to .cfg again.
Automatically positions all models, props, particles, decals, subfiles, ifo-blockers, and cf7 blockers in the scene.
When used with the rdm4 converter and texconv, it will automatically convert .rdm to .glb and .dds to .png for importing.
Also capable of importing/exporting corresponding .ifo and .cf7 (converted from .fc) files.
"""

import bpy
bl_info = {
    "name": "ImportExportAnnoCfg",
    "version": (1, 6),
    "blender": (2, 93, 0),
    "category": "Import-Export",
}
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator, AddonPreferences

import xml.etree.ElementTree as ET
import os
import re
import subprocess
import mathutils
from datetime import datetime
from pathlib import Path


class ImportExportAnnoCfgPreferences(AddonPreferences):
    bl_idname = __name__

    path_to_rda_folder : StringProperty(
        name = "Path to rda Folder",
        description = "Path where you unpacked the Anno rda files. Should contain the data folder.",
        subtype='FILE_PATH',
        default = "",
    )
    path_to_rdm4 : StringProperty(
        name = "Path to rdm4-bin.exe",
        description = "Path to the rdm4 converter.",
        subtype='FILE_PATH',
        default = "C:\\tools\\rdm4-bin.exe",
    )
    path_to_texconv : StringProperty(
        name = "Path to texconv.exe",
        description = "Path to the texconv tool used to convert .dds to .png.",
        subtype='FILE_PATH',
        default = "C:\\Users\\Public\\texconv.exe",
    )
    path_to_fc_converter : StringProperty(
        name = "Path to AnnoFCConverter.exe",
        description = "Path to the AnnoFCConverter tool used to convert .fc to .cf7 and vice versa.",
        subtype='FILE_PATH',
        default = "C:\\tools\\AnnoFCConverter.exe",
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Paths")
        layout.prop(self, "path_to_rda_folder")
        layout.prop(self, "path_to_rdm4")
        layout.prop(self, "path_to_texconv")
        layout.prop(self, "path_to_fc_converter")

    @classmethod
    def get_path_to_rda_folder(cls):
        return Path(bpy.context.preferences.addons[__name__].preferences.path_to_rda_folder)
    @classmethod
    def get_path_to_rdm4(cls):
        return Path(bpy.context.preferences.addons[__name__].preferences.path_to_rdm4)
    @classmethod
    def get_path_to_texconv(cls):
        return Path(bpy.context.preferences.addons[__name__].preferences.path_to_texconv)
    @classmethod
    def get_path_to_fc_converter(cls):
        return Path(bpy.context.preferences.addons[__name__].preferences.path_to_fc_converter)


def add_rda_path_prefix(path):
    return Path(ImportExportAnnoCfgPreferences.get_path_to_rda_folder(), path)

################################################################################################################################

def config_types():
    return ["MODEL", "FILE", "PROPCONTAINER", "PROP", "PARTICLE", "MATERIAL", "DECAL"]

class UniqueNamer():
    def __init__(self):
        self.unique_names = set()
        self.unique_id_counter = 0
    # If input_name is not unique for this file, generate a new unique name from config_type and namehint
    def get_unique_name(self, input_name, config_type, namehint = None):
        if input_name is not None and input_name != "":
            input_name = input_name.strip()
            if input_name not in self.unique_names:
                unique_name = input_name
                if not re.match(config_type, input_name, re.I):
                    unique_name = config_type + "_" + unique_name
                self.unique_names.add(unique_name)
                return unique_name
            unique_name = config_type +"_"+ str(self.unique_id_counter) +"_"+ input_name
            self.unique_id_counter += 1
            self.unique_names.add(unique_name)
            return unique_name
        if namehint is None:
            namehint = "unnamed"
        unique_name = config_type +"_"+ str(self.unique_id_counter) +"_"+ namehint
        self.unique_id_counter += 1
        self.unique_names.add(unique_name)
        return unique_name
        

def ensure_unique_identifiers_in_subtree(node, unique_namer):
    config_type = node.find("ConfigType")
    if config_type is not None:
        config_type = config_type.text.upper()
    if config_type in config_types():        
        name_node = node.find("Name")
        if name_node is None:
            name_node = ET.SubElement(node, "Name")
            name_node.text = ""
        file_name = node.find("FileName")
        if file_name is not None:
            ft = file_name.text
            if ft is None:
                ft = ""
            file_name = Path(ft).stem
        name_node.text = unique_namer.get_unique_name(name_node.text, config_type, file_name)
    for child in list(node):
        ensure_unique_identifiers_in_subtree(child, unique_namer)


def prepare_cfg_file_unique_names(file_path):
        if not file_path.exists():
            print(f"Cannot find {file_path}")
            return
        tree = ET.parse(file_path)
        root = tree.getroot()
        unique_namer = UniqueNamer()
        if root is None:
            return 
        ensure_unique_identifiers_in_subtree(root, unique_namer)
        tree.write(file_path)

################################################################################################################################



def parse_float_node(node, query, default_value = 0.0):
    value = default_value
    if node.find(query) is not None:
        value = float(node.find(query).text)
    return value



class Transform:
    """
    Parses an xml tree node for transform operations, stores them and can apply them to a blender object.
    """
    def __init__(self, loc = (0,0,0), rot = (1,0,0,0), sca = (1,1,1), anno_coords = True):
        self.location = loc
        self.rotation = rot
        self.scale = sca
        self.anno_coords = anno_coords


    def convert_to_blender_coords(self):
        if not self.anno_coords:
            return
        self.location = (-self.location[0], -self.location[2], self.location[1])
        self.rotation = (self.rotation[0], self.rotation[1], self.rotation[3], -self.rotation[2])
        self.scale = (self.scale[0], self.scale[2], self.scale[1])
        self.anno_coords = False

    def convert_to_anno_coords(self):
        if self.anno_coords:
            return      
        self.location = (-self.location[0], self.location[2], -self.location[1])
        self.rotation = (self.rotation[0], self.rotation[1], -self.rotation[3], self.rotation[2])
        self.scale = (self.scale[0], self.scale[2], self.scale[1])
        self.anno_coords = True
        

    def parse_position(self, node):
        x = parse_float_node(node, "Position.x")
        y = parse_float_node(node, "Position.y")
        z = parse_float_node(node, "Position.z")
        if parse_float_node(node, "Position", None) is not None:
            value = parse_float_node(node, "Position")
            return (value, value, value)
        return (x, y, z)

    def parse_rotation(self, node):
        x = parse_float_node(node, "Rotation.x")
        y = parse_float_node(node, "Rotation.y")
        z = parse_float_node(node, "Rotation.z")
        w = parse_float_node(node, "Rotation.w", 1.0)
        return (w,x, y, z)
    

    def parse_scale(self, node):
        x = parse_float_node(node, "Scale.x", 1.0)
        y = parse_float_node(node, "Scale.y", 1.0)
        z = parse_float_node(node, "Scale.z", 1.0)
        if parse_float_node(node, "Scale", None) is not None:
            value = parse_float_node(node, "Scale")
            return (value, value, value)
        return (x, y, z)
    
    def mirror_mesh(self, object):
        if not object.data:
            return
        for v in object.data.vertices:
            v.co.x *= -1.0
    
    def apply_to(self, object):
        if self.anno_coords:
            self.convert_to_blender_coords()
        self.mirror_mesh(object)
        object.location = self.location
        object.rotation_mode = "QUATERNION"
        object.rotation_quaternion = self.rotation
        object.scale = self.scale

    
    @classmethod
    def from_transformer_node(cls, transformer_node):
        self = Transform()
        if transformer_node is None:
            return self
        self.location = self.parse_position(transformer_node)
        self.rotation = self.parse_rotation(transformer_node)
        self.scale = self.parse_scale(transformer_node)
        self.anno_coords = True
        return self

        

class Material:
    """
    Can be created from an xml material node. Stores with diffuse, normal and metal texture paths and can create a corresponding blender material from them.
    Uses a cache to avoid creating the exact same blender material multiple times when loading just one .cfg 
    """
    materialCache = {}
    def __init__(self):
        self.diff_path = None
        self.norm_path = None
        self.metal_path = None
        self.node = None
        self.name = "Unnamed Material"
    @classmethod
    def from_material_node(cls, material_node):
        self = Material()
        name_node = material_node.find("Name")
        if name_node is not None:
            self.name = name_node.text
        if material_node.find("cModelDiffTex") is not None:
            diff_path = material_node.find("cModelDiffTex").text
            self.diff_path = diff_path
        if material_node.find("cModelNormalTex") is not None:
            norm_path = material_node.find("cModelNormalTex").text
            self.norm_path = norm_path
        if material_node.find("cModelMetallicTex") is not None:
            metal_path = material_node.find("cModelMetallicTex").text
            self.metal_path = metal_path
        self.node = material_node
        return self
    @classmethod
    def from_filepaths(cls, name, diff_path, norm_path, metal_path):
        self = Material()
        self.name = name
        if diff_path:
            self.diff_path = diff_path
        if norm_path: 
            self.norm_path = norm_path
        if metal_path:
            self.metal_path = metal_path
        return self

    def get_material_cache_key(self):
        return (self.name, self.diff_path, self.norm_path, self.metal_path)        
    def as_blender_material(self):
        if self.get_material_cache_key() in Material.materialCache:
            return Material.materialCache[self.get_material_cache_key()]
        if self.name is None:
            self.name = "Material"
        material = bpy.data.materials.new(name=self.name)
        material.use_nodes = True
        bsdf = material.node_tree.nodes["Principled BSDF"]
        
        diff_img = get_image(self.diff_path)
        if diff_img is not None:
            texImage_diff = material.node_tree.nodes.new('ShaderNodeTexImage')
            texImage_diff.image = diff_img
            material.node_tree.links.new(bsdf.inputs['Base Color'], texImage_diff.outputs['Color'])
            material.node_tree.links.new(bsdf.inputs['Alpha'], texImage_diff.outputs['Alpha'])
        norm_img = get_image(self.norm_path)
        if norm_img is not None:
            texImage_norm = material.node_tree.nodes.new('ShaderNodeTexImage')
            texImage_norm.image = norm_img
            seperateRGB = material.node_tree.nodes.new("ShaderNodeSeparateRGB")
            
            material.node_tree.links.new(seperateRGB.inputs['Image'], texImage_norm.outputs['Color'])
            combineRGB = material.node_tree.nodes.new(type="ShaderNodeCombineRGB")
            material.node_tree.links.new(combineRGB.inputs['R'], seperateRGB.outputs['R'])
            material.node_tree.links.new(combineRGB.inputs['G'], seperateRGB.outputs['G'])
            combineRGB.inputs[2].default_value = 1
            
            normal_node = material.node_tree.nodes.new("ShaderNodeNormalMap")
            material.node_tree.links.new(normal_node.inputs['Color'], combineRGB.outputs['Image'])

            material.node_tree.links.new(bsdf.inputs['Normal'], normal_node.outputs['Normal'])
            
            invertGlossy = material.node_tree.nodes.new("ShaderNodeMath")
            invertGlossy.operation = 'SUBTRACT'
            invertGlossy.inputs[0].default_value = 1
            material.node_tree.links.new(invertGlossy.inputs[1], texImage_norm.outputs['Alpha'])
            material.node_tree.links.new(bsdf.inputs['Roughness'], invertGlossy.outputs['Value'])
        metal_img = get_image(self.metal_path)
        if metal_img is not None:
            texImage_metal = material.node_tree.nodes.new('ShaderNodeTexImage')
            texImage_metal.image = metal_img
            rgbToBW = material.node_tree.nodes.new("ShaderNodeRGBToBW")
            material.node_tree.links.new(rgbToBW.inputs["Color"], texImage_metal.outputs['Color'])
            material.node_tree.links.new(bsdf.inputs['Metallic'], rgbToBW.outputs['Val'])
        material.blend_method = "CLIP"

        #Store all kinds of properties for export
        if self.node is not None:
            for prop in material_properties():
                value_node = self.node.find(prop)
                if value_node is not None:
                    material[prop] = value_node.text


        Material.materialCache[self.get_material_cache_key()] = material
        return material
    
###################################################################################################################



def get_first_or_none(list):
    if list:
        return list[0]
    return None
def get_image(texture_path):
    if (texture_path is None):
        return None
    texture_path = Path(texture_path)
    texture_path = Path(texture_path.parent, texture_path.stem + "_0.dds")
    png_file = texture_path.with_suffix(".png")
    image = bpy.data.images.get(str(png_file), None)
    if image is not None:
        return image
    fullpath = add_rda_path_prefix(texture_path)
    png_fullpath = add_rda_path_prefix(png_file)
    if png_fullpath.exists():
        image = bpy.data.images.load(str(png_fullpath))
        return image
    if ImportExportAnnoCfgPreferences.get_path_to_texconv().exists():
        if fullpath.exists():
            subprocess.call(f"\"{ImportExportAnnoCfgPreferences.get_path_to_texconv()}\" -ft PNG -sepalpha -y -o \"{fullpath.parent}\" \"{fullpath}\"")
            if png_fullpath.exists():
                image = bpy.data.images.load(str(png_fullpath))
                return image
            else:
                print(f"Warning: Conversion to png failed {png_fullpath} does not exist.")
                return None
    print(f"Warning: Cannot find image: {texture_path}")
    return None


def prop_container_properties():
    return ["VariationEnabled", "VariationProbability", "AllowYScale"]

def prop_properties():
    return ["Flags", "FileName"]

def file_properties():
    return ["FileName", "AdaptTerrainHeight"]

def model_properties():
    return ["FileName", "IgnoreRuinState"]


def material_properties():
    return ["ShaderID", "VertexFormat", "NumBonesPerVertex", "METALLIC_TEX_ENABLED", "cModelMetallicTex", "cUseTerrainTinting", "SEPARATE_AO_TEXTURE", \
        "cSeparateAOTex", "Common", "DIFFUSE_ENABLED", "cModelDiffTex", "NORMAL_ENABLED", "cModelNormalTex", "cDiffuseColor.r", "cDiffuseColor.g", \
        "cDiffuseColor.b", "cTexScrollSpeed", "DYE_MASK_ENABLED", "HEIGHT_MAP_ENABLED", "cHeightMap", "cParallaxScale", "PARALLAX_MAPPING_ENABLED", \
        "SELF_SHADOWING_ENABLED", "WATER_CUTOUT_ENABLED", "TerrainAdaption", "ADJUST_TO_TERRAIN_HEIGHT", "VERTEX_COLORED_TERRAIN_ADAPTION", \
        "ABSOLUTE_TERRAIN_ADAPTION", "Environment", "cUseLocalEnvironmentBox", "cEnvironmentBoundingBox.x", "cEnvironmentBoundingBox.y", "cEnvironmentBoundingBox.z", \
        "cEnvironmentBoundingBox.w", "Glow", "GLOW_ENABLED", "cEmissiveColor.r", "cEmissiveColor.g", "cEmissiveColor.b", "NIGHT_GLOW_ENABLED", \
        "cNightGlowMap", "WindRipples", "WIND_RIPPLES_ENABLED", "cWindRippleTex", "cWindRippleTiling", "cWindRippleSpeed", "cWindRippleNormalIntensity", \
        "cWindRippleMeshIntensity", "DisableReviveDistance", "cGlossinessFactor", "cOpacity"]

def particle_properties():
    return ["FileName", "TimeScale", "WindImpact", "ReceiveShadows", "SoftParticlesEnabled", "EarlyPass", "IsEmitterBound", "UseDepthBias", \
        "AdaptTerrainHeight", "DelayFadeOut", "AlwaysVisible", "DarkenAtNight", "Color/x", "Color/y", "Color/z", "TextureAtlas"]

def ifo_data_properties(tag):
    return {"Sequence":["Id", "Duration", "Looped", "Speed"]}[tag]

def cf7_dummy_properties():
    return ["HeightAdaptationMode"]


def ifo_empty_objects():
    return ["Sequence"]

def ifo_cube_objects():
    return ["BoundingBox", "MeshBoundingBox", "IntersectBox", "Dummy", ]
def ifo_plane_objects():
    return ["BuildBlocker", "FeedbackBlocker", "UnevenBlocker"]



class ExportAnnoCfg(Operator, ExportHelper):
    """Exports the selected MAIN_FILE into a .cfg Anno file. Check the export ifo box to also create the .ifo/.cf7 file."""
    bl_idname = "export.anno_cfg_files" 
    bl_label = "Export Anno .cfg Files"

    # ImportHelper mixin class uses this
    filename_ext = ".cfg"

    filter_glob: StringProperty(
        default="*.cfg",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    also_export_ifo: BoolProperty(
        name="Export IFO",
        description="Also writes an .ifo file of the same name.",
        default=True,
    )
    also_export_cf7: BoolProperty(
        name="Export cf7",
        description="Also writes an .cf7 file of the same name. ONLY works when you've imported the file with an .cf7 file.",
        default=True,
    )
    prefer_safe_over_cf7: BoolProperty(
        name="Prefer s.a.f.e. over cf7",
        description="Prefer simple anno feedback encoding over cf7",
        default=True,
    )

    def execute(self, context):
        if not context.active_object:
            self.report({'ERROR'}, f"MAIN_FILE Object needs to be selected. CANCELLED")
            return {'CANCELLED'}
        self.main_obj = context.active_object
        if not self.main_obj.name.startswith("MAIN_FILE"):
            self.report({'ERROR'}, f"MAIN_FILE Object needs to be selected. CANCELLED")
            return {'CANCELLED'}
        print("EXPORTING", self.main_obj.name, "to", self.filepath)
        self.blueprint_filepath = add_rda_path_prefix(self.main_obj["FileName"])

        if not self.blueprint_filepath.exists():
            self.report({'ERROR'}, f"Missing blueprint file: {self.blueprint_filepath} CANCELLED")
            return {'CANCELLED'}
        

        self.initialize_child_map()
        self.export_object_set = set()
        self.add_object_to_export_set(self.main_obj)

        tree = ET.parse(self.blueprint_filepath)
        self.root = tree.getroot()
        

        for node in list(self.root):
            self.remove_nonexisting_objects(node, self.root)




        self.export_object(self.main_obj)
        
        ET.indent(tree, space="", level=0)
        tree.write(self.filepath)
        self.report({'INFO'}, 'cfg export completed')

        if self.also_export_ifo:
            for obj in self.children_by_object[self.main_obj.name]:
                if self.get_object_config_type(obj) == "IFOFILE":
                    self.export_ifo(obj, Path(self.filepath).with_suffix(".ifo"))
                    break
        if self.also_export_cf7:
            for obj in self.children_by_object[self.main_obj.name]:
                if self.get_object_config_type(obj) == "CF7FILE":
                    if self.prefer_safe_over_cf7:
                        self.export_safe_file(obj, Path(self.filepath).with_suffix(".xml"))
                    else:
                        self.export_cf7_file(obj, Path(self.filepath).with_suffix(".cf7"))
                    break

        self.report({'INFO'}, 'Export completed!')
        return {'FINISHED'}

    # If the queried node does not exists, creates it (and returns it). Query can only be of the form A/B/C etc.
    def find_or_create(self, parent, simple_query):
        parts = simple_query.split("/", maxsplit = 1)
        query = parts[0]
        queried_node = parent.find(query)
        if queried_node is None:
            queried_node = ET.SubElement(parent, query)
        if len(parts) > 1:
            return self.find_or_create(queried_node, parts[1])
        return queried_node
    
    def add_properties(self, obj, node):
        for prop, value in obj.items():
            if prop in ["_RNA_UI"]: #weird properties that blender seems to do on its own.
                continue
            if prop in ["GroupName"]: #for technical reasons
                continue
            self.find_or_create(node, prop).text = str(value)

    def format_float(self, value):
        return "{:.6f}".format(value)

    def add_transform_to_node(self, obj, node):
        scale_node = node.find("Scale")
        if scale_node is not None:
            node.remove(scale_node)
        scale_component = node.find("Scale.x")
        if scale_component is not None:
            node.remove(scale_component)
        scale_component = node.find("Scale.y")
        if scale_component is not None:
            node.remove(scale_component)
        scale_component = node.find("Scale.z")
        if scale_component is not None:
            node.remove(scale_component)

        transform = Transform(obj.location, obj.rotation_quaternion, obj.scale, anno_coords = False)
        transform.convert_to_anno_coords()
        self.find_or_create(node, "Position.x").text = self.format_float(transform.location[0])
        self.find_or_create(node, "Position.y").text = self.format_float(transform.location[1])
        self.find_or_create(node, "Position.z").text = self.format_float(transform.location[2]) #blender y is inverted

        self.find_or_create(node, "Rotation.x").text = self.format_float(transform.rotation[1])
        self.find_or_create(node, "Rotation.y").text = self.format_float(transform.rotation[2])
        self.find_or_create(node, "Rotation.z").text = self.format_float(transform.rotation[3])
        self.find_or_create(node, "Rotation.w").text = self.format_float(transform.rotation[0])
        if self.get_object_config_type(obj) in ["PROP"]: #which ones allow for xyz scale???
            self.find_or_create(node, "Scale.x").text = self.format_float(transform.scale[0])
            self.find_or_create(node, "Scale.y").text = self.format_float(transform.scale[1])
            self.find_or_create(node, "Scale.z").text = self.format_float(transform.scale[2])
        else:
            scale_values = set([obj.scale[0], obj.scale[1], obj.scale[2]])
            if len(scale_values) > 1:
                self.report({'INFO'}, f"WARNING: Cannot have different xyz scale values: {obj.name}")
            self.find_or_create(node, "Scale").text = self.format_float(obj.scale[0])
    

    #maybe should use query like this for transform Transformer/Config[ConfigType="ORIENTATION_TRANSFORM"] to not get color transforms...
    def export_transform_to_orientation_transform_node(self, obj, node):
        transform_config_node = node.find("Transformer/Config[ConfigType='ORIENTATION_TRANSFORM']")
        if transform_config_node is None:
            transformer_node = self.find_or_create(node, "Transformer")
            transform_config_node = ET.SubElement(transformer_node, "Config")
            ET.SubElement(transform_config_node, "ConfigType").text = "ORIENTATION_TRANSFORM"
            ET.SubElement(transform_config_node, "Conditions").text = "0"
        self.add_transform_to_node(obj, transform_config_node)

    def export_propcontainer(self, obj, node):
        if node is None: #create new propcontainer in root/propcontainers
            propcontainer_container_node = self.find_or_create(self.root, "Propcontainers")
            node = ET.SubElement(propcontainer_container_node, "Config")
        self.find_or_create(node, "Props")
        self.find_or_create(node, "Name").text = obj.name
        self.find_or_create(node, "ConfigType").text = "PROPCONTAINER"
        #First I need an example that this is actually allowed.
        #self.export_transform_to_orientation_transform_node(obj, node)
        self.add_properties(obj, node)

    def export_prop(self, obj, node):
        if node is None: #create new prop in root/propcontainers/propcontainer/props
            propcontainer_obj = obj.parent
            propcontainer_node = self.get_node_by_name(propcontainer_obj.name)
            props_node = propcontainer_node.find("Props")
            node = ET.SubElement(props_node, "Config")
        self.find_or_create(node, "ConfigType").text = "PROP"
        self.find_or_create(node, "Name").text = obj.name
        self.add_transform_to_node(obj, node)
        self.add_properties(obj, node)

    def export_particle(self, obj, node):
        if node is None: #create new particle in root/particles
            particles_node = self.find_or_create(self.root, "Particles")
            node = ET.SubElement(particles_node, "Config")
        self.find_or_create(node, "ConfigType").text = "PARTICLE"
        self.find_or_create(node, "Name").text = obj.name
        self.export_transform_to_orientation_transform_node(obj, node)
        self.add_properties(obj, node)
        

    def export_file(self, obj, node):
        if node is None: #create new file in root/files
            files_node = self.find_or_create(self.root, "Files")
            node = ET.SubElement(files_node, "Config")
        self.find_or_create(node, "ConfigType").text = "FILE"
        self.find_or_create(node, "Name").text = obj.name
        self.export_transform_to_orientation_transform_node(obj, node)
        self.add_properties(obj, node)

    def export_material(self, blender_material_obj, node):
        self.find_or_create(node, "ConfigType").text = "MATERIAL"
        self.find_or_create(node, "Name").text = blender_material_obj.name
        self.add_properties(blender_material_obj, node)
        #Try to find user changes to material: For simplicity, lets assume they follow the XXX_type_0.xxx naming convention.
        #Todo: Use the shader graph to find out which ones are actually connected to which outputs.
        for shader_node in blender_material_obj.node_tree.nodes:
            if shader_node.type=='TEX_IMAGE':
                filepath_full = bpy.path.abspath(shader_node.image.filepath, library=shader_node.image.library)
                texture_path = Path(filepath_full).relative_to(ImportExportAnnoCfgPreferences.get_path_to_rda_folder())
                stem = texture_path.stem
                if stem.endswith("_0"):
                    stem = stem[:-2]
                texture_path = Path(texture_path.parent, stem + ".psd")
                if stem.endswith("_diff"):
                    self.find_or_create(node, "cModelDiffTex").text = str(texture_path)
                if stem.endswith("_norm"):
                    self.find_or_create(node, "cModelNormalTex").text = str(texture_path)
                if stem.endswith("_metal"):
                    self.find_or_create(node, "cModelMetallicTex").text = str(texture_path)
                if stem.endswith("_mask"):
                    self.find_or_create(node, "cNightGlowMap").text = str(texture_path)
                if stem.endswith("_height"):
                    self.find_or_create(node, "cHeightMap").text = str(texture_path)
                    

    def export_model(self, obj, node):
        if node is None: 
            models_node = self.find_or_create(self.root, "Models")
            node = ET.SubElement(models_node, "Config")
        self.find_or_create(node, "ConfigType").text = "MODEL"
        self.find_or_create(node, "Name").text = obj.name
        self.export_transform_to_orientation_transform_node(obj, node)
        self.add_properties(obj, node)
        materials_node = node.find("Materials")
        if materials_node:
            node.remove(materials_node)
        materials_node = ET.SubElement(node, "Materials")
        for blender_material_slot in obj.material_slots:
            blender_material = blender_material_slot.material
            if blender_material is None:
                print("Ignoring invalid material")
                continue
            material_node = ET.SubElement(materials_node, "Config")
            self.export_material(blender_material, material_node)

        #Extents
    def export_decal(self, obj, node):
        if node is None:
            self.report({"INFO"}, f"Warning: Cannot create new decals because idk why you'd want that. Ignoring {obj.name}")
            return
        # If new decals are supported
        # self.find_or_create(node, "ConfigType").text = "FILE"
        # self.find_or_create(node, "Name").text = obj.name
        extentx = node.find("Extents.x")
        if extentx is not None:
            extentx.text = self.format_float(-obj.scale[0])
        extenty = node.find("Extents.z")
        if extenty is not None:
            extenty.text = self.format_float(-obj.scale[1])
        self.add_properties(obj, node)

        materials_node = node.find("Materials")
        if materials_node:
            node.remove(materials_node)
        materials_node = ET.SubElement(node, "Materials")
        for blender_material_slot in obj.material_slots:
            blender_material = blender_material_slot.material
            if blender_material is None:
                print("Ignoring invalid material for decal")
                continue
            material_node = ET.SubElement(materials_node, "Config")
            self.export_material(blender_material, material_node)


    def export_object(self, obj):
        config_type = self.get_object_config_type(obj)
        node = None
        if config_type is not None:
            node = self.get_node_by_name(obj.name)
            if config_type == "PROPCONTAINER":
                self.export_propcontainer(obj, node)
            if config_type == "PROP":
                self.export_prop(obj, node)
            if config_type == "PARTICLE":
                self.export_particle(obj, node)
            if config_type == "FILE":
                self.export_file(obj, node)
                #We cannot export the children of a file obj into this file.
                return 
            if config_type == "MODEL":
                self.export_model(obj, node)
            if config_type == "DECAL":
                self.export_decal(obj, node)

            
        if obj.name not in self.children_by_object:
            return
        for child in self.children_by_object[obj.name]:
            if self.get_object_config_type(child) in ["IFOFILE", "CF7FILE"]:
                continue
            self.export_object(child)

    def get_text(self, node, query, default = ""):
        if node.find(query) is not None:
            return node.find(query).text
        return default
    def remove_nonexisting_objects(self, node, parent_node):
        config_type = self.get_text(node, "ConfigType").upper()
        if config_type in ["MODEL", "FILE", "PROPCONTAINER", "PROP", "PARTICLE", "DECAL"]:
            name = self.get_text(node, "Name")
            if name not in self.export_object_set:
                parent_node.remove(node)
                return
        for child in list(node):
            self.remove_nonexisting_objects(child, node)


    def export_ifo_cube(self, obj, node):
        self.find_or_create(node, "Name").text = obj["Name"]

        transform = Transform(obj.location, obj.rotation_quaternion, obj.scale, anno_coords = False)
        transform.convert_to_anno_coords()

        self.find_or_create(node, "Position/xf").text = self.format_float(transform.location[0])
        self.find_or_create(node, "Position/yf").text = self.format_float(transform.location[1])
        self.find_or_create(node, "Position/zf").text = self.format_float(transform.location[2])

        self.find_or_create(node, "Extents/xf").text = self.format_float(transform.scale[0])
        self.find_or_create(node, "Extents/yf").text = self.format_float(transform.scale[1])
        self.find_or_create(node, "Extents/zf").text = self.format_float(transform.scale[2])

        self.find_or_create(node, "Rotation/wf").text = self.format_float(transform.rotation[0])
        self.find_or_create(node, "Rotation/xf").text = self.format_float(transform.rotation[1])
        self.find_or_create(node, "Rotation/yf").text = self.format_float(transform.rotation[2])
        self.find_or_create(node, "Rotation/zf").text = self.format_float(transform.rotation[3])
    
    def export_ifo_plane(self, obj, node):
        if "Name" in obj.keys():
            self.find_or_create(node, "Name").text = obj["Name"]
        for vert in obj.data.vertices:
            position_node = ET.SubElement(node, "Position")
            ET.SubElement(position_node, "xf").text = self.format_float(vert.co.x)
            ET.SubElement(position_node, "zf").text = self.format_float(-vert.co.y)

    def export_ifo_empty(self, obj, node):
        for prop in ifo_data_properties(obj["Tag"]):
            if prop in obj.keys():
                ET.SubElement(node, prop).text = obj[prop]


    def export_ifo(self, ifo_obj, ifo_filepath):
        ifotree = ET.ElementTree(element = ET.Element("Info"))
        root = ifotree.getroot()
        self.add_properties(ifo_obj, root)
        for obj in self.children_by_object[ifo_obj.name]:
            if "Tag" not in obj.keys():
                continue
            node = ET.SubElement(root, obj["Tag"])
            if obj["Tag"] in ifo_cube_objects():
                self.export_ifo_cube(obj, node)
            if obj["Tag"] in ifo_plane_objects():
                self.export_ifo_plane(obj, node)
            if obj["Tag"] in ifo_empty_objects():
                self.export_ifo_empty(obj, node)
        ET.indent(ifotree, space="", level=0)
        ifotree.write(ifo_filepath)


    def export_cf7_dummy_object(self, obj, node):
        if node is None:
            self.report({'INFO'}, f"Warning, detected new cf7 object. This is not supported. Ignoring {obj.name}")
            return
        obj.rotation_mode = "QUATERNION"
        transform = Transform(obj.location, obj.rotation_quaternion, obj.scale, anno_coords = False)
        transform.convert_to_anno_coords()
        
        self.find_or_create(node, "Position/x").text = self.format_float(transform.location[0])
        self.find_or_create(node, "Position/y").text = self.format_float(transform.location[1])
        self.find_or_create(node, "Position/z").text = self.format_float(transform.location[2])

        self.find_or_create(node, "Extents/x").text = self.format_float(transform.scale[0])
        self.find_or_create(node, "Extents/y").text = self.format_float(transform.scale[1])
        self.find_or_create(node, "Extents/z").text = self.format_float(transform.scale[2])


        self.find_or_create(node, "Orientation/w").text = self.format_float(transform.rotation[0])
        self.find_or_create(node, "Orientation/x").text = self.format_float(transform.rotation[1])
        self.find_or_create(node, "Orientation/y").text = self.format_float(transform.rotation[2])
        self.find_or_create(node, "Orientation/z").text = self.format_float(transform.rotation[3])

        obj.rotation_mode = "XYZ"
        rotationZ = obj.rotation_euler.z
        self.find_or_create(node, "RotationY").text = self.format_float(rotationZ)

        self.add_properties(obj, node)

    def get_cf7_node_by_name(self,cf7root, name):
        node =  cf7root.find(f".//i/[Name=\"{name}\"]")
        return node

    def get_safe_node_by_name(self,cf7root, name):
        node =  cf7root.find(f".//Dummy/[Name=\"{name}\"]")
        return node

    def export_cf7_file(self, cf7_object, cf7_filepath): 
        cf7_blueprint_filepath = Path(cf7_object["FileName"])
        if not cf7_blueprint_filepath.exists():
            self.report({'Info'}, f"Missing cf7 blueprint file: {cf7_blueprint_filepath}")
            return
        cf7root = None
        with open(cf7_blueprint_filepath) as f:
            xml = '<cf7_imaginary_root>' + f.read() + '</cf7_imaginary_root>'
            cf7root = ET.fromstring(xml)
        cf7tree = ET.ElementTree(cf7root)
        for cf7_dummy_obj in self.children_by_object[cf7_object.name]:
            if len(cf7_dummy_obj.name.split("_")) == 1:
                print("Invalid name for ", cf7_dummy_obj.name, "ignoring")
                continue
            name = cf7_dummy_obj.name.split("_", maxsplit = 1)[1]
            node = self.get_cf7_node_by_name(cf7root, name)
            self.export_cf7_dummy_object(cf7_dummy_obj, node)
       
        #take care of the root element again
        cf7tree_string = ET.tostring(cf7root, encoding='unicode', method='xml')
        cf7tree_string = cf7tree_string.replace("</cf7_imaginary_root>", "").replace("<cf7_imaginary_root>","")
        with open(cf7_filepath, 'w') as f:
            f.write(cf7tree_string)
        if ImportExportAnnoCfgPreferences.get_path_to_fc_converter().exists():
            subprocess.call(f"\"{ImportExportAnnoCfgPreferences.get_path_to_fc_converter()}\" -w \"{cf7_filepath}\" -y -o \"{cf7_filepath.with_suffix('.fc')}\"")
        return

    def export_safe_dummy_object(self, obj, node, dummy_groups_node):
        if node is None:
            group_name = obj.name.split("_", maxsplit = 1)[1]
            if "GroupName" in obj and str(obj["GroupName"]) != "":
                group_name = str(obj["GroupName"])

            group_node = dummy_groups_node.find(f".//DummyGroup/[Name=\"{group_name}\"]")
            if group_node is None:
                group_node = ET.SubElement(dummy_groups_node, "DummyGroup")
                ET.SubElement(group_node, "Name").text = group_name
            node = ET.SubElement(group_node, "Dummy")
            ET.SubElement(node, "Name").text = obj.name.split("_", maxsplit = 1)[1]
        obj.rotation_mode = "QUATERNION"
        transform = Transform(obj.location, obj.rotation_quaternion, obj.scale, anno_coords = False)
        transform.convert_to_anno_coords()
        
        self.find_or_create(node, "Position/x").text = self.format_float(transform.location[0])
        self.find_or_create(node, "Position/y").text = self.format_float(transform.location[1])
        self.find_or_create(node, "Position/z").text = self.format_float(transform.location[2])

        self.find_or_create(node, "Extents/x").text = self.format_float(transform.scale[0])
        self.find_or_create(node, "Extents/y").text = self.format_float(transform.scale[1])
        self.find_or_create(node, "Extents/z").text = self.format_float(transform.scale[2])

        self.find_or_create(node, "Orientation/w").text = self.format_float(transform.rotation[0])
        self.find_or_create(node, "Orientation/x").text = self.format_float(transform.rotation[1])
        self.find_or_create(node, "Orientation/y").text = self.format_float(transform.rotation[2])
        self.find_or_create(node, "Orientation/z").text = self.format_float(transform.rotation[3])

        obj.rotation_mode = "XYZ"
        rotationZ = obj.rotation_euler.z
        self.find_or_create(node, "RotationY").text = self.format_float(rotationZ)

        self.add_properties(obj, node)

    def export_safe_file(self, cf7_object, safe_filepath): 
        cf7_blueprint_filepath = Path(cf7_object["FileName"])
        tree = None
        root = None
        if not cf7_blueprint_filepath.exists() or cf7_blueprint_filepath.suffix != ".xml":
            root = ET.Element("SimpleAnnoFeedbackEncoding")
            tree = ET.ElementTree(root)
            ET.SubElement(root, "FeedbackConfigs")
            ET.SubElement(root, "GUIDNames")
        else:
            tree = ET.parse(str(cf7_blueprint_filepath))
            root = tree.getroot()
        dummy_groups_node = self.find_or_create(root, "DummyGroups")
        for group_node in list(dummy_groups_node): #clean all dummies so that one can delete...
            dummy_groups_node.remove(group_node)
        for cf7_dummy_obj in self.children_by_object[cf7_object.name]:
            if len(cf7_dummy_obj.name.split("_")) == 1:
                print("Invalid name for ", cf7_dummy_obj.name, "ignoring")
                continue
            name = cf7_dummy_obj.name.split("_", maxsplit = 1)[1]
            node = self.get_safe_node_by_name(root, name)
            self.export_safe_dummy_object(cf7_dummy_obj, node, dummy_groups_node)
        ET.indent(tree, space="\t", level=0)
        tree.write(safe_filepath)



    def get_object_config_type(self, obj):
        return obj.name.split("_")[0]
        # for config_type in config_types():
        #     if cleaned_name.startswith(config_type):
        #         return config_type
        # return None

    def add_object_to_export_set(self, obj):
        self.export_object_set.add(obj.name)
        if obj.name not in self.children_by_object:
            return
        for child in self.children_by_object[obj.name]:
            self.add_object_to_export_set(child)

    def initialize_child_map(self):
        self.children_by_object = {}
        for obj in bpy.data.objects:
            if obj.parent is not None:
                if obj.parent.name in self.children_by_object:
                    self.children_by_object[obj.parent.name].append(obj)
                else:
                    self.children_by_object[obj.parent.name] = [obj]

    def get_node_by_name(self, name):
        node = self.root.find(f".//Config/[Name=\"{name}\"]")
        return node
        # return self.root.find(f".//Config/Name[text()=\"{name}\"]/..")
        


class ImportAnnoCfg(Operator, ImportHelper):
    """Parses Anno (1800) .cfg files and automatically imports and positions all models, props, particles and decals in the scene. Can also import .prp files into your scene, but you must select a parent object"""
    bl_idname = "import.anno_cfg_files" 
    bl_label = "Import Anno .cfg Files"

    # ImportHelper mixin class uses this
    filename_ext = ".cfg;.prp"

    filter_glob: StringProperty(
        default="*.cfg;*.prp",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    # load_prop_models: BoolProperty(
    #     name="Load Prop Models",
    #     description="Load Prop Models",
    #     default=True,
    # )
    load_subfiles: BoolProperty(
        name="Load Subfiles",
        description="Load Subfiles. If disabled, each file will only be represented by an empty. If enabled, all models, props subfiles etc. of the subfile will be loaded.",
        default=True,
    )
    auto_convert_rdm: BoolProperty(
        name="Auto Convert to .glb",
        description="Automatically converts all required .rdm models to .glb (if they haven't been converted already)",
        default=True,
    )
    also_import_ifo: BoolProperty(
        name="Import .ifo",
        description="Also import the .ifo file with the same name.",
        default=True,
    )
    also_import_cf7: BoolProperty(
        name="Import .cf7",
        description="Also import the .cf7 file with the same name.",
        default=True,
    )
    prefer_safe_over_cf7: BoolProperty(
        name="Prefer s.a.f.e. over cf7",
        description="Prefer simple anno feedback encoding over cf7",
        default=True,
    )

    import_as_subfile: BoolProperty(
        name="Import .cfg as Subfile",
        description="Adds the file as a FILE_ object under the selected MAIN_FILE object. Note: Some .cfgs require specific sequences in the main files ifo in order to show up in game properly.",
        default=False,
    )


    def execute(self, context):
        self.prop_data_by_filename = {}
        self.main_file_path = Path(self.filepath)
        if self.main_file_path.suffix == ".cfg":
            if not self.import_as_subfile:
                file_obj = self.import_cfg_file(self.main_file_path.relative_to(ImportExportAnnoCfgPreferences.get_path_to_rda_folder()), "MAIN_FILE_" + self.main_file_path.name)
            else:
                parent_object = context.active_object
                if parent_object is None or self.get_object_config_type(parent_object) != "MAIN":
                    self.report({"ERROR"}, "You need to select the MAIN_FILE as active object first.")
                    return {'CANCELLED'}
                name = "FILE_IMPORT_" + self.main_file_path.name
                file_obj = self.add_empty_to_scene(name, Transform(), parent_object)
                file_obj["AdaptTerrainHeight"] = 1
                file_obj = self.import_cfg_file(self.main_file_path.relative_to(ImportExportAnnoCfgPreferences.get_path_to_rda_folder()), name, Transform(), parent_object, file_obj)
            if self.also_import_ifo:
                self.import_ifo_file(self.main_file_path.with_suffix(".ifo"), file_obj)
            if self.also_import_cf7:
                if self.prefer_safe_over_cf7 and self.main_file_path.with_suffix(".xml").exists():
                    self.import_safe_file(self.main_file_path.with_suffix(".xml"), file_obj)
                else:
                    self.import_cf7_file(self.main_file_path.with_suffix(".cf7"), file_obj)
        elif self.main_file_path.suffix == ".prp":
            name = "PROP_IMPORT_" + self.main_file_path.name
            parent_object = context.active_object
            if parent_object is None or self.get_object_config_type(parent_object) != "PROPCONTAINER":
                self.report({"ERROR"}, "You need to select a parent propcontainer as active object first.")
                return {'CANCELLED'}
            self.import_single_prop(self.main_file_path, name, parent_object)
        else:
            self.report({"ERROR"}, "Invalid filetype. Only supports .cfg and .prp")
            return {'CANCELLED'}
        self.report({'INFO'}, "Import completed!")
        return {'FINISHED'}

    def add_empty_to_scene(self, name, transform, parent_object, empty_type = "SINGLE_ARROW"):
        bpy.ops.object.empty_add(type=empty_type, align='WORLD', location = (0,0,0), scale = (1,1,1))
        for obj in bpy.context.selected_objects:
            obj.name = name
            if parent_object is not None:
                obj.parent = parent_object
            
            transform.apply_to(obj)
            return obj

    def convert_to_glb(self, fullpath):
        rdm4_path = ImportExportAnnoCfgPreferences.get_path_to_rdm4()
        if self.auto_convert_rdm and rdm4_path.exists() and fullpath.exists():
            subprocess.call(f"\"{rdm4_path}\" --input \"{fullpath}\" -n --outdst \"{fullpath.parent}\"", shell = True)

    def convert_to_glb_if_required(self, data_path):
        if data_path is None:
            return None
        fullpath = add_rda_path_prefix(data_path)
        glb_fullpath = fullpath.with_suffix(".glb")
        if fullpath.exists() and not glb_fullpath.exists():
            self.convert_to_glb(fullpath)

    def add_glb_model_to_scene(self, data_path, name, materials, transform, parent_object):
        self.convert_to_glb_if_required(data_path)
        if data_path is None:
            self.report({'INFO'}, f"Missing file: Cannot find model for {name} at {data_path}.")
            return None
        
        fullpath = add_rda_path_prefix(data_path).with_suffix(".glb")

        if not fullpath.exists():
            return self.add_empty_to_scene(name, transform, parent_object)
        
        ret = bpy.ops.import_scene.gltf(filepath=str(fullpath))
        obj = bpy.context.active_object

        obj.name = name
        if parent_object is not None:
            obj.parent = parent_object
        transform.apply_to(obj)
        for i,material in enumerate(materials):
            if len(obj.data.materials) <= i:
                print(obj.name)
                print("Warning: Missing materials slot for material" ,i, "at", data_path)
                break
            obj.data.materials[i] = material.as_blender_material()
        return obj

#######################################################################################################################
    def import_ifo_cube(self,name, node, parent_object): 
        sca = (parse_float_node(node, "Extents/xf", 1.0), parse_float_node(node, "Extents/yf", 1.0), parse_float_node(node, "Extents/zf", 1.0))
        loc = (parse_float_node(node, "Position/xf"), parse_float_node(node, "Position/yf"), parse_float_node(node, "Position/zf"))
        rot = (parse_float_node(node, "Rotation/wf"), parse_float_node(node, "Rotation/xf"), parse_float_node(node, "Rotation/yf"), parse_float_node(node, "Rotation/zf"))
        bpy.ops.mesh.primitive_cube_add(location=(0,0,0))
        obj = bpy.context.active_object
        obj.display_type = 'WIRE'
        transform = Transform(loc, rot, sca, anno_coords = True)
        transform.apply_to(obj)
        if parent_object is not None: 
            obj.parent = parent_object
        obj["Tag"] = node.tag
        if self.get_text(node, "Name") != "":
            obj["Name"] = self.get_text(node, "Name")
            obj.name = "IFO_"+node.tag+"_"+self.get_text(node, "Name")
    
    def add_object_from_vertices(self, vertices):
        edges = []
        faces = [[i for i,v in enumerate(vertices)]] #leads to double vertices -> bad
        new_mesh = bpy.data.meshes.new('new_mesh')
        new_mesh.from_pydata(vertices, edges, faces)
        new_mesh.update()
        new_object = bpy.data.objects.new('new_object', new_mesh)
        bpy.context.scene.collection.objects.link(new_object)
        return new_object

    def import_ifo_plane(self, name, node, parent_object):
        if node.find("Position") is None:
            return
        vertices = []
        for pos_node in node.findall("Position"):
            x = parse_float_node(pos_node, "xf")
            y = - parse_float_node(pos_node, "zf")
            vertices.append((x,y, 0.0))
        new_object = self.add_object_from_vertices(vertices)

        new_object.name = name
        new_object["Tag"] = node.tag
        if self.get_text(node, "Name") != "":
            obj["Name"] = self.get_text(node, "Name")
        if parent_object is not None: 
            new_object.parent = parent_object
        return

    def import_ifo_empty(self, name, node, parent_object):
        obj = self.add_empty_to_scene(name, Transform(), parent_object)
        obj.name = name
        obj["Tag"] = node.tag
        for prop in ifo_data_properties(node.tag):
            self.save_as_custom_property(node, prop, obj)

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
        ifo_obj = self.add_empty_to_scene("IFOFILE", Transform(), file_obj)
        for node in list(root):
            if node: #has children
                self.import_ifo_object(node, ifo_obj)
            else: #has no children
                ifo_obj[node.tag] = node.text
        return

    def import_cf7_object(self, node, parent_object, parent_name = ""):
        name = self.get_text(node, "Name", "")
        if node.tag in ['Dummy','i']  and node.find("Position") is not None and node.find("Orientation") is not None and node.find("Extents") is not None:
            #this should be a node that defines a feedback dummy object
            sca = (parse_float_node(node, "Extents/x", 1.0), parse_float_node(node, "Extents/y", 1.0), parse_float_node(node, "Extents/z", 1.0))
            loc = (parse_float_node(node, "Position/x"), parse_float_node(node, "Position/y"), parse_float_node(node, "Position/z"))
            # rot = (parse_float_node(node, "Orientation/w"), parse_float_node(node, "Orientation/x"), parse_float_node(node, "Orientation/y"), parse_float_node(node, "Orientation/z"))
            rot = (1,0,0,0)
            if name == "": #idk what to do with unnamed dummies
                return
            obj = self.add_empty_to_scene("CF7DUMMY_"+name, Transform(loc, rot, sca, anno_coords = True), parent_object, "ARROWS")
            obj.rotation_mode = "XYZ"
            obj.rotation_euler.z = parse_float_node(node, "RotationY")
            for attribute in cf7_dummy_properties():
                self.save_as_custom_property(node, attribute, obj)
            obj["GroupName"] = name.rsplit("_", maxsplit=1)[0]
            if parent_name != "":
                obj["GroupName"] = parent_name
            return
        for subnode in list(node):
            self.import_cf7_object(subnode, parent_object, name)


    def import_cf7_file(self, fullpath, file_obj): 
        if not fullpath.exists() and not fullpath.with_suffix(".fc").exists():
            self.report({'INFO'}, f"Missing file: {fullpath.with_suffix('.fc')}")
            return
        if not fullpath.exists() and fullpath.with_suffix(".fc").exists() and ImportExportAnnoCfgPreferences.get_path_to_fc_converter().exists():
            subprocess.call(f"\"{ImportExportAnnoCfgPreferences.get_path_to_fc_converter()}\" -r \"{fullpath.with_suffix('.fc')}\" -o \"{fullpath}\"")
        if not fullpath.exists():
            self.report({'INFO'}, f"Missing file: {fullpath}")
            return
        root = None
        with open(fullpath) as f:
            xml = '<cf7_imaginary_root>' + f.read() + '</cf7_imaginary_root>'
            root = ET.fromstring(xml)
        tree = ET.ElementTree(root)
        cf7_object = self.add_empty_to_scene("CF7FILE", Transform(), file_obj)
        cf7_object["FileName"] = str(fullpath) 
        for node in list(root):
            self.import_cf7_object(node, cf7_object)
        return

    def import_safe_file(self, fullpath, file_obj): 
        if not fullpath.exists():
            self.report({'INFO'}, f"Missing file: {fullpath}")
            return
        print("importing safexml")
        tree = ET.parse(fullpath)
        root = tree.getroot()
        safe_object = self.add_empty_to_scene("CF7FILE_SAFE", Transform(), file_obj)
        safe_object["FileName"] = str(fullpath) 
        for node in list(root):
            self.import_cf7_object(node, safe_object)
        return

    def import_cfg_file(self, data_path, name, transform = Transform(), parent_object = None, file_obj = None): 
        if data_path is None:
            return
        if file_obj is None:
            file_obj = self.add_empty_to_scene(name, transform, parent_object)
        file_obj['FileName'] = str(data_path)
        fullpath = add_rda_path_prefix(data_path)
        if not fullpath.exists():
            self.report({'INFO'}, f"Missing file: {data_path}")
            return
        if not self.load_subfiles and fullpath != self.main_file_path:
            return
        prepare_cfg_file_unique_names(fullpath)
        tree = ET.parse(fullpath)
        root = tree.getroot()
        if root is None:
            return
        models = root.find("Models")
        if models is not None:
            for model in models:
                self.import_model(model, file_obj)
        prop_containers = root.find("PropContainers")
        if prop_containers is not None:
            for prop_container in prop_containers:
                self.import_prop_container(prop_container, file_obj)
        particles = root.find("Particles")
        if particles is not None:
            for particle in particles:
                self.import_particle(particle, file_obj)
        decals = root.find("Decals")
        if decals is not None:
            for decal in decals:
                self.import_decal(decal, file_obj)
        files = root.find("Files")
        if files is not None:
            for file in files:
                self.import_subfile(file, file_obj)
        return file_obj

    def get_text(self, node, query, default = ""):
        if node.find(query) is not None:
            return node.find(query).text
        return default
    def get_transform_from_transformer_child(self, node):
        if node.find("Transformer/Config") is not None:
            return Transform.from_transformer_node(node.find("Transformer/Config"))
        return Transform()
    # Saves the value of node.find(query) in the blender object as a custom property. 
    def save_as_custom_property(self, node, query, blender_object):
        value_node = node.find(query)
        if value_node is not None:
            blender_object[query] = value_node.text

    def import_model(self, node, parent_object):
        transform = self.get_transform_from_transformer_child(node)
        imported_materials = []
        if node.find("Materials") is not None:
            for material_node in node.find("Materials"):
                material = Material.from_material_node(material_node)
                imported_materials.append(material)
        name = self.get_text(node, "Name")
        file_name = self.get_text(node, "FileName", None)
        obj = self.add_glb_model_to_scene(file_name, name, imported_materials, transform, parent_object)
        for attribute in model_properties():
            self.save_as_custom_property(node, attribute, obj)


    def import_prop_container(self, node, parent_object):
        transform = self.get_transform_from_transformer_child(node)
        name = self.get_text(node, "Name")
        prop_container_obj = self.add_empty_to_scene(name, transform, parent_object)
        props = node.find("Props")
        if props is not None:
            for prop in props:
                self.import_prop(prop, prop_container_obj)
        for attribute in prop_container_properties():
            self.save_as_custom_property(node, attribute, prop_container_obj)

    
    def get_prop_data(self, prop_data_path):
        if prop_data_path in self.prop_data_by_filename:
            return self.prop_data_by_filename[prop_data_path]
        prop_file = add_rda_path_prefix(prop_data_path)
        if not prop_file.exists():
            return (prop_data_path, None)
        propfile = open(prop_file).read()
        mesh_file_name = re.findall("<MeshFileName>(.*?)<", propfile, re.I)[0]
        diff_path = get_first_or_none(re.findall("<cModelDiffTex>(.*?)<", propfile, re.I))
        norm_path = get_first_or_none(re.findall("<cModelNormalTex>(.*?)<", propfile, re.I))
        metallic_path = get_first_or_none(re.findall("<cModelNormalTex>(.*?)<", propfile, re.I))
        material = Material.from_filepaths(prop_data_path.name, diff_path, norm_path, metallic_path)
        prop_data = (mesh_file_name, material)
        self.prop_data_by_filename[prop_data_path] = prop_data
        return prop_data

    def import_single_prop(self, full_prop_file_path, name, parent_object, transform = Transform()):
        prop_obj = None
        if full_prop_file_path.exists() and full_prop_file_path.suffix == ".prp":
            model_file_name, material = self.get_prop_data(full_prop_file_path)
            prop_obj = self.add_glb_model_to_scene(model_file_name, name, [material], transform, parent_object)
        else:
            prop_obj = self.add_empty_to_scene(name, transform, parent_object)
        prop_obj["FileName"] = str(full_prop_file_path.relative_to(ImportExportAnnoCfgPreferences.get_path_to_rda_folder()))
        prop_obj["Flags"] = "0"
    
    def import_prop(self, node, parent_object):
        transform = Transform.from_transformer_node(node) #stored directly in prop
        name = self.get_text(node, "Name")
        prop_data_path = self.get_text(node, "FileName")
        full_prop_file_path = add_rda_path_prefix(Path(prop_data_path))
        prop_obj = None
        if full_prop_file_path.exists() and full_prop_file_path.suffix == ".prp":
            model_file_name, material = self.get_prop_data(full_prop_file_path)
            prop_obj = self.add_glb_model_to_scene(model_file_name, name, [material], transform, parent_object)
        else:
            prop_obj = self.add_empty_to_scene(name, transform, parent_object)
        for attribute in prop_properties():
            self.save_as_custom_property(node, attribute, prop_obj)
        
    def import_particle(self, node, parent_object):
        transform = self.get_transform_from_transformer_child(node)
        name = self.get_text(node, "Name")
        file_name = self.get_text(node, "FileName")
        if file_name == "":
            return
        particle_obj = self.add_empty_to_scene(name, transform, parent_object, "SPHERE")
        for attribute in particle_properties():
            self.save_as_custom_property(node, attribute, particle_obj)

    def import_decal(self, node, parent_object):
        transform = self.get_transform_from_transformer_child(node)
        name = self.get_text(node, "Name")
        materials = []
        if node.find("Materials") is not None:
            for material_node in node.find("Materials"):
                material = Material.from_material_node(material_node)
                materials.append(material)
        # Let's assume that there's only one material...
        if not materials:
            return
        material = materials[0]
        
        x = parse_float_node(node, "Extents.x", 0.0)
        y = parse_float_node(node, "Extents.y", 0.0)
        z = parse_float_node(node, "Extents.z", 0.0)
        if node.find("Extents") is not None:
            x = parse_float_node(node, "Extents")
            y = x
            z = x
        #Why do we even have a value for the height???
        bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, align='WORLD', location=(0,0,0), scale=(1,1,1))
        obj = bpy.context.active_object
        obj.scale[0] = -x
        obj.scale[1] = -z
        if parent_object is not None:
            obj.parent = parent_object
        obj.name = name
        obj.data.materials.append(material.as_blender_material())

    def import_subfile(self, node, parent_object):
        transform = self.get_transform_from_transformer_child(node)
        file_path = self.get_text(node, "FileName")
        name = self.get_text(node, "Name")
        file_obj = self.add_empty_to_scene(name, transform, parent_object)
        for prop in file_properties():
            self.save_as_custom_property(node, prop, file_obj)
        self.import_cfg_file(file_path, name, transform, parent_object, file_obj)
            

    def get_object_config_type(self, obj):
        return obj.name.split("_")[0]

                       
def menu_func_import(self, context):
    self.layout.operator(ImportAnnoCfg.bl_idname, text="Anno (.cfg, .prp)")

def menu_func_export(self, context):
    self.layout.operator(ExportAnnoCfg.bl_idname, text="Anno (.cfg)")


def register():
    bpy.utils.register_class(ImportExportAnnoCfgPreferences)
    bpy.utils.register_class(ImportAnnoCfg)
    bpy.utils.register_class(ExportAnnoCfg)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ImportExportAnnoCfgPreferences)
    bpy.utils.unregister_class(ImportAnnoCfg)
    bpy.utils.unregister_class(ExportAnnoCfg)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

# prepare_cfg_file_unique_names(cfg_file)
