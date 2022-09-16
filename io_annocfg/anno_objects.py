
from __future__ import annotations
import bpy
from bpy.types import Object as BlenderObject
import xml.etree.ElementTree as ET
import os
import random
import re
import subprocess
from pathlib import Path, PurePath
from typing import Tuple, List, NewType, Any, Union, Dict, Optional, TypeVar, Type
from abc import ABC, abstractmethod
from bpy.props import EnumProperty, BoolProperty, PointerProperty, IntProperty, FloatProperty, CollectionProperty, StringProperty, FloatVectorProperty
from bpy.types import PropertyGroup, Panel, Operator, UIList
import bmesh
import sys

from collections import defaultdict
from math import radians
from .prefs import IO_AnnocfgPreferences
from .utils import *
from .transform import Transform
from .material import Material, ClothMaterial
from .feedback_ui import FeedbackConfigItem, GUIDVariationListItem, FeedbackSequenceListItem
from . import feedback_enums


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
    print(data_path)
    if not data_path:
        print("invalid data path")
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
    # bpy.context.view_layer.objects.active = None
    # for obj in bpy.data.objects:
    #     obj.select_set(False)
    ret = bpy.ops.import_scene.gltf(filepath=str(fullpath))
    obj = bpy.context.active_object
    print(obj.name, obj.type)
    Transform.mirror_mesh(obj)
    return obj

def convert_animation_to_glb(model_fullpath, animation_fullpath: Path):
    #Usage: ./rdm4-bin.exe -i rdm/container_ship_tycoons_lod1.rdm -sam anim/container_ship_tycoons_idle01.rdm
    rdm4_path = IO_AnnocfgPreferences.get_path_to_rdm4()
    if rdm4_path.exists() and animation_fullpath.exists() and model_fullpath.exists():
        out_filename = animation_fullpath.parent
        subprocess.call(f"\"{rdm4_path}\" -i \"{model_fullpath}\" -sam \"{animation_fullpath}\" --force --outdst \"{out_filename}\"", shell = True)


def import_animated_model_to_scene(model_data_path: Union[str, Path, None], animation_data_path) -> BlenderObject:
    print(model_data_path, animation_data_path)
    if not model_data_path or not animation_data_path:
        print("Invalid data path for animation or model")
        return add_empty_to_scene()
    model_fullpath = data_path_to_absolute_path(model_data_path)
    fullpath = data_path_to_absolute_path(animation_data_path)
    if fullpath is None:
        return None
    combined_path = Path(model_fullpath.parent, Path(model_fullpath.stem + "_a_"+Path(animation_data_path).stem + ".glb"))
    if not combined_path.exists():
            
        out_fullpath = Path(fullpath.parent, Path("out.glb"))
        if out_fullpath.exists():
            out_fullpath.unlink()
        if fullpath.exists():
            convert_animation_to_glb(model_fullpath, fullpath)
        if not out_fullpath.exists():
            return None
        out_fullpath.replace(combined_path)
        print("Saved animation ", animation_data_path, " of model ", model_data_path, " to ", combined_path)
    if not combined_path.exists():
        print(f"Warning: Conversion of {animation_data_path} for model {model_data_path} failed.")
        #self.report({'INFO'}, f"Missing file: Cannot find glb model {data_path}.")
        return None
    ret = bpy.ops.import_scene.gltf(filepath=str(combined_path))
    obj = bpy.context.active_object
    print(obj.name, obj.type)
    Transform.mirror_mesh(obj)
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
    #f.e. Animations->Type,  <Animations><A></A><A></A><A></A></Animations>
    child_anno_object_types_without_container: Dict[str, type] = {}
    #f.e. A->Type, <A></A><A></A><A></A>
    

    
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
        return ET.Element(cls.__name__)

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
                for i, subnode in enumerate(list(subnodes)):
                    child_obj = subcls.xml_to_blender(subnode, obj)
                    child_obj["import_index"] = i
                node.remove(subnodes)
        for subnode_name, subcls in cls.child_anno_object_types_without_container.items():
            if subcls == AnimationSequences and not IO_AnnocfgPreferences.turn_sequences_into_blender_objects():
                continue
            subnodes = node.findall(subnode_name)
            for i, subnode in enumerate(list(subnodes)):
                child_obj = subcls.xml_to_blender(subnode, obj)
                child_obj["import_index"] = i
                node.remove(subnode)
        
    @classmethod
    def xml_to_blender(cls: Type[T], node: ET.Element, parent_object = None) -> BlenderObject:

        obj = cls.add_blender_object_to_scene(node)
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

        for coll in obj.users_collection:
            # Unlink the object
            coll.objects.unlink(obj)

        # Link each object to the target collection
        bpy.context.scene.collection.objects.link(obj)
        return obj
    
    @classmethod
    def add_children_from_obj(cls, obj, node, child_map):
        container_name_by_subclass = {subcls : container_name for container_name, subcls in cls.child_anno_object_types.items()}
        children = obj.children
        if child_map is not None:
            #ToDo: Do not use child map if it is not necessary. I think there were problems with obj.children, but i do not remember them.
            children = child_map.get(obj.name, [])
        for child_obj in children:
            subcls = get_anno_object_class(child_obj)
            if subcls == NoAnnoObject:
                continue
            if subcls in cls.child_anno_object_types_without_container.values():
                subnode =  subcls.blender_to_xml(child_obj, node, child_map)
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
        cls.blender_to_xml_finish(obj, node)
        return node
    @classmethod
    def blender_to_xml_finish(cls, obj, node):
        return
    
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
        if not name.startswith(config_type + "_"):
            name = config_type + "_" + name
        return name
    
    
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
        
        if not obj.data:
            #or not obj.data.materials:
            return
        if len(materials) > 1 and all([bool(re.match( "Material_[0-9]+.*",m.name)) for m in obj.data.materials]):
            sorted_materials = sorted([mat.name for i, mat in enumerate(obj.data.materials)])
            if sorted_materials != [mat.name for mat in obj.data.materials]:
                
                print("Imported .glb with unordered but enumerated materials. Sorting the slots.")
                print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
                print(sorted_materials)
                for sorted_index, mat_name in enumerate(sorted_materials):
                    index = 0
                    for i, mat in enumerate(obj.data.materials):
                        index = i
                        if mat.name == mat_name:
                            break
                    bpy.context.object.active_material_index = index
                    for _ in range(len(obj.data.materials)):
                        bpy.ops.object.material_slot_move(direction='DOWN')

        missing_slots = len(materials) - len(obj.data.materials)
        if missing_slots > 0:
            for i in range(missing_slots):
                obj.data.materials.append(bpy.data.materials.new(name="NewSlotMaterial"))
        for i, material in enumerate(materials):
            if not material:
                continue
            slot = i
            old_material = obj.data.materials[slot]
            obj.data.materials[slot] = material.as_blender_material()
            old_material.user_clear()
            bpy.data.materials.remove(old_material)
        # for i, material in enumerate(materials):
        #     if not material:
        #         continue
        #     if i < len(obj.data.materials):
        #         old_material = obj.data.materials[i]
        #         obj.data.materials[i] = material.as_blender_material()
        #         old_material.user_clear()
        #         bpy.data.materials.remove(old_material)
        #     else:
        #         obj.data.materials.append(material.as_blender_material())
        


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

