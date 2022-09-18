import bpy
from bpy.props import StringProperty, IntProperty, CollectionProperty, PointerProperty, EnumProperty, FloatProperty, BoolProperty
from bpy.types import PropertyGroup, UIList, Operator, Panel
from . import feedback_enums
from .utils import data_path_to_absolute_path, to_data_path, get_text
import xml.etree.ElementTree as ET
from . import anno_objects
import random


class FeedbackConfigItem(PropertyGroup):
    """Group of properties representing a feedback config"""
    Description: StringProperty(name = "Description", default = "", description = "Optional")# type: ignore
    IgnoreRootObjectXZRotation: BoolProperty(# type: ignore
           name="IgnoreRootObjectXZRotation", description="Feedback units won't rotate with the building - why would you want that?",
    )
    IsAlwaysVisibleActor: BoolProperty(# type: ignore
           name="IsAlwaysVisibleActor", description="",
    )
    ApplyScaleToMovementSpeed: BoolProperty(# type: ignore
           name="ApplyScaleToMovementSpeed", description="", default=True,
    )
    ActorCount: IntProperty(# type: ignore
           name="ActorCount", description="",
           default=1, min = 1, max = 256,
    )
    MaxActorCount: IntProperty(# type: ignore
           name="MaxActorCount", description="",
           default=1, min = 1, max = 256,
    )
    CreateChance: IntProperty(# type: ignore
           name="CreateChance", description="",
           default=100, min = 0, max = 100, subtype = "PERCENTAGE"
    )
    BoneLink: StringProperty(name = "BoneLink", default = "NoLink", description = "")# type: ignore
    RenderFlags: IntProperty(# type: ignore
           name="RenderFlags", description="",
           default=0, min = 0,
    )
    MultiplyActorByDummyCount: PointerProperty(name = "MultiplyActorByDummyCount", description = "Select a DummyGroup object (or nothing)", type = bpy.types.Object)# type: ignore
    IgnoreForceActorVariation: BoolProperty(# type: ignore
           name="IgnoreForceActorVariation", description="",
    )
    IgnoreDistanceScale: BoolProperty(# type: ignore
           name="IgnoreDistanceScale", description="",default=True
    )
    m_MinScaleFactor: FloatProperty(# type: ignore
           name="m_MinScaleFactor", description="A scale of 0.5 seems to be the default value.",
           default=0.5, min = 0.0
    )
    m_MaxScaleFactor: FloatProperty(# type: ignore
           name="m_MaxScaleFactor", description="",
           default=0.5, min = 0.0
    )
    DefaultStateDummy: PointerProperty(name = "DefaultStateDummy", description = "Select a Dummy object", type = bpy.types.Object)# type: ignore
    StartDummyGroup: PointerProperty(name = "StartDummyGroup",  # type: ignore
            description = "Select a Dummy object, used with multiply actor count to create a group of units that have the same animation (will use ALL given IdleAnimation sequences and ignore everything else) at different locations. REQUIRES properly named dummies inside the dummy group. For a dummy group named 'group', name them 'group_0', 'group_1', and so on.",
            type = bpy.types.Object
    ) 

def guid_enum_callback(guid_list_item, context):
    guid_type = guid_list_item.guid_type
    guid_dict = feedback_enums.guid_type_dict[guid_type]
    return feedback_enums.enum_from_dict(guid_dict)

class GUIDVariationListItem(PropertyGroup):
    """Group of properties representing an item in the list."""
    #guid: StringProperty(name = "GUID", default = "", description = "ID or Alias")
    guid_type : EnumProperty( # type: ignore
            name='Type',
            description='GUID Type',
            items= [
                ("Custom", "Custom", "Custom - if the guid you need is not in this list."),
                ("Resident", "Resident", "Resident"),
                ("ColonyResident", "ColonyResident", "Residents of the colonies. 01: New World, AF: Africa, 03: Arctic"),
                ("Worker", "Worker", "Worker"),
                ("LandAnimal", "LandAnimal", "LandAnimal"),
                ("Fish", "Fish", "Fish"),
                ("Bird", "Bird", "Bird"),
            ],
            default='Resident')
    guid: EnumProperty( # type: ignore
            name='GUID',
            description='GUID',
            items= guid_enum_callback,
            #default='production_generic_worker_01'
            )
    custom_guid: StringProperty( # type: ignore
            name='GUID',
            description='Enter your custom GUID here.',
            default=''
            )

