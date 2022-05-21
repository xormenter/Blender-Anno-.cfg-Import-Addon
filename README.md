# Blender-Anno-.cfg-Import/Export-Addon
Allows you to import from Anno (1800) .cfg files, make changes and export it to .cfg again.
Automatically positions all models, props, particles, decals, subfiles, ifo-blockers, and cf7 blockers in the scene.
When used with the rdm4 converter and texconv, it will automatically convert .rdm to .glb and .dds to .png for importing. Same goes for .fc files and the AnnoFCConverter. It also has a export to .rda option for models.
This means that if you have all those tools, you don't have to convert anything manually and can edit everything directly in Blender.

# Requirements
- Blender **3(.2)** https://www.blender.org/

**You can get Blender 3.2 Beta here: https://builder.blender.org/download/daily/**

**If not using v.3.2+, you'll need to update the gltf importer addon manually!** (A required fix for a bug only comes with Blender 3.2) For this, download the *repository* (master branch) from https://github.com/KhronosGroup/glTF-Blender-IO and overwrite the `io_scene_gltf_2`addon folder in your blender installation with the `io_scene_gltf_2`folder found inside the `addons` folder of the downloaded repository. DO NOT download the most recent release of glTF-Blender-IO. The bugfix isn't released yet!

For full functionality you need:
- rdm4 converter https://github.com/lukts30/rdm4
- texconv.exe https://github.com/microsoft/DirectXTex
- .fc Converter (AnnoFCConverter.exe) (please use this one, as it doesn't have a problem with newlines at the end: https://github.com/jakobharder/AnnoFCConverter)
- The blender addon "A.N.T. Landscape". It is shipped with blender, but needs to be enabled in the addon preferences.
And of course the .rda explorer to unpack the game files: https://github.com/lysannschlegel/RDAExplorer

# Installation
1. Install the other tools.
2. Open blender, go to Edit->Preferences->Addons. Click `Install...` and select the downloaded `io_annocfg.zip` (https://github.com/xormenter/Blender-Anno-.cfg-Import-Addon/releases/tag/v.2.1).
3. If you haven't done so already, **unpack the .rda files** (at least the data/graphics part of it) into a single folder. It should look something like this: `C:\whatever\somewhere\rda\data\graphics\...`.  
4. In the addon preferences, set the **rda path** to the folder that **contains** your `data` folder with the unpacked rda files. In this example, that would be `C:\whatever\somewhere\rda`
5. Specify the paths to the `texconv.exe`, `rdm4-bin.exe`, `AnnoFCConverter.exe` executables.

You are now ready to go! Optional: Set up the prop asset library (See below)


# Usage
## Importing 
1. With the addon enabled, go to `Blender->Import->Anno (.cfg)`. Select the .cfg file that you want to import into blender. 
2. This may take some time. Tip: Use solid viewport shading during the import - generating the material shaders takes up the most time. 
3. It should look something like this now:
4. ![Blender 08_01_2022 23_04_29](https://user-images.githubusercontent.com/94999291/148661492-a38178c6-9e5f-49b2-9c3f-404f283c21a0.png)

If you don't want to import from the rda directory, but from a mod folder, set the Anno Mod Folder (under Anno Scene) to your mod folder first. This allows the addon to also consider the files inside that folder.


## Editing
First a few words to the scene structure. Your imported object is called MAIN_FILE_* and all other objects are (in)direct children of it, corresponding to the tree structure of the .cfg xml. Furthermore, the main file has two special children, the IFOFILE (blocking) and the CF7FILE (animated stuff), if you imported these files. 
Each object in the scene starts with some capitalized identifier (its config type). The name does not determine the ConfigType though, it is just for clarity.
The hierarchy corresponds to the XML hierarchy and is  therefore important.

With "N", you can show/hide a properties window in the 3D View. There, select "Anno Object" to get more details on each object. 

You can:
- Reposition models, props, dummies etc to your liking. Or duplicate or delete them.
- Edit meshes. When done, keep the Model selected and go to Export->Anno Model (.rdm, .glb). You can directly safe it as .rdm. Please export it to a subfolder of the rda folder or your scenes mod folder. I suggest to use `Ctrl+A->All Transforms` before exporting.
- Edit the properties in the Anno Object Tab.
- Change material texture files - but make sure that the texture path is a subpath of either the rda folder or your current mod directory, otherwise the addon cannot convert the path to a relative /data/graphics/... path. The same goes for FileNames of other objects. If you want to add new materials, you need to duplicate existing materials imported from .cfg files and use that one. Otherwise it will lack important xml entries and will not work in the game itself.
- Add new props with the import prop functionality. For this, select the parent PropContainer first.
- Add subfiles by importing another .cfg file while the MAIN_FILE is selected and using the option "import as subfile".
- Regarding the .ifo objects: There are two types of ifo objects. Cubes and Planes. Cubes: Move them around, scale them, rotate them. Edit mode modifications do not work for these. IfoPlanes can be edited in edit mode (and object mode, if you want). This is because for planes, the individual vertex positions are important, for cubes its just about the boundaries.
- If you want to add some assets from another .cfg file, simply import both. Then you change the parent to bring them into the other file.
Tip: The .ifo and .cf7 objects might be distracting. If you shift click on the eye next to the IFOFILE or CF7FILE object in the scene tree view, you can hide them all.

## Exporting
0. If you edited models, you must export them to .rdm first. (This automatically adapts their FileName to your export location).

1. Select your MAIN_FILE object.
2. Go the Export->Anno (.cfg) and select where you want to export to. 
3. The exporter will create the .cfg (and .ifo and .cf7) file(s).

## Feedback
When you've imported a .cf7 file, you'll get a CF7FILE Object. In its properties, you basically get the whole xml document (except for the dummies). You can edit the values there. But due to blender ui scripting limitations, you cannot add or remove any nodes here. :-( But wait, cf7 is a terrible format for Feedback Definitions anyways, right? 
You might have noticed that the import/export tools allow you to change from .cf7 to SimpleAnnoFeedbackEncoding. For this feature I integrated my feedback encoding (https://github.com/xormenter/Simple-Anno-Feedback-Encoding) directly into the blender editor. It offers a very simple and much more intuitive way to define feedback sequences. But a) its less powerful and b) sadly, you must write it all yourself. So I suggest using it when you want truely custom feedback. Otherwise, if you're just repositioning dummies, stick with .cf7.
To use it:
1. Select your MAIN_FILE object. 
2. Click the Add SimpleAnnoFeedback button in the Anno Object tab.
3. Select that new object and add a DummyGroup. Give it a Name (in the anno object tab!) and click the fix name button to also rename the object in the outliner.
4. Under the DummyGroup, add Dummy Objects. They'll be named after your group. This naming scheme is sometimes important, so make sure that you keep it this way. DO NOT duplicate dummies using `Ctrl+D`. ALWAYS use the "Duplicate Dummy" button in the anno object tab to get a new dummy. 
5. Add a FeedbackConfig to the SimpleAnnoFeedbackObject. The easiest option is to select the DummyGroup first and click the button to create one from there. This will make sure it has a descriptive name. In the properties panel, you can see a feedback category where you can edit the values, add GUID Variations and Sequence Elements. (For the original guide on what they do, have a look at the original simple anno feedback github page.)
6. Either select a dummy for the DefaultStateDummy or a dummy group for StartDummyGroup and MultiplyActorByDummyCount. To select one, you might want to click on the pick something icon and then select it in the outliner (instead of in the scene). This is much easier... You select a DefaultStateDummy if you want a unit doing things in one specific order (moving around) and a group if you want a bunch of units that all do the same thing albeit in different locations (one unit will spawn on each dummy of the group and they cannot move).
8. Add a guid variation entry. For example we can choose Santa in the "Worker" category. You can add more than one, but keep in mind that not all units share the same set of animations (or do different things at the same animation), so be careful if you want something very specific.
9. Add elements to the feedback sequence list. An element can be a `Walk` (moves the unit from its current location to the target dummy), or `(Timed)IdleAnimation` (play an animation x times, resp. x milliseconds). For configs with a StartDummyGroup, only IdleAnimation elements are valid.
10. To figure out which animations you want to use, the addon can visualize your current feedback directly in blender (to some extend).There's an option to load the selected GUIDVariation as a feedback unit (purely for the visualization in blender, does not get exported) and update its animation and position to the currently selected dummy.
  - You click the button to load the model + animations (takes quite some time) of the currently selected GUIDVariation. 
  - The unit will spawn on the default state dummy. (or a random one if you're using a group)
  - Then you can click on a feedback sequence entry and update the unit. It will teleport to the dummy it will be on when this animation is played in game and display the animation of the currently selected sequence element entry. Most importantly, it throws an error when your unit does not support this animation.
12. Here's an example config that makes Santa walk between two dummies:
![Blender 08_01_2022 23_31_12](https://user-images.githubusercontent.com/94999291/148662128-756104d4-bf6d-4ce1-8b38-347f6136be44.png)
14. Here's an example of the FeedbackUnit animation preview:
![Untitled](https://user-images.githubusercontent.com/94999291/169657383-14e0fe62-ce2f-4687-bc27-554655b56b9c.jpg)

15. **Important**, when exporting the MAIN_FILE object, select the FeedbackType `SimpleAnnnoFeedbackEncoding`. It will write a .xml file, convert it to .cf7 and convert that to .fc. If you export with the cf7 option selected, it will ignore your custom feedback...

# Asset Library
## Setup 
To set up  the prop asset library, create a fresh .blend file. Click the `File->Import Anno Prop Asset` button. The addon will now load *all* prop assets located somewhere in the selected folder (which needs to be somewhere inside your rda folder). This will take a long time (go for a walk, watch a movie, sleep). After that save this .blend file in a user-library directory. The default one is `C:\Users\<USERNAME>\Documents\Blender\Assets` (but you can add more in the blender preferences). Now every prop is marked as an asset and tagged with more or less useful tags. If you want, you can further categorize the props (I suggest to at least put everything into a "Props" category). Close this file.

You might also want to have other objects in your asset browser. 
If you want f.e. to use all the models you made somewhere in all your project files, just save all your .blend files in the same user-library directory and mark the models you want as assets. I'd suggest to add a duplicate of them that has no parent object as asset (to avoid confusion). So you can just extract all kinds of nice parts from the vanilla models, save them in your asset library and then use them whereever you want. 

If you have **Blender 3.2+**, the asset browser supports collections. This allows the addon to automatically import .cfg files into your asset library. Use the "Import All Cfgs" operator found next to the corresponding operator for props to import them and also safe this file in your user-library directory.
Note that when you drag a .cfg asset into your scene, it will be an *instanced collection*, i.e. looking great but totally useless for modding purposes.
There are two options to make them useful:
- You convert it into a FILE object using `Instanced Collection To FILE_` in the anno object tab. It will be an empty that behaves like a file object, so you can parent it to a main file. You can however not edit it, nor can you load its animations.
- You make the instanced collection *real*. You can either use `Object->Apply->Make Instances Real` (with the keep hierarchy setting active) or just use the button `Make Collection Instance Real`, located in the Anno Object tab. After that, you'll get a `File` object that you can parent to some other main file or edit.

## Usage
Now you can use this library in other .blend files. For this, open the asset browser and select the user library you used. Drag and drop the assets into your scene. **Important: You'll need to set the parent (propcontainer) for each prop you add, otherwise your props won't know where they belong and won't be exported!** If you add a lot of props, you might find it more convenient to first place all of them where you want, then hide the main object and all children (shift click on visibility), select all newly added props, and parent all of them to the propcontainer at the same time.

# Island Import/Export
*Enable the ANT landscape addon for this functionality.*
This is not a full island editor and requires in depth knowledge about how island files work. 
It supports importing/exporting the gamedata.xml and rd3d.xml file of an island and represents parts of these files as 3d objects:
- The `PropGrid` from rd3d.xml. These props do not have parents. You can move, duplicate or delete them. Also supports adding new props from the asset browser, just drag them in the scene (for them Flag=1 corresponds to AdaptTerrainHeight=True).
- The `CoarseHeightmap` from the rd3d.xml. No export. Note that the scaling along the z-axis might not be 100% correct, as I'm not sure how to calculate it properly. But it looks fine, I think. 
- Objects inside `./GameSessionManager/AreaManagerData/None/Data/Content/AreaObjectManager/GameObject/objects`. 
Tip: With `Shift+G`, you can select the parent of an object. You'll find it useful.

For the gamedata.xml, you'll need to have the assets.xml extracted in your rda folder (because they use GUIDs there...). 
And be warned, importing it can take some time (and blender will freeze during this). If you want to see progress updates, open the system console before importing.
To export, select either the ISLAND_FILE (for rd3d.xml) or the ISLAND_GAMEDATA_FILE (for gamedata.xml) and click export. 


# Troubleshooting
The anno files are complicated and things can go wrong, here's how to figure out what's wrong.

When the imported file does not look like you expected, have a look at the console `Window->Toggle System Console` and scroll through. If the tool wasn't able to locate textures or models or if the conversion from rdm to glb using rdm4 failed, you'll see these things here.

If you get an parsing error that means that something is wrong with one of the imported .cfg/.cf7/.ifo files and this caused the xml parser to fail. 

If you are unsure if the export worked properly, try importing your exported file. If it doesn't look identical, something went wrong. Make sure that the object parent hierarchy is valid, if some objects do not show up in your imported file.

For materials, its important to not have any standard blender materials on your models, otherwise the export will fail. You'll need to use an imported material - only those have the specific custom properties and correctly named shader nodes. Speaking of shader nodes, please note that Cloth materials and Model materials are incompatible. 

There are quite a few weird reason for your model or parts of it becoming invisible in game. Most likely, it's related to something being wrong with the materials. Missing textures (keep in mind that anno needs a `.dds` version of your `.png`file. Also, make sure that your material has the correct vertex format (same as your model, almost always `P4h_N4b_G4b_B4b_T2h`)! Some models (those with animations) have a different vertex format than others. 
Animated models in general are quite tricky and can also cause issues with visibility. If you have animated models in your cfg that you want to use and edit (as a static object), remove all animation entries from the model. Furthermore, go through all Tracks in the AnimatedSequences section and remove all of them that reference this model with the BlenderModelID property. Note that if you want to use edited animated models, that's much more effort and is not directly supported by this tool. I refer you to the rdm4 documentation. 