# Not really worth it to have this as its own object, I think. But maybe I'm wrong, so I'll leave it here.
class TrackElement(AnnoObject):
    has_transform = False
    has_name = False
    @classmethod
    def node_to_property_node(self, node, obj):
        node = super().node_to_property_node(node, obj)
        model_id = int(get_text(node, "ModelID", "-1"))
        main_file = obj.parent.parent.parent.parent
        for o in main_file.children:
            if get_anno_object_class(o) != Model:
                continue
            if o["import_index"] == model_id:
                model_name = o.name
                node.remove(node.find("ModelID"))
                ET.SubElement(node, "BlenderModelID").text = model_name
        particle_id = int(get_text(node, "ParticleID", "-1"))
        for o in main_file.children:
            if get_anno_object_class(o) != Particle:
                continue
            if o["import_index"] == particle_id:
                particle_name = o.name
                node.remove(node.find("ParticleID"))
                ET.SubElement(node, "BlenderParticleID").text = particle_name
        return node

class Track(AnnoObject):
    has_transform = False
    has_name = False
    # child_anno_object_types_without_container = {
    #     "TrackElement" : TrackElement,
    # }
    @classmethod
    def blender_name_from_node(cls, node):
        track_id = int(get_text(node, "TrackID", ""))
        name = "TRACK_"+ str(track_id)
        return name
    @classmethod
    def node_to_property_node(self, node, obj):
        for track_node in node.findall("TrackElement"):
            model_id = int(get_text(track_node, "ModelID", "-1"))
            main_file = obj.parent.parent.parent
            for o in main_file.children:
                if get_anno_object_class(o) != Model:
                    continue
                if o["import_index"] == model_id:
                    model_name = o.name
                    track_node.remove(track_node.find("ModelID"))
                    ET.SubElement(track_node, "BlenderModelID").text = model_name
            particle_id = int(get_text(track_node, "ParticleID", "-1"))
            for o in main_file.children:
                if get_anno_object_class(o) != Particle:
                    continue
                if o["import_index"] == particle_id:
                    particle_name = o.name
                    track_node.remove(track_node.find("ParticleID"))
                    ET.SubElement(track_node, "BlenderParticleID").text = particle_name
        return node
    
class AnimationSequence(AnnoObject):
    has_transform = False
    has_name = False
    child_anno_object_types_without_container = {
        "Track" : Track,
    }
    @classmethod
    def blender_name_from_node(cls, node):
        config_type = "SEQUENCE"
        seq_id = int(get_text(node, "SequenceID", "-1"))
        name = config_type + "_"+ feedback_enums.NAME_BY_SEQUENCE_ID.get(seq_id, str(seq_id))
        return name


class AnimationSequences(AnnoObject):
    has_transform = False
    has_name = False
    child_anno_object_types_without_container = {
        "Config" : AnimationSequence,
    }
    @classmethod
    def blender_name_from_node(cls, node):
        return "ANIMATION_SEQUENCES"


class AnimationsNode(AnnoObject):
    has_name = False
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        anim_obj = add_empty_to_scene()
        return anim_obj
    

class Animation(AnnoObject):
    has_name = False
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        controller_obj = add_empty_to_scene("ARROWS")
        if IO_AnnocfgPreferences.mirror_models():
            controller_obj.scale.x = -1
        
        model_data_path = get_text_and_delete(node, "ModelFileName")
        anim_data_path = get_text(node, "FileName")
        imported_obj = import_animated_model_to_scene(model_data_path, anim_data_path)
        
        if imported_obj is not None:
            imported_obj.parent = controller_obj
        return controller_obj
    
    @classmethod
    def blender_name_from_node(cls, node):
        config_type = "ANIMATION"
        file_name = Path(get_text(node, "FileName", "")).stem
        index = get_text(node, "AnimationIndex", "")
        name = config_type + "_"+ index + "_" + file_name
        return name
    
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
    
    @classmethod
    def add_children_from_obj(cls, obj, node, child_map):
        super().add_children_from_obj(obj, node, child_map)
        if node.find("Animations") is not None:
            return
        #Animations may have been loaded.
        children = obj.children
        if child_map is not None:
            #ToDo: Do not use child map if it is not necessary. I think there were problems with obj.children, but i do not remember them.
            children = child_map.get(obj.name, [])
        for child_obj in children:
            subcls = get_anno_object_class(child_obj)
            if subcls != AnimationsNode:
                continue
            animations_container = child_obj
            animations_node = find_or_create(node, "Animations")
            anim_nodes = []
            anim_children = animations_container.children
            if child_map is not None:
                #ToDo: Do not use child map if it is not necessary. I think there were problems with obj.children, but i do not remember them.
                anim_children = child_map.get(animations_container.name, [])
            for anim_obj in anim_children:
                subcls = get_anno_object_class(anim_obj)
                if subcls != Animation:
                    continue
                anim_node = Animation.blender_to_xml(anim_obj, None, child_map)
                anim_nodes.append(anim_node)
            anim_nodes.sort(key = lambda anim_node: int(get_text(anim_node, "AnimationIndex")))
            for anim_node in anim_nodes:
                anim_node.remove(anim_node.find("AnimationIndex"))
                animations_node.append(anim_node)