class FeedbackSequenceListItem(PropertyGroup):
    """Group of properties representing an item in the list."""
    animation_type: EnumProperty( # type: ignore
            name='Type',
            description='Animation Type',
            items=[
            ('Walk', 'Walk', 'Walk from current dummy to the target dummy.'),
            ('IdleAnimation', 'IdleAnimation', 'Repeat animation a number of times'),
            ('TimedIdleAnimation', 'TimedIdleAnimation', 'Repeat animation for time in ms')],
            default='IdleAnimation')
    
    sequence: EnumProperty( # type: ignore
            name='Sequence',
            description='Animation Sequence',
            items= feedback_enums.animation_sequences,
            default='idle01')
    
    target_empty: PointerProperty(name="TargetDummy", type=bpy.types.Object) # type: ignore
    
    speed_factor_f: FloatProperty( # type: ignore
           name="SpeedFactorF",
           description="0.0 is default speed",
           default=0.0,
           min = 0.0,
           max = 10.0,
    )
    
    min_play_count: IntProperty( # type: ignore
           name="MinPlayCount",
           description="",
           default=1,
           min = 0,
           max = 100,
    )
    max_play_count: IntProperty( # type: ignore
           name="MaxPlayCount",
           description="",
           default=1,
           min = 0,
           max = 100,
    )
    
    min_play_time: IntProperty( # type: ignore
           name="MinPlayTime",
           description="",
           default=1000,
           min = 0,
    )
    max_play_time: IntProperty( # type: ignore
           name="MaxPlayTime",
           description="",
           default=1000,
           min = 0,
    )
    
    def copy_from(self, other):
        self.animation_type = other.animation_type
        self.sequence = other.sequence
        self.target_empty = other.target_empty
        self.speed_factor_f = other.speed_factor_f
        self.min_play_count = other.min_play_count
        self.max_play_count = other.max_play_count
        self.min_play_time = other.min_play_time
        self.max_play_time = other.max_play_time

class FEEDBACK_GUID_UL_List(UIList):
    """Demo UIList."""

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row()
            row.prop(item, "guid_type")
            if item.guid_type == "Custom":
                row.prop(item, "custom_guid")
            else:
                row.prop(item, "guid")
                
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="")

#Blogpost ui lists: https://sinestesia.co/blog/tutorials/using-uilists-in-blender/
class FEEDBACK_SEQUENCE_UL_List(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):

        # We could write some code to decide which icon to use here...
        custom_icon = 'OBJECT_DATAMODE'

        # Make sure your code supports all 3 layout types
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            
            split = layout.split(factor=0.05)
            row1 = split.row()
            row2 = split.box().grid_flow(row_major=True, columns=7, even_columns=False, even_rows=False, align=False)
            
            row1.box().label(text = str(index))
            
            #ACTION
            # row2.label(text=item.animation_type, icon = "TOOL_SETTINGS")
            # row2.label(text=item.sequence, icon = "ARMATURE_DATA")
            row2.prop(item, "animation_type", icon = "TOOL_SETTINGS", text = "")
            row2.prop(item, "sequence", icon = "ARMATURE_DATA", text = "")
            
            if item.animation_type == "Walk":
                row2.prop(item, "target_empty", text = "Target")
                if item.target_empty is not None:
                    row2.label(text = "(" + item.target_empty.dynamic_properties.get_string("Name")+ ")")
                row2.prop(item, "speed_factor_f")
            elif item.animation_type == "IdleAnimation":
                row2.prop(item, "min_play_count")
                row2.prop(item, "max_play_count")
            elif item.animation_type == "TimedIdleAnimation":
                row2.prop(item, "min_play_time", icon = "TIME")
                row2.prop(item, "max_play_time", icon = "TIME")
                
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon = custom_icon)

class FEEDBACK_GUID_LIST_OT_NewItem(Operator):
    """Add a new item to the list."""

    bl_idname = "feedback_guid_list.new_item"
    bl_label = "Add a new item"

    def execute(self, context):
        context.active_object.feedback_guid_list.add()
        return{'FINISHED'}




