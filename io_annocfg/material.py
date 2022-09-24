from __future__ import annotations
import bpy
from bpy.types import Object as BlenderObject
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Tuple, List, NewType, Any, Union, Dict, Optional, TypeVar, Type
import bmesh
import sys
import os
import subprocess
from collections import defaultdict
from .prefs import IO_AnnocfgPreferences
from .utils import *


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
                <cModelNormalTex>{norm_path}</cModelNormalTex>
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
            filepath_full = os.path.realpath(bpy.path.abspath(shader_node.image.filepath, library=shader_node.image.library))
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
        fullpath = data_path_to_absolute_path(texture_path)
        png_fullpath = data_path_to_absolute_path(png_file)
        image = bpy.data.images.get(str(png_file.name), None)
        if image is not None:
            image_path_full = os.path.normpath(bpy.path.abspath(image.filepath, library=image.library))
            if str(image_path_full) == str(png_fullpath):
                return image
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