def recursive_add_to_collection(obj, collection):
    collection.objects.link(obj)
    for c in obj.children:
        recursive_add_to_collection(c, collection)

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
    def try_loading_from_library(cls, data_path, last_modified):
        from datetime import datetime
        libpath = IO_AnnocfgPreferences.get_cfg_cache_path()
        p = Path(libpath, Path(data_path + ".blend"))
        if p.exists():
            cache_last_modified = p.stat().st_mtime
            if cache_last_modified < last_modified:
                print(f"Cache Invalidation for {p}, modified {data_path} at {datetime.fromtimestamp(last_modified)}, last cache update at {datetime.fromtimestamp(cache_last_modified)}")
                p.unlink()
                return None
            
            with bpy.data.libraries.load(str(p)) as (data_from, data_to):
                data_to.collections = data_from.collections
            for new_coll in data_to.collections:
                if Path(data_path).name in new_coll.name:
                    instance = bpy.data.objects.new(new_coll.name, None)
                    instance.instance_type = 'COLLECTION'
                    instance.instance_collection = new_coll
                    bpy.context.scene.collection.objects.link(instance)
                    print(f"Loaded {Path(data_path).name} from lib")
                    return instance
            print(f"Warning: Failed to load {Path(data_path).name} from existing cache file {p}")
        return None
    
    @classmethod 
    def cache_to_library(cls, file_obj, data_path):
        print(f"Caching {data_path} in library")
        libpath = IO_AnnocfgPreferences.get_cfg_cache_path()
        if not libpath.exists():
            print(f"Warning, invalid cfg cache path {libpath}")
            return 
        p = Path(libpath, Path(data_path).parent)
        p.mkdir(parents=True, exist_ok=True)
        
        
        collection = bpy.data.collections.new(file_obj.name)
        bpy.context.scene.collection.children.link(collection)
        
        collection.asset_mark()
        collection.asset_data.tags.new("cfg")
        collection.asset_data.description = data_path
        for directory in PurePath(data_path).parts[:-1]:
            if directory not in ["graphics", "data"]:
                collection.asset_data.tags.new(directory)
        bpy.ops.ed.lib_id_generate_preview({"id": collection})
        
        
        recursive_add_to_collection(file_obj, collection)
        objects = []
        for obj in collection.all_objects:
            objects.append(obj)
        objects.append(collection)
        filename = f"{Path(data_path).name}.blend"
        filepath = Path(p, filename)
        bpy.data.libraries.write(str(filepath), set(objects), fake_user=True)
        bpy.context.scene.collection.children.unlink(collection)
        bpy.data.collections.remove(collection)
        
    @classmethod 
    def load_subfile(cls, data_path):
        if data_path is None:
            return add_empty_to_scene()
        fullpath = data_path_to_absolute_path(data_path)
        if not fullpath.exists():
            return add_empty_to_scene()
        
        last_modified = fullpath.stat().st_mtime
        
        if IO_AnnocfgPreferences.cfg_cache_loading_enabled(): #ToDo: Remove True here!!!
            file_obj = cls.try_loading_from_library(data_path, last_modified)
            if file_obj is not None:
                return file_obj
        
        tree = ET.parse(fullpath)
        root = tree.getroot()
        if root is None:
            return add_empty_to_scene()
        
        file_obj = MainFile.xml_to_blender(root)
        file_obj.name = "MAIN_FILE_" + fullpath.name
        
        if random.random() < IO_AnnocfgPreferences.cfg_cache_probability():
            cls.cache_to_library(file_obj, data_path)
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
        "location.x":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']/Position.x",
        "location.y":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']/Position.y",
        "location.z":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']/Position.z",
        "rotation.x":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']/Rotation.x",
        "rotation.y":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']/Rotation.y",
        "rotation.z":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']/Rotation.z",
        "rotation.w":"Transformer/Config[ConfigType = 'ORIENTATION_TRANSFORM']/Rotation.w",
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
    
    prop_obj_blueprints: Dict[str, BlenderObject] = {} #used to copy mesh prop data 
    
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
        if prop_filename in cls.prop_obj_blueprints:
            try: #If the reference prop has already been deleted, we cannot copy it.
                prop_obj = cls.prop_obj_blueprints[prop_filename].copy() #Can fail.
                bpy.context.scene.collection.objects.link(prop_obj)
                prop_obj.dynamic_properties.reset() #Fix doubled properties
                return prop_obj
            except:
                pass
        model_filename, material = cls.get_prop_data(prop_filename)
        imported_obj = import_model_to_scene(model_filename)
        if imported_obj is None:
            return add_empty_to_scene()
        #materials
        cls.apply_materials_to_object(imported_obj, [material])
        cls.prop_obj_blueprints[prop_filename] = imported_obj
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
            "WaterBlocker":IfoPlane,
            "FeedbackBlocker":IfoPlane,
            "PriorityFeedbackBlocker":IfoPlane,
            "UnevenBlocker":IfoPlane,
            "QuayArea":IfoPlane,
            "InvisibleQuayArea":IfoPlane,
            "MeshHeightmap":IfoMeshHeightmap,
        }
        for child_node in list(node):
            ifo_cls = ifo_object_by_name.get(child_node.tag, None)
            if ifo_cls is None:
                continue
            ifo_obj = ifo_cls.xml_to_blender(child_node, obj)
            node.remove(child_node)
    
    @classmethod
    def add_children_from_obj(cls, obj, node, child_map):
        children = obj.children
        if child_map is not None:
            #ToDo: Do not use child map if it is not necessary. I think there were problems with obj.children, but i do not remember them.
            children = child_map.get(obj.name, [])
        for child_obj in children:
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
            x = parse_float_node(pos_node, "xf")
            if IO_AnnocfgPreferences.mirror_models():
                x *= -1
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
            coords = obj.matrix_local @ vert.co
            x = coords.x
            if IO_AnnocfgPreferences.mirror_models():
                x *= -1
            y = -coords.y
            position_node = ET.SubElement(node, "Position")
            if node.tag == "BuildBlocker":
                x = float(round(x*2)) / 2
                y = float(round(y*2)) / 2 
            ET.SubElement(position_node, "xf").text = format_float(x)
            ET.SubElement(position_node, "zf").text = format_float(y)
                
        return node

class IfoMeshHeightmap(AnnoObject):
    has_transform = True
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        maxheight = float(get_text(node, "MaxHeight"))
        startx = float(get_text(node, "StartPos/x"))
        starty = float(get_text(node, "StartPos/y"))
        stepx = float(get_text(node, "StepSize/x"))
        stepy = float(get_text(node, "StepSize/y"))
        width = int(get_text(node, "Heightmap/Width"))
        height = int(get_text(node, "Heightmap/Height"))
        heightdata = [float(s.text) for s in node.findall("Heightmap/Map/i")]
        node.find("Heightmap").remove(node.find("Heightmap/Map"))
        print(f"Heightmap w={width} x h={height} => {len(heightdata)}")
        
        mesh = bpy.data.meshes.new("MeshHeightmap")  # add the new mesh
        obj = bpy.data.objects.new(mesh.name, mesh)
        col = bpy.data.collections.get("Collection")
        col.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        verts = []
        i = 0
        for a in range(height):
            for b in range(width):
                verts.append((startx + b * stepx, starty + a * stepy, heightdata[i]))
                i += 1

        mesh.from_pydata(verts, [], [])
        for i, vert in enumerate(obj.data.vertices):
            vert.co.y *= -1
            
        return obj

    @classmethod 
    def blender_to_xml(cls, obj, parent_node, child_map):
        node = super().blender_to_xml(obj, parent_node, child_map)
        map_node = ET.SubElement(node.find("Heightmap"), "Map")
        for vert in obj.data.vertices:
            z = vert.co.z
            ET.SubElement(map_node, "i").text = format_float(z)
        return node