class FEEDBACK_GUID_LIST_OT_DeleteITem(Operator):
    """Delete the selected item from the list."""

    bl_idname = "feedback_guid_list.delete_item"
    bl_label = "Deletes an item"

    @classmethod
    def poll(cls, context):
        return context.active_object.feedback_guid_list

    def execute(self, context):
        feedback_guid_list = context.active_object.feedback_guid_list
        index = context.active_object.feedback_guid_list_index

        feedback_guid_list.remove(index)
        context.active_object.feedback_guid_list_index = min(max(0, index - 1), len(feedback_guid_list) - 1)

        return{'FINISHED'}

class LIST_OT_DeleteItem(Operator):
    """Delete the selected item from the list."""

    bl_idname = "feedback_sequence_list.delete_item"
    bl_label = "Deletes an item"

    @classmethod
    def poll(cls, context):
        return context.active_object.feedback_sequence_list

    def execute(self, context):
        feedback_sequence_list = context.active_object.feedback_sequence_list
        index = context.active_object.feedback_sequence_list_index

        feedback_sequence_list.remove(index)
        context.active_object.feedback_sequence_list_index = min(max(0, index - 1), len(feedback_sequence_list) - 1)

        return{'FINISHED'}


def load_sequence(obj, selected_sequence_id):
    for anim_sequences in obj.children:
        if not anno_objects.get_anno_object_class(anim_sequences) == anno_objects.AnimationSequences:
            continue
        for subfile_seq in anim_sequences.children:
            if not anno_objects.get_anno_object_class(subfile_seq) == anno_objects.AnimationSequence:
                continue
            seq_node = subfile_seq.dynamic_properties.to_node(ET.Element("Config"))
            sequence_id = int(get_text(seq_node, "SequenceID"))
            sequence_id = feedback_enums.NAME_BY_SEQUENCE_ID.get(sequence_id, str(sequence_id))
            if selected_sequence_id == sequence_id:
                bpy.context.view_layer.objects.active = subfile_seq
                bpy.ops.object.show_model()
                bpy.ops.object.show_sequence()
                return {"INFO"}, f"Successfully loaded {selected_sequence_id}."
    return {"ERROR"}, f"Missing Sequence {selected_sequence_id} on {obj.name}"

def update_feedback_unit(fcfg_obj):
    unit_obj = fcfg_obj.feedback_unit
    if unit_obj is None:
        return {"ERROR"}, "No unit object"
    unit_obj.scale = (5, 5, 5)
    if fcfg_obj.feedback_config_item.StartDummyGroup:
        group = fcfg_obj.feedback_config_item.StartDummyGroup
        if group.children and len(group.children) > 0:
            child = random.choice(group.children)
            unit_obj.parent = child
    if fcfg_obj.feedback_config_item.DefaultStateDummy:
        unit_obj.parent = fcfg_obj.feedback_config_item.DefaultStateDummy
    feedback_sequence_list = fcfg_obj.feedback_sequence_list
    index = fcfg_obj.feedback_sequence_list_index
    sequence = None
    for i, item in enumerate(feedback_sequence_list):
        if i > index:
            break
        if item.animation_type == "Walk":
            unit_obj.parent = item.target_empty
        sequence = item.sequence
    if sequence is not None:
        return load_sequence(unit_obj, sequence)
    return {"INFO"}, "No sequence"
   
class FEEDBACK_OT_UpdateFeedbackUnit(Operator):
    """Updates the feedback unit to the currently selected entry in the feedback sequence list. Can be used to visualize the feedback. No effect in game."""

    bl_idname = "feedback_unit.update"
    bl_label = "Updates the feedback unit to the currently selected entry in the feedback sequence list. Can be used to visualize the feedback. No effect in game."

    def execute(self, context):
        obj = context.active_object
        
        c, b = update_feedback_unit(obj)
        self.report(c, b)
            
        bpy.context.view_layer.objects.active = obj
        
        return{'FINISHED'}

