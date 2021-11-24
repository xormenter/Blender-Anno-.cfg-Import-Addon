
"""
Parses Anno (1800) .cfg files and automatically imports and positions all models, props, particles and decals in the scene.
When available, the corresponding .glb file is used, otherwise a named empty serves as placeholder.
If the necessary textures can be found in .png format, they are used for the material.
"""

import bpy
bl_info = {
    "name": "Annocfg",
    "version": (1, 0),
    "blender": (2, 93, 0),
    "category": "Import-Export",
}
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator, AddonPreferences

import xml.etree.ElementTree as ET
import os
import re
import subprocess
import mathutils

class ImportAnnoCfgPreferences(AddonPreferences):
    bl_idname = __name__

    path_to_rda_folder : StringProperty(
        name = "Path to rda Folder",
        description = "Path where you unpacked the Anno rda files. Should contain the data folder.",
        subtype='FILE_PATH',
        default = "",
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Path Properties")
        layout.prop(self, "path_to_rda_folder")

def get_full_path(p):
    return os.path.join(bpy.context.preferences.addons[__name__].preferences.path_to_rda_folder, p)

def change_extension(p, new_extension):
    return os.path.splitext(p)[0] + new_extension

def get_file_basename(p):
    return os.path.basename(p)

def has_file_type(p, extension):
    return os.path.splitext(p)[1] == extension

def parse_float_node(node, query, default_value = 0.0):
    value = default_value
    if node.find(query) is not None:
        value = float(node.find(query).text)
    return value

def parse_name(node):
    name = node.find("Name")
    if (name is not None):
        return name.text
    return None

def get_first_or_none(list):
    if list:
        return list[0]
    return None
    
def get_collection(collectionName):
    if bpy.data.collections.get(collectionName) is None:
        collection = bpy.data.collections.new(collectionName)
        
        bpy.context.scene.collection.children.link(collection)
        return collection
    else:
        return bpy.data.collections[collectionName]

def get_image(texture_path):
    if (texture_path is None):
        return None
    image = bpy.data.images.get(texture_path, None)
    if image is not None:
        return image
    elif (os.path.exists(get_full_path(texture_path))):
            image = bpy.data.images.load(get_full_path(texture_path))
            return image
    print("Warning: Cannot find image: ", texture_path, "\n")
    return None

"""
Parses an xml tree node for transform operations, stores them and can apply them to a blender object.
"""
class Transform:
    def __init__(self):
        self.location = (0,0,0)
        self.rotation = (1,0,0,0)
        self.scale = (1,1,1)



    def parse_position(self, node):
        x = parse_float_node(node, "Position.x")
        y = parse_float_node(node, "Position.y")
        z = parse_float_node(node, "Position.z")
        if parse_float_node(node, "Position", None) is not None:
            value = parse_float_node(node, "Position")
            return (value, -value, value)
        return (x, -z, y)

    def parse_rotation(self, node):
        x = parse_float_node(node, "Rotation.x")
        y = parse_float_node(node, "Rotation.y")
        z = parse_float_node(node, "Rotation.z")
        w = parse_float_node(node, "Rotation.w", 1.0)
        return (w,x, z, y)
    

    def parse_scale(self, node):
        x = parse_float_node(node, "Scale.x", 1.0)
        y = parse_float_node(node, "Scale.y", 1.0)
        z = parse_float_node(node, "Scale.z", 1.0)
        if parse_float_node(node, "Scale", None) is not None:
            value = parse_float_node(node, "Scale")
            return (value, value, value)
        return (x, z, y)
    @classmethod
    def from_transformer_node(cls, transformer_node):
        self = Transform()
        if transformer_node is None:
            return self
        self.location = self.parse_position(transformer_node)
        self.rotation = self.parse_rotation(transformer_node)
        self.scale = self.parse_scale(transformer_node)
        return self
    def apply_to(self, object):
        object.location = self.location
        object.rotation_quaternion = self.rotation
        object.scale = self.scale
        
"""
Can be created from an xml material node. Stores with diffuse, normal and metal texture paths and can create a corresponding blender material from them.
Uses a cache to avoid creating the exact same blender material multiple times when loading just one .cfg 
"""
class Material:
    materialCache = {}
    def __init__(self):
        self.diff_path = None
        self.norm_path = None
        self.metal_path = None
        self.name = "Unnamed Material"
    @classmethod
    def from_material_node(cls, material_node):
        self = Material()
        name_node = material_node.find("Name")
        if name_node is not None:
            self.name = name_node.text
        if material_node.find("cModelDiffTex") is not None:
            print("found diff path")
            diff_path = change_extension(material_node.find("cModelDiffTex").text, "_0.png")
            self.diff_path = diff_path
        if material_node.find("cModelNormalTex") is not None:
            norm_path = change_extension(material_node.find("cModelNormalTex").text, "_0.png")
            self.norm_path = norm_path
        if material_node.find("cModelMetallicTex") is not None:
            metal_path = change_extension(material_node.find("cModelMetallicTex").text, "_0.png")
            self.metal_path = metal_path
        return self
    @classmethod
    def from_filepaths(cls, name, diff_path, norm_path, metal_path):
        self = Material()
        self.name = name
        if diff_path:
            self.diff_path = change_extension(diff_path, "_0.png")
        if norm_path: 
            self.norm_path = change_extension(norm_path, "_0.png")
        if metal_path:
            self.metal_path = change_extension(metal_path, "_0.png")
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
        Material.materialCache[self.get_material_cache_key()] = material
        return material
    






            

class ImportAnnoCfg(Operator, ImportHelper):
    """Parses Anno (1800) .cfg files and automatically imports and positions all models, props, particles and decals in the scene.
When available, the corresponding .glb file is used, otherwise a named empty serves as placeholder."""
    bl_idname = "import.annocfg" 
    bl_label = "Import Anno .cfg"

    # ImportHelper mixin class uses this
    filename_ext = ".cfg"

    filter_glob: StringProperty(
        default="*.cfg",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    load_prop_models: BoolProperty(
        name="Load Prop Models",
        description="Load Prop Models",
        default=True,
    )
    load_files: BoolProperty(
        name="Load Files",
        description="Load Files",
        default=True,
    )
    load_props: BoolProperty(
        name="Load Props",
        description="Load Props",
        default=True,
    )
    load_decals: BoolProperty(
        name="Load Decals",
        description="Load Decals",
        default=True,
    )
    load_particles: BoolProperty(
        name="Load Particles",
        description="Load Particles",
        default=True,
    )

    def __init__(self):
        self.loadedFiles = []
    def execute(self, context):
        self.parse_cfg_file(self.filepath)
        return {'FINISHED'}
    

    PROP_DATA_BY_FILENAME = {}
    def get_prop_data(self, propDataPath):
        if propDataPath in ImportAnnoCfg.PROP_DATA_BY_FILENAME:
            return ImportAnnoCfg.PROP_DATA_BY_FILENAME[propDataPath]
        propFilename = get_full_path(propDataPath)
        if not os.path.exists(propFilename):
            return (propDataPath, None)
        propfile = open(propFilename).read()
        meshFileName = re.findall("<MeshFileName>(.*)<", propfile, re.I)[0]
        
        diff_path = get_first_or_none(re.findall("<cModelDiffTex>(.*)<", propfile, re.I))
        norm_path = get_first_or_none(re.findall("<cModelNormalTex>(.*)<", propfile, re.I))
        metallic_path = get_first_or_none(re.findall("<cModelNormalTex>(.*)<", propfile, re.I))
        material = Material.from_filepaths(get_file_basename(propfile), diff_path, norm_path, metallic_path)
        
        prop_data = (meshFileName, material)
        ImportAnnoCfg.PROP_DATA_BY_FILENAME[propDataPath] = prop_data
        return prop_data

    def parse_prop(self, prop, collection, parentObj = None):
        name = parse_name(prop)
        propFilePath = prop.find("FileName").text
        transform = Transform.from_transformer_node(prop)
        if self.load_prop_models:
            if has_file_type(propFilePath,'.prp'):
                modelFilePath, material = self.get_prop_data(propFilePath)
                self.import_GLFT(modelFilePath, transform, [material], name, collection, parentObj)
                return
        if name is None:
            name = get_file_basename(propFilePath)
        self.add_named_empty(name, transform, collection, parentObj)
        
    def parse_particle(self, particle, collection, parentObj = None):
        name = parse_name(particle)
        fileName = particle.find("FileName").text
        position = (0,0,0)
        rotation = (1,0,0,0)
        scale = (1,1,1)
        transform = Transform.from_transformer_node(particle.find("Transformer/Config"))
        if name is None: 
            name = os.path.basename(fileName)
        self.add_named_empty(name, transform, None, parentObj, "SPHERE")

    def parse_prop_container(self, container, parentObj = None):
        collectionName = parse_name(container)
        if collectionName is None:
            collectionName = "PropCollection"
        collection = get_collection(collectionName)
        if (container.find("OrientationTransform")):
            print("Found Orientation Transform, currently ignored for PropContainers because I didn't find an example file.")
        for prop in container.find("Props"):
            self.parse_prop(prop, collection, parentObj)

    def parse_model(self, model, parentObj = None):
        transform = Transform.from_transformer_node(model.find("Transformer/Config"))
        materials = []
        if model.find("Materials") is not None:
            for material_node in model.find("Materials"):
                material = Material.from_material_node(material_node)
                materials.append(material)
        name = parse_name(model)
        fileName = model.find("FileName").text
        self.import_GLFT(fileName, transform, materials, name, None, parentObj)

    def parse_decal(self, decal_node, parentObj = None):
        #Can decals even have transforms? Idk...
        transform = Transform.from_transformer_node(decal_node.find("Transformer/Config"))
        materials = []
        if decal_node.find("Materials") is not None:
            for material_node in decal_node.find("Materials"):
                material = Material.from_material_node(material_node)
                materials.append(material)
        # Let's assume that there's only one material...
        if not materials:
            return
        material = materials[0]
        
        x = parse_float_node(decal_node, "Extents.x", 0.0)
        y = parse_float_node(decal_node, "Extents.x", 0.0)
        z = parse_float_node(decal_node, "Extents.x", 0.0)
        if decal_node.find("Extents") is not None:
            x = parse_float_node(decal_node, "Extents")
            y = x
            z = x
        #Why do we even have a value for the height???
        bpy.ops.mesh.primitive_plane_add(size=2, enter_editmode=False, align='WORLD', location=(0,0,0), scale=(1,1,1))
        bpy.context.object.scale[0] = x
        bpy.context.object.scale[1] = -z
        if parentObj is not None:
            bpy.context.object.parent = parentObj
        bpy.context.object.name = "GroundDecal"
        bpy.context.object.data.materials.append(material.as_blender_material())

    def parse_included_file(self, file, parentObj = None):
        transform = Transform.from_transformer_node(file.find("Transformer/Config"))
        fileName = file.find("FileName").text
        if (os.path.exists(get_full_path(fileName))):
            file_obj = self.add_named_empty("FILE_"+get_file_basename(fileName), transform, None, parentObj, "ARROWS")
            self.parse_cfg_file(get_full_path(fileName), file_obj)
        else:
            file_obj = self.add_named_empty("FILE_"+get_file_basename(fileName), transform, None, parentObj)
            print(f"Warning: Missing file {fileName}")
            
    def parse_cfg_file(self, filePath, parentObj = None):
        if not os.path.exists(filePath):
            print(f"Error: Failed to parse {filePath}, file is missing")
            return
        tree = ET.parse(filePath)
        root = tree.getroot()
        for child in root:
            if (child.tag == 'PropContainers') and self.load_props:
                for container in child:
                    self.parse_prop_container(container, parentObj)
            if (child.tag == 'Particles') and self.load_particles:
                collection = get_collection("Particles")
                for particle in child:
                    self.parse_particle(particle, collection, parentObj)
            if (child.tag == 'Models'):
                for model in child:
                    self.parse_model(model, parentObj)
            if (child.tag == 'Files') and self.load_files:
                for file in child:
                    self.parse_included_file(file, parentObj)
            if (child.tag == 'Decals') and self.load_decals:
                for decal in child:
                    self.parse_decal(decal, parentObj)

    def add_named_empty(self, name, transform, collection = None, parentObject = None, type = "PLAIN_AXES"):
        bpy.ops.object.empty_add(type=type, align='WORLD', location = (0,0,0), scale = (1,1,-1))
        for o in bpy.context.selected_objects:
            o.name = name
            if parentObject is not None:
                o.parent = parentObject
            transform.apply_to(o)
            if collection is not None:
                o.users_collection[0].objects.unlink(o)
                collection.objects.link(o)
            return o

    """
    Imports the model located at datapath. Regardless of file ending, it looks for the .glb file. 
    If no such file can be found, an empty is created instead.
    After importing the transform is used to place it in the scene.
    Attaches the materials to the object.
    If no name is given, the object will be named after its file.
    """
    def import_GLFT(self, datapath, transform, materials, name = None, collection = None, parentObject = None):
        fullpath = get_full_path(datapath)
        fullpath_glb = change_extension(fullpath, ".glb")
        fn = get_file_basename(datapath)
        
        shortname = change_extension(fn, "").replace("_lod0", "")
        if (name is None) or (name == ""):
            name = fn
        if not os.path.exists(fullpath_glb):
            print(f"\nWarning: Missing .glb file for: {datapath}")
            self.add_named_empty(name, transform, collection, parentObject)
            return        
        bpy.ops.import_scene.gltf(filepath=fullpath_glb)
        for o in bpy.context.selected_objects:
            o.name = name
            if parentObject is not None:
                o.parent = parentObject
            transform.apply_to(o)
            if materials:
                for i,material in enumerate(materials):
                    if len(o.data.materials) <= i:
                        print("Warning: Missing materials slot for material" ,i )
                        break
    #                oldMaterial = o.data.materials[i]
    #                oldMaterial.user_clear()
    #                bpy.data.materials.remove(oldMaterial)
                    o.data.materials[i] = material.as_blender_material()
            if collection is not None:
                o.users_collection[0].objects.unlink(o)
                collection.objects.link(o)
                        
# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportAnnoCfg.bl_idname, text="Anno (.cfg)")


def register():
    bpy.utils.register_class(ImportAnnoCfgPreferences)
    bpy.utils.register_class(ImportAnnoCfg)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportAnnoCfgPreferences)
    bpy.utils.unregister_class(ImportAnnoCfg)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()