class Sequence(AnnoObject):
    has_transform = False
    has_name = False
    
    @classmethod
    def node_to_property_node(self, node, obj):
        node = super().node_to_property_node(node, obj)
        seq_id = get_text_and_delete(node, "Id")
        ET.SubElement(node, "SequenceID").text = seq_id
        return node
    
    @classmethod
    def property_node_to_node(self, property_node, obj):
        node = super().property_node_to_node(property_node, obj)
        seq_id = get_text_and_delete(node, "SequenceID")
        ET.SubElement(node, "Id").text = seq_id
        return node
 


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
        node = super().default_node() # type: ignore
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
        node = super().default_node() # type: ignore
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
        children = obj.children
        if child_map is not None:
            #ToDo: Do not use child map if it is not necessary. I think there were problems with obj.children, but i do not remember them.
            children = child_map.get(obj.name, [])
        for child_obj in children:
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
        node = super().default_node() # type: ignore
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
        if prop in ["MultiplyActorByDummyCount", "StartDummyGroup"]:
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
        children = obj.children
        if child_map is not None:
            #ToDo: Do not use child map if it is not necessary. I think there were problems with obj.children, but i do not remember them.
            children = child_map.get(obj.name, [])
        for child_obj in children:
            subcls = get_anno_object_class(child_obj)
            if subcls != Cf7DummyGroup:
                continue
            Cf7DummyGroup.blender_to_xml(child_obj, dummy_groups_node, child_map)
        if not IO_AnnocfgPreferences.splines_enabled():
            return
        spline_data_node = find_or_create(node, "SplineData")
        for spline_obj in children:
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
 

class NamedMockObject:
    def __init__(self, name):
        self.name = name

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
    child_anno_object_types_without_container = {
        "Sequences" : AnimationSequences,
    }
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        file_obj = add_empty_to_scene()  
        return file_obj
    
    @classmethod
    def blender_to_xml_finish(cls, obj, node):
        model_index_by_name = {}
        for i, model_node in enumerate(node.findall("Models/Config")):
            model_index_by_name[get_text(model_node, "Name")] = i
        for track_element_node in node.findall("Sequences/Config/Track/TrackElement/BlenderModelID/.."):
            blender_model_id_node = track_element_node.find("BlenderModelID")
            blender_model_id = blender_model_id_node.text
            model_name = Model.anno_name_from_blender_object(NamedMockObject(blender_model_id))
            if model_name not in model_index_by_name:
                print(f"Error: Could not resolve BlenderModelID {blender_model_id}: No model named {model_name}. Using model 0 instead.")
            model_id = model_index_by_name.get(model_name, 0)
            track_element_node.remove(blender_model_id_node)
            ET.SubElement(track_element_node, "ModelID").text = str(model_id)
        #particles
        particle_index_by_name = {}
        for i, particle_node in enumerate(node.findall("Particles/Config")):
            particle_index_by_name[get_text(particle_node, "Name")] = i
        for track_element_node in node.findall("Sequences/Config/Track/TrackElement/BlenderParticleID/.."):
            blender_particle_id_node = track_element_node.find("BlenderParticleID")
            blender_particle_id = blender_particle_id_node.text
            particle_name = Particle.anno_name_from_blender_object(NamedMockObject(blender_particle_id))
            if particle_name not in particle_index_by_name:
                print(f"Error: Could not resolve BlenderParticleID {blender_particle_id}: No particle named {particle_name}. Using particle 0 instead.")
            particle_id = particle_index_by_name.get(particle_name, 0)
            track_element_node.remove(blender_particle_id_node)
            ET.SubElement(track_element_node, "ParticleID").text = str(particle_id)
            
            

class PropGridInstance:
    @classmethod
    def add_blender_object_to_scene(cls, node, prop_objects) -> BlenderObject:
        index = int(get_text(node, "Index", "-1"))
        if index == -1 or index >= len(prop_objects):
            o = bpy.data.objects.new( "empty", None )

            # due to the new mechanism of "collection"
            bpy.context.scene.collection.objects.link( o )

            # empty_draw was replaced by empty_display
            o.empty_display_size = 1
            o.empty_display_type = 'ARROWS'   
            return o
        prop_obj = prop_objects[index]
        if prop_obj is None:
            return None
        copy = prop_obj.copy()
        bpy.context.scene.collection.objects.link(copy)
        return copy
    @classmethod
    def str_to_bool(cls, b):
        return b in ["True", "true", "TRUE"]
    @classmethod
    def xml_to_blender(cls, node: ET.Element, prop_objects = [], parent_obj = None) -> BlenderObject:
        """
        <None>
            <Index>67</Index> #Use the prop at index 67 of FileNames
            <Position>153,76723 0,1976307 31,871208</Position> #Coordinates x z y for blender?
            <Rotation>0 -0,92359954 -0 0,3833587</Rotation>
            <Scale>0,6290292 0,6290292 0,6290292</Scale>
            <Color>1 1 1 1</Color> #Some data to store
            <AdaptTerrainHeight>True</AdaptTerrainHeight>
        </None>
        """
        obj = cls.add_blender_object_to_scene(node, prop_objects)
        if obj is None:
            return
        if parent_obj:
            obj.parent = parent_obj
        
        set_anno_object_class(obj, cls)
        
        location = [float(s) for s in get_text_and_delete(node, "Position", "0,0 0,0 0,0").replace(",", ".").split(" ")]
        rotation = [float(s) for s in get_text_and_delete(node, "Rotation", "1,0 0,0 0,0 0,0").replace(",", ".").split(" ")]
        rotation = [rotation[3], rotation[0], rotation[1], rotation[2]] #xzyw -> wxzy
        #rotation = [rotation[1], rotation[2], rotation[3], rotation[0]] #xzyw -> wxzy or something else
        scale    = [float(s) for s in get_text_and_delete(node, "Scale", "1,0 1,0 1,0").replace(",", ".").split(" ")]
        
        if node.find("AdaptTerrainHeight") is not None:
            node.find("AdaptTerrainHeight").text = str(int(cls.str_to_bool(node.find("AdaptTerrainHeight").text)))
        else:
            ET.SubElement(node, "AdaptTerrainHeight").text = "0"
        transform = Transform(location, rotation, scale, anno_coords = True)
        transform.apply_to(obj)

        obj.dynamic_properties.from_node(node)
        return obj
    
    @classmethod
    def blender_to_xml(cls, obj, parent = None, child_map = None):
        base_node = obj.dynamic_properties.to_node(ET.Element("None"))
        node = ET.Element("None")

        
        ET.SubElement(node, "FileName").text = get_text(base_node, "FileName")
        ET.SubElement(node, "Color").text = get_text(base_node, "Color", "1 1 1 1")
        if base_node.find("AdaptTerrainHeight") is not None:
            adapt = bool(int(get_text(base_node, "AdaptTerrainHeight")))
            ET.SubElement(node, "AdaptTerrainHeight").text = str(adapt)
        else:
            adapt = bool(int(get_text(base_node, "Flags")))
            ET.SubElement(node, "AdaptTerrainHeight").text = str(adapt)
        
        transform = Transform(obj.location, obj.rotation_quaternion, obj.scale, anno_coords = False)
        transform.convert_to_anno_coords()
        location = [format_float(f) for f in transform.location]
        rotation = [format_float(f) for f in[transform.rotation[1], transform.rotation[2], transform.rotation[3], transform.rotation[0]]] #wxzy ->xzyw
        scale = [format_float(f) for f in transform.scale]
        
        ET.SubElement(node, "Position").text = ' '.join(location).replace(".", ",")
        ET.SubElement(node, "Rotation").text = ' '.join(rotation).replace(".", ",")
        ET.SubElement(node, "Scale").text = ' '.join(scale).replace(".", ",")

        return node