class FEEDBACK_OT_DeleteFeedbackUnit(Operator):
    """Deletes the visual feedback unit (blender only)"""

    bl_idname = "feedback_unit.delete"
    bl_label = "Deletes the visual feedback unit (blender only)"
    def delete_recursively(self, obj):
        for o in obj.children:
            self.delete_recursively(o)
        bpy.data.objects.remove(obj, do_unlink=True)

    def execute(self, context):
        obj = context.active_object
        
        unit_obj = obj.feedback_unit
        self.delete_recursively(unit_obj)
        obj.feedback_unit = None
        
        return{'FINISHED'}
    
    
class FEEDBACK_OT_LoadFeedbackUnit(Operator):
    """Loads one of the GuidVariation cfgs. Can be used to visualize the feedback. No effect in game."""

    bl_idname = "feedback_unit.load"
    bl_label = "Loads one of the GuidVariation cfgs. Can be used to visualize the feedback. No effect in game."

    def execute(self, context):
        obj = context.active_object
        guid_list = obj.feedback_guid_list
        if len(guid_list) == 0:
            return {'CANCELLED'}
        item = guid_list[obj.feedback_guid_list_index]
        name = item.guid
        guid = feedback_enums.full_guids_by_name.get(name, name)
        cfg = feedback_enums.cfg_by_guid[guid]
        
        unit_obj = self.import_cfg_file(data_path_to_absolute_path(cfg), "FeedbackUnit_"+name)
        bpy.context.view_layer.objects.active = unit_obj
        
        #If the model was loaded from cache, it only is an instanced collection
        if unit_obj.instance_collection is not None:
            print("Loaded feedback unit from cache, making it real.")
            bpy.ops.object.make_hierarchical_collection_instance_real()
        
        bpy.ops.object.load_all_animations()
        # bpy.context.view_layer.objects.active = unit_obj
        # bpy.ops.object.ShowSequence()
        
        obj.feedback_unit = unit_obj
        
        c, b = update_feedback_unit(obj)
        self.report(c, b)
        
        
        bpy.context.view_layer.objects.active = obj
        
        return{'FINISHED'}
    
    def import_cfg_file(self, absolute_path, name): 
        if not absolute_path.exists():
            self.report({'INFO'}, f"Missing file: {absolute_path}")
            return
        tree = ET.parse(absolute_path)
        root = tree.getroot()
        if root is None:
            return
        
        file_obj = anno_objects.MainFile.xml_to_blender(root)
        file_obj.name = name
        
        return file_obj
    
def get_dummy_index(dummy):
    name = dummy.dynamic_properties.get_string("Name")
    head = name.rstrip('0123456789')
    tail = name[len(head):]
    return int(tail)

class AutogenerateWalkSequence(Operator):
    """Uses the parent dummy group of the default state dummy to create a walk sequence."""
    bl_idname = "object.autogenerate_walk_sequence"
    bl_label = "Generate Walk Sequence From DefaultDummy"
    def execute(self, context):
        obj = context.active_object
        feedback_sequence_list = obj.feedback_sequence_list
        default_start_dummy = obj.feedback_config_item.DefaultStateDummy
        if not default_start_dummy or default_start_dummy.anno_object_class_str != "Dummy":
            self.report({"ERROR"}, "Select a DefaultStateDummy first")
            return {'CANCELLED'}
        group = default_start_dummy.parent
        if not group:
            self.report({"ERROR"}, f"Dummy {default_start_dummy.name} missing parent group.")
            return {"CANCELLED"}
        sorted_children = sorted(list(group.children), key = lambda obj: get_dummy_index(obj))
        for i,dummy in enumerate(sorted_children):
            if i != 0:
                feedback_sequence_list.add()
                index = len(feedback_sequence_list)-1
                item = feedback_sequence_list[index]
                item.animation_type = "Walk"
                item.sequence = "walk01"
                item.target_empty = dummy
            if dummy.dummy_add_idle_in_walk_sequence == True:
                feedback_sequence_list.add()
                index = len(feedback_sequence_list)-1
                item = feedback_sequence_list[index]
                item.animation_type = "IdleAnimation"
                item.sequence = "idle01"
        return {'FINISHED'}
    
class LIST_OT_NewItem(Operator):
    """Add a new item to the list."""

    bl_idname = "feedback_sequence_list.new_item"
    bl_label = "Add a new item"

    def execute(self, context):
        context.active_object.feedback_sequence_list.add()

        return{'FINISHED'}


