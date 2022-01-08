import bpy
from bpy.props import StringProperty, IntProperty, CollectionProperty, PointerProperty, EnumProperty, FloatProperty, BoolProperty
from bpy.types import PropertyGroup, UIList, Operator, Panel
from . import feedback_enums


class FeedbackConfigItem(PropertyGroup):
    """Group of properties representing a feedback config"""
    Description: StringProperty(name = "Description", default = "", description = "Optional")
    IgnoreRootObjectXZRotation: BoolProperty(
           name="IgnoreRootObjectXZRotation", description="Feedback units won't rotate with the building - why would you want that?",
    )
    IsAlwaysVisibleActor: BoolProperty(
           name="IsAlwaysVisibleActor", description="",
    )
    ApplyScaleToMovementSpeed: BoolProperty(
           name="ApplyScaleToMovementSpeed", description="", default=True,
    )
    ActorCount: IntProperty(
           name="ActorCount", description="",
           default=1, min = 1, max = 256,
    )
    MaxActorCount: IntProperty(
           name="MaxActorCount", description="",
           default=1, min = 1, max = 256,
    )
    CreateChance: IntProperty(
           name="CreateChance", description="",
           default=100, min = 0, max = 100, subtype = "PERCENTAGE"
    )
    BoneLink: StringProperty(name = "BoneLink", default = "NoLink", description = "")
    RenderFlags: IntProperty(
           name="RenderFlags", description="",
           default=0, min = 0,
    )
    MultiplyActorByDummyCount: PointerProperty(name = "MultiplyActorByDummyCount", description = "Select a DummyGroup object (or nothing)", type = bpy.types.Object)
    IgnoreForceActorVariation: BoolProperty(
           name="IgnoreForceActorVariation", description="",
    )
    IgnoreDistanceScale: BoolProperty(
           name="IgnoreDistanceScale", description="",default=True
    )
    m_MinScaleFactor: FloatProperty(
           name="m_MinScaleFactor", description="A scale of 0.5 seems to be the default value.",
           default=0.5, min = 0.0
    )
    m_MaxScaleFactor: FloatProperty(
           name="m_MaxScaleFactor", description="",
           default=0.5, min = 0.0
    )
    DefaultStateDummy: PointerProperty(name = "DefaultStateDummy", description = "Select a Dummy object", type = bpy.types.Object)

def guid_enum_callback(guid_list_item, context):
    guid_type = guid_list_item.guid_type
    guid_dict = feedback_enums.guid_type_dict[guid_type]
    return feedback_enums.enum_from_dict(guid_dict)

class GUIDVariationListItem(PropertyGroup):
    """Group of properties representing an item in the list."""
    #guid: StringProperty(name = "GUID", default = "", description = "ID or Alias")
    guid_type : EnumProperty(
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
    guid: EnumProperty(
            name='GUID',
            description='GUID',
            items= guid_enum_callback,
            #default='production_generic_worker_01'
            )
    custom_guid: StringProperty(
            name='GUID',
            description='Enter your custom GUID here.',
            default=''
            )

class FeedbackSequenceListItem(PropertyGroup):
    """Group of properties representing an item in the list."""
    animation_type: EnumProperty(
            name='Type',
            description='Animation Type',
            items={
            ('Walk', 'Walk', 'Walk from current dummy to the target dummy.'),
            ('IdleAnimation', 'IdleAnimation', 'Repeat animation a number of times'),
            ('TimedIdleAnimation', 'TimedIdleAnimation', 'Repeat animation for time in ms')},
            default='IdleAnimation')
    
    sequence: EnumProperty(
            name='Sequence',
            description='Animation Sequence',
            items= feedback_enums.animation_sequences,
            default='idle01')
    
    target_empty: PointerProperty(name="TargetDummy", type=bpy.types.Object)
    
    speed_factor_f: FloatProperty(
           name="SpeedFactorF",
           description="0.0 is default speed",
           default=0.0,
           min = 0.0,
           max = 10.0,
    )
    
    min_play_count: IntProperty(
           name="MinPlayCount",
           description="",
           default=1,
           min = 0,
           max = 100,
    )
    max_play_count: IntProperty(
           name="MaxPlayCount",
           description="",
           default=1,
           min = 0,
           max = 100,
    )
    
    min_play_time: IntProperty(
           name="MinPlayTime",
           description="",
           default=1000,
           min = 0,
    )
    max_play_time: IntProperty(
           name="MaxPlayTime",
           description="",
           default=1000,
           min = 0,
    )

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
            row2 = split.box().grid_flow(row_major=True, columns=1, even_columns=True, even_rows=False, align=False)
            
            row1.label(text = str(index))
            
            #ACTION
            # row2.label(text=item.animation_type, icon = "TOOL_SETTINGS")
            # row2.label(text=item.sequence, icon = "ARMATURE_DATA")
            row2.prop(item, "animation_type", icon = "TOOL_SETTINGS")
            row2.prop(item, "sequence", icon = "ARMATURE_DATA")
            
            if item.animation_type == "Walk":
                row2.prop(item, "target_empty")
                if item.target_empty is not None:
                    row2.label(text = "TargetDummy.Name: " + item.target_empty.dynamic_properties.get_string("Name"))
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


class LIST_OT_NewItem(Operator):
    """Add a new item to the list."""

    bl_idname = "feedback_sequence_list.new_item"
    bl_label = "Add a new item"

    def execute(self, context):
        context.active_object.feedback_sequence_list.add()

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


class LIST_OT_MoveItem(Operator):
    """Move an item in the list."""

    bl_idname = "feedback_sequence_list.move_item"
    bl_label = "Move an item in the list"

    direction: bpy.props.EnumProperty(items=(('UP', 'Up', ""),
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
    chars = int(context.region.width / 7)
    wrapper = textwrap.TextWrapper(width=chars)
    text_lines = wrapper.wrap(text=text)
    for text_line in text_lines:
        parent.label(text=text_line)

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
            if key in ["DefaultStateDummy", "MultiplyActorByDummyCount"]:
                obj = getattr(context.active_object.feedback_config_item, key, None)
                if obj is not None:
                    col.label(text = key+".Name: " + obj.dynamic_properties.get_string("Name"))
        col = layout.row().box().column()
        col.label(text = "GUIDVariationList")
        col.template_list("FEEDBACK_GUID_UL_List", "feedback_guid_list", active_object,
                          "feedback_guid_list", active_object, "feedback_guid_list_index", rows = 1)
        row = col.row()
        row.operator('feedback_guid_list.new_item', text='NEW')
        row.operator('feedback_guid_list.delete_item', text='REMOVE')
            
        
        feedback_sequence_box = layout.box()
        
        feedback_sequence_box.label(text = "FeedbackSequence")
        row = feedback_sequence_box.row()
        row.template_list("FEEDBACK_SEQUENCE_UL_List", "feedback_sequence_list", active_object,
                          "feedback_sequence_list", active_object, "feedback_sequence_list_index")

        row = feedback_sequence_box.row()
        row.operator('feedback_sequence_list.new_item', text='NEW')
        row.operator('feedback_sequence_list.delete_item', text='REMOVE')
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
    bpy.types.Object.feedback_config_item = bpy.props.PointerProperty(type=FeedbackConfigItem)

def unregister():

    del bpy.types.Object.feedback_sequence_list
    del bpy.types.Object.feedback_sequence_list_index
    
    del bpy.types.Object.feedback_guid_list
    del bpy.types.Object.feedback_guid_list_index
    
    del bpy.types.Object.feedback_config_item
    
    for cls in classes:
        bpy.utils.unregister_class(cls)