class IslandFile:
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        file_obj = add_empty_to_scene()  
        return file_obj
    @classmethod
    def blender_to_xml(cls, obj, parent = None, child_map = None):
        """Only exports the prop grid. Not the heighmap or the prop FileNames."""
        base_node = ET.fromstring(obj["islandxml"])
        
        prop_grid_node = base_node.find("PropGrid")
        if prop_grid_node.find("Instances"): #delete existing
            prop_grid_node.remove(prop_grid_node.find("Instances"))
        instances_node = ET.SubElement(prop_grid_node, "Instances")
        
        index_by_filename = {}
        index = 0
        
        for obj in bpy.data.objects:
            if get_anno_object_class(obj) not in [PropGridInstance, Prop]:
                continue
            if obj.parent is not None: #when .cfgs are imported there will be props with parents, so don't use them.
                continue
            prop_node = PropGridInstance.blender_to_xml(obj)
            file_name = get_text_and_delete(prop_node, "FileName")
            if file_name not in index_by_filename:
                index_by_filename[file_name] = index
                index += 1
            ET.SubElement(prop_node, "Index").text = str(index_by_filename[file_name])
            instances_node.append(prop_node)
            
        if prop_grid_node.find("FileNames"): #delete existing
            prop_grid_node.remove(prop_grid_node.find("FileNames"))
        filenames_node = ET.SubElement(prop_grid_node, "FileNames")
        
        print(index_by_filename.items())
        for filename, index in sorted(index_by_filename.items(), key = lambda kv: kv[1]):
            ET.SubElement(filenames_node, "None").text = filename
        
        return base_node
    
    @classmethod
    def xml_to_blender(cls, node: ET.Element, prop_import_mode) -> BlenderObject:
        import numpy as np
        
        obj = cls.add_blender_object_to_scene(node)
        obj["islandxml"] = ET.tostring(node)
        obj.name = "ISLAND_FILE"
        set_anno_object_class(obj, cls)
        
        terrain_node = node.find("Terrain")
        if terrain_node is not None:
            heightmap_node = terrain_node.find("CoarseHeightMap")
            width = int(get_text(heightmap_node, "width"))
            height = int(get_text(heightmap_node, "width"))
            data = [int(s) for s in get_text(heightmap_node, "map").split(" ")]
            print(f"Heightmap w={width} x h={height} => {len(data)}")
            grid_width = float(get_text(terrain_node,"GridWidth", "8192"))
            grid_height = float(get_text(terrain_node,"GridHeight", "8192"))
            unit_scale = float(get_text(terrain_node,"UnitScale", "0,03125").replace(",", "."))
            bpy.ops.mesh.landscape_add(subdivision_x=width, subdivision_y=height, mesh_size_x=grid_width*unit_scale, mesh_size_y=grid_width*unit_scale,
                                       height=0, refresh=True)
            terrain_obj = bpy.context.active_object
            max_height = 8192
            min_height = float(get_text(terrain_node,"MinMeshLevel", "0"))
            #0,03125
            for i, vert in enumerate(terrain_obj.data.vertices):
                vert.co.z = data[i] / max_height * 32
                vert.co.x *= -1
            terrain_obj.location.x -= grid_width*unit_scale/2
            terrain_obj.location.y -= grid_width*unit_scale/2
            terrain_obj.rotation_euler[2] = radians(90.0)
            
            if False:
                #Make a terrain texture
                print("Making heightmap")
                image = bpy.data.images.new("TerrainHeightmap", width=width, height=height)
                pixels = [None] * width * height
                maxh = 0.0
                np_array = np.zeros((width,height,4), dtype = np.float16)
                for x, row in enumerate(np_array):
                    for y, pix in enumerate(row):
                        index = (x * np_array.shape[0]) + y
                        
                        h = ((data[index]+max_height)/(2*max_height))
                        pix[0] = h
                        pix[1] = h
                        pix[2] = h
                        pix[3] = 1.0
                        # For some reason, the height value does not convert correctly. Super weird...
                        # In theory, after subtracting 0.5 and multiplying with 64, we should get the exact same heightmap...
                # return obj
                # for x in range(width):
                #     for y in range(height):
                #         index = (y * width) + x
                #         h = (data[index]/8192.0*0.5)+0.5
                        
                #         maxh = max(maxh, data[index])
                #         r = h
                #         g = h
                #         b = h
                #         a = 1.0
                #         np_array[index] = [r,g,b,a]
                #         pixels[index] = [r, g, b, a]
                # print("Maximum height value", maxh)
                # flatten list
                # pixels = [chan for px in pixels for chan in px]
                image.pixels = np_array.ravel()
                image.filepath_raw = "C:/Users/Lars/test.png"
                image.file_format = 'PNG'
                # image.save()
                # bpy.context.scene.render.image_settings.color_depth = '16'

                #Save as 16bit BW
                scene = bpy.context.scene
                settings = scene.render.image_settings
                old_color_depth, old_format, old_color_mode = (settings.color_depth, settings.file_format, settings.color_mode)
                settings.color_depth = '16'
                settings.file_format = 'PNG'
                settings.color_mode = 'BW'
                # Save with scene
                image.save_render('C:/Users/Lars/test_smart.png', scene = scene)
                #Reset settings
                settings.color_depth = old_color_depth
                settings.file_format = old_format
                settings.color_mode = old_color_mode
                print("Exported image")
                
                bpy.ops.mesh.landscape_add(subdivision_x=width, subdivision_y=height, mesh_size_x=grid_width*unit_scale, mesh_size_y=grid_width*unit_scale,
                                            height=0, refresh=True)
                terrain_obj = bpy.context.active_object
                heightTex = bpy.data.textures.new('HeightMap', type = 'IMAGE')
                heightTex.image = image

                terrain_obj.location.x -= grid_width*unit_scale/2
                terrain_obj.location.y -= grid_width*unit_scale/2
            
        if prop_import_mode == "None":
            return obj
        filenames_node = node.find("PropGrid/FileNames")
        prop_objects = []
        if filenames_node is not None:
            for i, file_node in enumerate(list(filenames_node)):
                data_path = file_node.text
                if prop_import_mode == "No Vegetation" and "vegetation" in data_path:
                    prop_objects.append(None)
                    continue
                prop_xml_node = ET.fromstring(f"""
                            <Config>
                                <ConfigType>PROP</ConfigType>
                                <FileName>{data_path}</FileName>
                                <Name>PROP_{i}_{Path(data_path).stem}</Name>
                                <Flags>1</Flags>
                            </Config>                  
                        """)
                prop_obj = Prop.xml_to_blender(prop_xml_node)
                prop_objects.append(prop_obj)
            
        instances_node = node.find("PropGrid/Instances")
        if instances_node is not None:
            instance_nodes = list(instances_node)
            print(len(instance_nodes), " Objects.")
            for i, instance_node in enumerate(instance_nodes):
                if i % int(len(instance_nodes)/100) == 0: 
                    print(str(float(i) / len(instance_nodes) * 100.0) + "%")
                PropGridInstance.xml_to_blender(instance_node, prop_objects)
        else:
            print("Island missing PropGrid")
            print(node.find("PropGrid"))
        #delete the blueprint props
        for prop_obj in prop_objects:
            if prop_obj is None:
                continue
            bpy.data.objects.remove(prop_obj, do_unlink=True)
        return obj