class LIST_OT_DuplicateItem(Operator):
    """Add a new item to end of the list (duplicate of selected one)."""

    bl_idname = "feedback_sequence_list.duplicate_item"
    bl_label = "Duplicate selected item"

    def execute(self, context):
        feedback_sequence_list = context.active_object.feedback_sequence_list
        index = context.active_object.feedback_sequence_list_index
        
        feedback_sequence_list.add()
        
        feedback_sequence_list[len(feedback_sequence_list)-1].copy_from(feedback_sequence_list[index])
        return{'FINISHED'}


class LIST_OT_MoveItem(Operator):
    """Move an item in the list."""

    bl_idname = "feedback_sequence_list.move_item"
    bl_label = "Move an item in the list"

    direction: bpy.props.EnumProperty(items=(('UP', 'Up', ""),  # type: ignore
                                              ('DOWN', 'Down', ""),))

    @classmethod
    def poll(cls, context):
        return context.active_object.feedback_sequence_list

    def move_index(self):
        """ Move index of an item render queue while clamping it. """

        index = bpy.context.active_object.feedback_sequence_list_index
        list_length = len(bpy.context.active_object.feedback_sequence_list) - 1  # (index starts at 0)
        new_index = index + (-1 if self.direction == 'UP' else 1)

        bpy.context.active_object.feedback_sequence_list_index = max(0, min(new_index, list_length))

    def execute(self, context):
        feedback_sequence_list = context.active_object.feedback_sequence_list
        index = context.active_object.feedback_sequence_list_index

        neighbor = index + (-1 if self.direction == 'UP' else 1)
        feedback_sequence_list.move(neighbor, index)
        self.move_index()

        return{'FINISHED'}

 #https://b3d.interplanety.org/en/multiline-text-in-blender-interface-panels/
def _label_multiline(context, text, parent):
    import textwrap
    chars = int(context.region.width / 6.2)
    wrapper = textwrap.TextWrapper(width=chars)
    text_lines = wrapper.wrap(text=text)
    for text_line in text_lines:
        parent.label(text=text_line)

def available_animations(unit_obj):
    if unit_obj is None:
        return ["UNKNOWN (Load Feedback Unit First)"]
    sequences = []
    for anim_sequences in unit_obj.children:
        if not anno_objects.get_anno_object_class(anim_sequences) == anno_objects.AnimationSequences:
            continue
        for subfile_seq in anim_sequences.children:
            if not anno_objects.get_anno_object_class(subfile_seq) == anno_objects.AnimationSequence:
                continue
            seq_node = subfile_seq.dynamic_properties.to_node(ET.Element("Config"))
            sequence_id = int(get_text(seq_node, "SequenceID"))
            sequence_id = feedback_enums.NAME_BY_SEQUENCE_ID.get(sequence_id, str(sequence_id))
            sequences.append(sequence_id)
    return sorted(sequences)