class BezierCurve():
    @classmethod
    def is_valid_bezier_curve_node(cls, node: ET.Element) -> bool:
        if node.tag != "BezierPath":
            return False
        path_node = node.find("Path")
        if path_node is None:
            return False
        curve_node = path_node.find("BezierCurve")
        if curve_node is None:
            return False
        for point_node in list(curve_node):
            for attribute in list(point_node):
                if attribute.tag not in ["p", "i", "o"]:
                    return False
        return True

    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        curvedata = bpy.data.curves.new(name="Curve", type='CURVE')   
        curvedata.dimensions = '3D'    
        obj = bpy.data.objects.new("BezierCurve", curvedata)   
        bpy.context.scene.collection.objects.link(obj)  
        polyline = curvedata.splines.new('BEZIER')  
        
        path_node = node.find("Path")
        curve_node = path_node.find("BezierCurve")
        point_nodes = list(curve_node)
        num_points = len(point_nodes)
        polyline.bezier_points.add(num_points-1) 
    
        for idx, _ in enumerate(point_nodes):
            point = polyline.bezier_points[idx]
            point_node = point_nodes[idx]
            v = [float(s) for s in get_text_and_delete(point_node, "p", "0,0 0,0 0,0").replace(",", ".").split(" ")]
            position = (-v[0], -v[2], v[1])
            point.co = position
            v = [float(s) for s in get_text_and_delete(point_node, "i", "0,0 0,0 0,0").replace(",", ".").split(" ")]
            handle_left = (position[0]-v[0], position[1]-v[2], position[2]+v[1])
            point.handle_left = handle_left
            v = [float(s) for s in get_text_and_delete(point_node, "o", "0,0 0,0 0,0").replace(",", ".").split(" ")]
            handle_right = (position[0]-v[0], position[1]-v[2], position[2]+v[1])
            point.handle_right = handle_right
            point.handle_left_type = 'FREE'
            point.handle_right_type = 'FREE'
        path_node.remove(curve_node)
        min_node = path_node.find("Minimum")
        max_node = path_node.find("Maximum")
        path_node.remove(min_node)
        path_node.remove(max_node)
        return obj 
        
    @classmethod
    def xml_to_blender(cls, node: ET.Element, parent_obj = None) -> BlenderObject:
        """
        Only supports these curves. No idea what w, u0 stands for in other variants of bezier curves.
        <BezierPath>
            <Path>
                <Minimum>121,90588 5,298042 160,05571</Minimum>
                <Maximum>128,76202 5,301949 165,46204</Maximum>
                <BezierCurve>
                    <None>
                        <p>127,08328 5,298042 160,76552</p>
                        <i>-0,19070435 0 -0,15771994</i>
                        <o>0,19070435 0 0,15771994</o>
                    </None>
                    <None>
                        <p>128,22751 5,298042 161,71184</p>
                        <i>-0,11701199 0 -0,21806403</i>
                        <o>0,17704894 0 0,32994914</o>
                    </None>
                </BezierCurve>
            </Path>
        </BezierPath>
        """
        obj = cls.add_blender_object_to_scene(node)
        set_anno_object_class(obj, cls)
        obj.dynamic_properties.from_node(node)
        if parent_obj:
            obj.parent = parent_obj
            obj.matrix_parent_inverse = obj.parent.matrix_basis.inverted()
        return obj
        
    @classmethod
    def blender_to_xml(cls, obj, parent = None, child_map = None):
        node = obj.dynamic_properties.to_node(ET.Element("None"))
        curvedata = obj.data
        spline = curvedata.splines[0]
        path_node = node.find("Path")
        curve_node = ET.SubElement(path_node, "BezierCurve")
        minp = (float("inf"), float("inf"), float("inf"))
        maxp = (-float("inf"), -float("inf"), -float("inf"))
        for bezier_point in spline.bezier_points:
            point_node = ET.SubElement(curve_node, "None")
            p = bezier_point.co
            p = (-p[0], p[2], -p[1])
            minp = (min(p[0], minp[0]), min(p[1], minp[1]), min(p[2], minp[2]))
            maxp = (max(p[0], maxp[0]), max(p[1], maxp[1]), max(p[2], maxp[2]))
            i = bezier_point.handle_left
            i = (-i[0] - p[0], i[2]- p[1], -i[1]- p[2])
            o = bezier_point.handle_right
            o = (-o[0]- p[0], o[2]- p[1], -o[1]- p[2])
            
            ET.SubElement(point_node, "p").text = ' '.join([format_float(f) for f in p])
            ET.SubElement(point_node, "i").text = ' '.join([format_float(f) for f in i])
            ET.SubElement(point_node, "o").text = ' '.join([format_float(f) for f in o])
        
        min_node = find_or_create(path_node, "Minimum")
        max_node = find_or_create(path_node, "Maximum")
        min_node.text = ' '.join([format_float(f) for f in minp])
        max_node.text = ' '.join([format_float(f) for f in maxp])
        return node


class AssetsXML():
    instance = None
    def __init__(self):
        self.path = Path(IO_AnnocfgPreferences.get_path_to_rda_folder(), Path("data/config/export/main/asset/assets.xml"))
        if not self.path.exists():
            raise Exception(f"Assets.xml required for this island file. Expected it at '{self.path}'")
        
        print("Loading assets.xml")
        self.tree = ET.parse(self.path)
        self.root = self.tree.getroot()
        print("Assets.xml loaded.")
        
        self.cfg_cache = {}
        self.assets_by_guid = {}
        self.extract_assets(self.root)
        print("Asset Dict completed")
        
    def extract_assets(self, node):
        if node.tag != "Asset":
            for c in list(node):
                self.extract_assets(c)
            return
        guid_node = node.find("Values/Standard/GUID")
        if guid_node is None:
            return
        self.assets_by_guid[guid_node.text] = node

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance
        
    def get_asset(self, guid):
        return self.assets_by_guid.get(str(guid), None)
        asset_node = self.root.find(f".//Asset/Values/Standard[GUID='{guid}']/../..")
        return asset_node
    
    def get_variation_cfg_and_name(self, guid, index):
        if (guid, index) in self.cfg_cache:
            return self.cfg_cache[guid, index]
        asset_node = self.get_asset(guid)
        if asset_node is None:
            print("Cannot find asset with guid {guid}")
            self.cfg_cache[(guid, index)] = None, None
            return None, None
        if asset_node.find("Values/Object/Variations") is None:
            return None, None
        variations = list(asset_node.find("Values/Object/Variations"))
        name = asset_node.find("Values/Standard/Name").text
        if index >= len(variations):
            print("Missing variation {index} for guid {guid} ({name})")
            self.cfg_cache[(guid, index)] = None, None
            return None, None
        item = variations[index]
        cfg_filename = item.find("Filename").text
        
        self.cfg_cache[(guid, index)] = (cfg_filename, name)
        return (cfg_filename, name)


class GameObject:
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        o = bpy.data.objects.new( "empty", None )
        # due to the new mechanism of "collection"
        bpy.context.scene.collection.objects.link( o )
        # empty_draw was replaced by empty_display
        o.empty_display_size = 1
        o.empty_display_type = 'ARROWS'   
        return o
    
    @classmethod 
    def parent_for_subfile(cls, file_obj) -> BlenderObject:
        node = ET.fromstring(f"""
        <None>
            <guid>0</guid>
            <ID>{random.randint(-2147483647,2147483647)}</ID>
            <Variation>0</Variation>
            <Position>0,0 0,0 0,0</Position>
            <Direction>3.14159</Direction>
            <ParticipantID>
                <id>8</id>
            </ParticipantID>
            <QuestObject>
                <QuestIDs />
                <ObjectWasVisible>
                <None>False</None>
                <None>False</None>
                </ObjectWasVisible>
                <OverwriteVisualParticipant />
            </QuestObject>
            <Mesh>
                <Flags>
                <flags>1</flags>
                </Flags>
                <SequenceData>
                <CurrentSequenceStartTime>100</CurrentSequenceStartTime>
                </SequenceData>
                <Orientation>0 0,0 0,0 0,0</Orientation>
                <Scale>1.0</Scale>
            </Mesh>
            <SoundEmitter />
        </None>
        """)
        obj = cls.add_blender_object_to_scene(node)
        set_anno_object_class(obj, cls)
        
        node.find("ID").text = "ID_"+node.find("ID").text
        mesh_node = node.find("Mesh")
    
        location = [float(s) for s in get_text_and_delete(node, "Position", "0,0 0,0 0,0").replace(",", ".").split(" ")]
        rotation = [1.0, 0.0, 0.0, 0.0] 
        scale    = [1.0, 1.0, 1.0]
        if mesh_node is not None:
            rotation = [float(s) for s in get_text_and_delete(mesh_node, "Orientation", "1,111 0,0 0,0 0,0").replace(",", ".").split(" ")]
            rotation = [rotation[3], rotation[0], rotation[1], rotation[2]] #xzyw -> wxzy
            scale = [float(s) for s in get_text_and_delete(mesh_node, "Scale", "1,0 1,0 1,0").replace(",", ".").split(" ")]
            if len(scale) == 1:
                scale = [scale[0], scale[0], scale[0]]
        
        transform = Transform(location, rotation, scale, anno_coords = True)
        transform.apply_to(obj)

        obj.dynamic_properties.from_node(node)
        
        
        obj.name = "GameObject_" + str(file_obj.name.replace("FILE_", ""))
        obj.location = file_obj.location
        obj.rotation_quaternion = file_obj.rotation_quaternion
        obj.scale = file_obj.scale
        file_obj.parent = obj
        file_obj.location = (0,0,0)
        file_obj.rotation_quaternion = (1, 0,0,0)
        file_obj.scale = (1,1,1)
        return obj
        
    @classmethod
    def xml_to_blender(cls, node: ET.Element, assetsXML, parent_obj = None) -> BlenderObject:
        """
        <None>
            <guid>100689</guid>
            <ID>-9221085318956974056</ID>
            <Variation>6</Variation>
            <Position>202,14145 0,7333633 121,70564</Position>
            <Direction>1,3954557</Direction>
            <ParticipantID>
                <id>8</id>
            </ParticipantID>
            <QuestObject>
                <QuestIDs />
                <ObjectWasVisible>
                <None>False</None>
                <None>False</None>
                </ObjectWasVisible>
                <OverwriteVisualParticipant />
            </QuestObject>
            <Mesh>
                <Flags>
                <flags>1</flags>
                </Flags>
                <SequenceData>
                <CurrentSequenceStartTime>100</CurrentSequenceStartTime>
                </SequenceData>
                <Orientation>0 -0,64247024 0 0,7662945</Orientation>
                <Scale>1.5</Scale>
            </Mesh>
            <SoundEmitter />
            <BezierPath/>
        </None>
        """
        obj = cls.add_blender_object_to_scene(node)
        if parent_obj:
            obj.parent = parent_obj
        
        set_anno_object_class(obj, cls)
        
        node.find("ID").text = "ID_"+node.find("ID").text
        mesh_node = node.find("Mesh")
    
        location = [float(s) for s in get_text_and_delete(node, "Position", "0,0 0,0 0,0").replace(",", ".").split(" ")]
        rotation = [1.0, 0.0, 0.0, 0.0] 
        scale    = [1.0, 1.0, 1.0]
        if mesh_node is not None:
            rotation = [float(s) for s in get_text_and_delete(mesh_node, "Orientation", "1,111 0,0 0,0 0,0").replace(",", ".").split(" ")]
            rotation = [rotation[3], rotation[0], rotation[1], rotation[2]] #xzyw -> wxzy
            scale = [float(s) for s in get_text_and_delete(mesh_node, "Scale", "1,0 1,0 1,0").replace(",", ".").split(" ")]
            if len(scale) == 1:
                scale = [scale[0], scale[0], scale[0]]
        
        transform = Transform(location, rotation, scale, anno_coords = True)
        transform.apply_to(obj)
        
        bezier_node = node.find("BezierPath")
        if bezier_node is not None:
            if BezierCurve.is_valid_bezier_curve_node(bezier_node):
                bezier_obj = BezierCurve.xml_to_blender(bezier_node, obj)

        obj.dynamic_properties.from_node(node)
        
        
        guid = get_text(node, "guid")
        variation = int(get_text(node, "Variation", "0"))
        file_name, asset_name = assetsXML.get_variation_cfg_and_name(guid, variation)
        obj.name = "GameObject_" + str(asset_name)
        if file_name is not None:
            try:
                subfile_node = ET.fromstring(f"""
                    <Config>
                        <FileName>{file_name}</FileName>
                        <ConfigType>FILE</ConfigType>
                        <Transformer>
                            <Config>
                            <ConfigType>ORIENTATION_TRANSFORM</ConfigType>
                            <Conditions>0</Conditions>
                            </Config>
                        </Transformer>
                    </Config>
                """)
                blender_obj = SubFile.xml_to_blender(subfile_node, obj)
            except Exception as ex:
                print(f"Error {guid} {variation} {file_name} {ex}")
        return obj
    
    @classmethod
    def blender_to_xml(cls, obj, parent = None, child_map = None):
        node = obj.dynamic_properties.to_node(ET.Element("None"))
        node.find("ID").text = node.find("ID").text.replace("ID_", "")
        
        transform = Transform(obj.location, obj.rotation_quaternion, obj.scale, anno_coords = False)
        transform.convert_to_anno_coords()
        location = [format_float(f) for f in transform.location]
        rotation = [format_float(f) for f in[transform.rotation[1], transform.rotation[2], transform.rotation[3], transform.rotation[0]]] #wxzy ->xzyw
        scale = [format_float(f) for f in transform.scale]
        mesh_node = find_or_create(node, "Mesh")
        ET.SubElement(node, "Position").text = ' '.join(location).replace(".", ",")
        ET.SubElement(mesh_node, "Orientation").text = ' '.join(rotation).replace(".", ",")
        if len(set(scale)) == 1:
            if scale[0] != format_float(1.0):
                ET.SubElement(mesh_node, "Scale").text =  scale[0].replace(".", ",")
        else:
            ET.SubElement(mesh_node, "Scale").text = ' '.join(scale).replace(".", ",")
        for child in obj.children:
            if get_anno_object_class(child) == BezierCurve:
                bezier_node = BezierCurve.blender_to_xml(child, node, child_map)
                node.append(bezier_node)
        return node
    
    