class PT_FeedbackConfig(Panel):
    """Demo panel for UI list Tutorial."""
    bl_label = "Simple Anno Feedback Encoding"
    bl_idname = "VIEW_3D_PT_AnnoObjectFeedbackConfig"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Anno Object' 
    @classmethod
    def poll(cls, context):
        if not context.active_object:
            return False
        return context.active_object.anno_object_class_str == "FeedbackConfig"

    def draw(self, context):
        layout = self.layout
        active_object = context.active_object

        
        description = "A simplified version of a .cf7 Feedback Definition. Export it by choosing the SimpleAnnoFeedbackEncoding feedback type option when exporting."
        _label_multiline(
            context=context,
            text=description,
            parent=layout
        )
        row = layout.row()
        col = row.box().column()
        for key in FeedbackConfigItem.__annotations__.keys():
            col.prop(context.active_object.feedback_config_item, key)
            if key in ["DefaultStateDummy", "MultiplyActorByDummyCount", "StartDummyGroup"]:
                obj = getattr(context.active_object.feedback_config_item, key, None)
                if obj is not None:
                    col.label(text = key+".Name: " + obj.dynamic_properties.get_string("Name"))
        
        col = layout.row().box().column()
        col.label(text = "GUIDVariationList")
        
        if context.active_object.feedback_unit is None:
            col.operator('feedback_unit.load', text='Load Feedback Unit')
        else:
            r = col.row()
            r.operator('feedback_unit.update', text='Update Feedback Unit')
            r.operator('feedback_unit.delete', text='Delete Feedback Unit')
        col.prop(context.active_object, "feedback_unit", text="Feedback Visualization Unit")
        
        col.template_list("FEEDBACK_GUID_UL_List", "feedback_guid_list", active_object,
                          "feedback_guid_list", active_object, "feedback_guid_list_index", rows = 1)
        row = col.row()
        row.operator('feedback_guid_list.new_item', text='New')
        row.operator('feedback_guid_list.delete_item', text='Remove')
        
        feedback_sequence_box = layout.box()
        header = feedback_sequence_box.row()
        header.label(text = "FeedbackSequence")
        header.prop(active_object, "show_available_sequences")
        available_sequences = "Valid Sequences: " + ", ".join(available_animations(active_object.feedback_unit))
        if active_object.show_available_sequences:
            _label_multiline(
                context=context,
                text=available_sequences,
                parent=feedback_sequence_box.box()
            )
        if len(active_object.feedback_sequence_list) == 0:
            feedback_sequence_box.row().operator(AutogenerateWalkSequence.bl_idname, text='Generate Walk Sequence')
        
        row = feedback_sequence_box.row()
        row.template_list("FEEDBACK_SEQUENCE_UL_List", "feedback_sequence_list", active_object,
                          "feedback_sequence_list", active_object, "feedback_sequence_list_index")

        row = feedback_sequence_box.row()
        row.operator('feedback_sequence_list.new_item', text='New')
        row.operator('feedback_sequence_list.delete_item', text='Remove')
        row.operator('feedback_sequence_list.duplicate_item', text='Copy')
        row.operator('feedback_sequence_list.move_item', text='UP').direction = 'UP'
        row.operator('feedback_sequence_list.move_item', text='DOWN').direction = 'DOWN'


classes = [
    GUIDVariationListItem,
    FEEDBACK_GUID_UL_List,
    FEEDBACK_GUID_LIST_OT_NewItem,
    FEEDBACK_GUID_LIST_OT_DeleteITem,
    FeedbackConfigItem,
    FeedbackSequenceListItem,
    FEEDBACK_SEQUENCE_UL_List,
    LIST_OT_NewItem,
    LIST_OT_DeleteItem,
    LIST_OT_MoveItem,
    PT_FeedbackConfig,
    LIST_OT_DuplicateItem,
    FEEDBACK_OT_LoadFeedbackUnit,
    FEEDBACK_OT_UpdateFeedbackUnit,
    FEEDBACK_OT_DeleteFeedbackUnit,
    AutogenerateWalkSequence,
]
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    

    bpy.types.Object.feedback_sequence_list = CollectionProperty(type = FeedbackSequenceListItem)
    bpy.types.Object.feedback_sequence_list_index = IntProperty(name = "Index for feedback_sequence_list",
                                             default = 0)
    
    bpy.types.Object.feedback_guid_list = CollectionProperty(type = GUIDVariationListItem)
    bpy.types.Object.feedback_guid_list_index = IntProperty(name = "Index for feedback_guid_list",
                                             default = 0)
    bpy.types.Object.dummy_add_idle_in_walk_sequence = BoolProperty(name = "Add idle when auto generating walk sequence",
                                             default = False)
    bpy.types.Object.show_available_sequences = BoolProperty(name = "Show Available Sequences",
                                             default = False, description = "Shows the sequences available to the currently loaded feedback unit.")
    bpy.types.Object.feedback_config_item = bpy.props.PointerProperty(type=FeedbackConfigItem)
    bpy.types.Object.feedback_unit = bpy.props.PointerProperty(type= bpy.types.Object, description = "Only used for visualization purposes in blender. No effect in game.")

def unregister():

    del bpy.types.Object.feedback_sequence_list
    del bpy.types.Object.feedback_sequence_list_index
    
    del bpy.types.Object.feedback_guid_list
    del bpy.types.Object.feedback_guid_list_index
    
    del bpy.types.Object.dummy_add_idle_in_walk_sequence
    
    del bpy.types.Object.show_available_sequences
    
    del bpy.types.Object.feedback_config_item
    del bpy.types.Object.feedback_unit
    
    for cls in classes:
        bpy.utils.unregister_class(cls)