class IslandGamedataFile:
    @classmethod
    def add_blender_object_to_scene(cls, node) -> BlenderObject:
        file_obj = add_empty_to_scene()  
        return file_obj
    
    @classmethod
    def xml_to_blender(cls, node: ET.Element, assetsXML) -> BlenderObject:
        obj = cls.add_blender_object_to_scene(node)
        obj["islandgamedataxml"] = ET.tostring(node)
        obj.name = "ISLAND_GAMEDATA_FILE"
        set_anno_object_class(obj, cls)
        
        
        objects_nodes = node.findall("./GameSessionManager/AreaManagerData/None/Data/Content/AreaObjectManager/GameObject/objects")
        for c, objects_node in enumerate(objects_nodes):
            for i, obj_node in enumerate(objects_node):
                print(f"Container {c+1} / {len(objects_nodes)}; Object {i+1} / {len(objects_node)},")
                GameObject.xml_to_blender(obj_node, assetsXML)
                
    @classmethod
    def blender_to_xml(cls, obj, randomize_ids = False):
        """Only exports the prop grid. Not the heighmap or the prop FileNames."""
        base_node = ET.fromstring(obj["islandgamedataxml"])
        
        objects_node_by_id = {}
        objects_nodes = base_node.findall("./GameSessionManager/AreaManagerData/None/Data/Content/AreaObjectManager/GameObject/objects")
        
        default_objects_node = objects_nodes[0]
        for c, objects_node in enumerate(objects_nodes):
            for i, obj_node in enumerate(list(objects_node)):
                obj_id = get_text(obj_node, "ID")
                objects_node_by_id[obj_id] = objects_node
                objects_node.remove(obj_node)
        for obj in bpy.data.objects:
            if get_anno_object_class(obj) != GameObject:
                continue
            game_obj_node = GameObject.blender_to_xml(obj)
            obj_id = get_text(game_obj_node, "ID")
            objects_node = objects_node_by_id.get(obj_id, default_objects_node)
            
            if randomize_ids:
                game_obj_node.find("ID").text = str(random.randint(-2**63, 2**63-1))
            
            objects_node.append(game_obj_node)
            
        return base_node   


anno_object_classes = [
    NoAnnoObject, MainFile, Model, Cf7File,
    SubFile, Decal, Propcontainer, Prop, Particle, IfoCube, IfoPlane, Sequence, DummyGroup,
    Dummy, Cf7DummyGroup, Cf7Dummy, FeedbackConfig,SimpleAnnoFeedbackEncodingObject, ArbitraryXMLAnnoObject, Light, Cloth, Material, IfoFile, Spline, IslandFile, PropGridInstance,
    IslandGamedataFile, GameObject, AnimationsNode, Animation, AnimationSequences, AnimationSequence, Track, TrackElement, IfoMeshHeightmap,BezierCurve,
]

def str_to_class(classname):
    return getattr(sys.modules[__name__], classname)

def get_anno_object_class(obj) -> type:
    return str_to_class(obj.anno_object_class_str)

def set_anno_object_class(obj, cls: type):
     obj.anno_object_class_str = cls.__name__
    
    
    
    
    

    
def register():
    bpy.types.Object.anno_object_class_str = bpy.props.EnumProperty(name="Anno Object Class", description = "Determines the type of the object.",
                                                                items = [(cls.__name__, cls.__name__, cls.__name__) for cls in anno_object_classes]
                                                                , default = "NoAnnoObject")
    
    #CollectionProperty(type = AnnoImageTextureProperties)

def unregister():
    del bpy.types.Object.anno_object_class_str

