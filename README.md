# Blender-Anno-.cfg-Import/Export-Addon
Allows you to import from Anno (1800) .cfg files, make changes and export it to .cfg again.
Automatically positions all models, props, particles, decals, subfiles, ifo-blockers, and cf7 blockers in the scene.
When used with the rdm4 converter and texconv, it will automatically convert .rdm to .glb and .dds to .png for importing. Same goes for .fc files and the AnnoFCConverter. It also has a export to .rda option for models.
This means that if you have all those tools, you don't have to convert anything manually and can edit everything directly in Blender.

# Requirements
- Blender **3** https://www.blender.org/

**If not using v.3.2+, you'll need to update the gltf importer addon manually!** (A required fix for a bug will only come with the blender 3.2 installer.) For this, download the *repository* from https://github.com/KhronosGroup/glTF-Blender-IO and overwrite the `io_scene_gltf_2`addon folder in your blender installation with the `io_scene_gltf_2`folder found inside the `addons` folder of the downloaded repository. DO NOT download the most recent release of glTF-Blender-IO. The bugfix isn't released yet!

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
- Regarding the .ifo objects: There are two types of ifo objects. Cubes and Planes. Cubes: Move them around, scale them, rotate them. Planes: Do not scale them! Enter into edit mode and manually position the vertices.
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
2. Then press `Shift-A`->Mesh->Add Anno Feedback Object. Select the type SimpleAnnoFeedbackObject. 
3. Select that new object and add a DummyGroup. Give it a Name (in the property panel!)
4. Under the DummyGroup, add Dummy Objects. (give it a name!) Note that if you duplicate a dummy/dummy group, the name in the property window will also be duplicated. You must change it to be unique!
5. Add a FeedbackConfig to the SimpleAnnoFeedbackObject. In the properties panel, you can see a feedback category where you can edit the values, add GUID Variations and Sequence Elements. For a guid on what they do, have a look at the original simple anno feedback github page.
6. Here's an example config that makes Santa walk between two dummies:
![Blender 08_01_2022 23_31_12](https://user-images.githubusercontent.com/94999291/148662128-756104d4-bf6d-4ce1-8b38-347f6136be44.png)

7. Finally, when exporting the MAIN_FILE object, select the FeedbackType SimpleAnnnoFeedbackEncoding. It will write a .xml file, convert it to .cf7 and convert that to .fc. 

Advanced: If you want the same kind of feedback unit on multiple locations doing the same thing, you can select a DummyGroup as StartDummyGroup (and MultiplyActorByDummyCount). This requires all dummies in the group to be named in the following fashion: groupname_0, groupname_1, and so on. Then add a IdleAnimation sequence element. 

### Which animation sequence fits?
Thankfully, Taludas went through the effort of recording all animations for all worker units. Have a look:
- Old World Workers: https://www.youtube.com/watch?v=dhI8R6WP7-E
- New World Workers: https://www.youtube.com/watch?v=7noO6grwhts

# Asset Library
## Setup 
To set up  the prop asset library, create a fresh .blend file. Click the `File->Import Anno Prop Asset` button. The addon will now load *all* prop assets located somewhere in the selected folder (which needs to be somewhere inside your rda folder). This will take a long time (go for a walk, watch a movie, sleep). After that save this .blend file in a user-library directory. The default one is `C:\Users\<USERNAME>\Documents\Blender\Assets` (but you can add more in the blender preferences). Now every prop is marked as an asset and tagged with more or less useful tags. If you want, you can further categorize the props (I suggest to at least put everything into a "Props" category). Close this file.

You might also want to have other objects in your asset browser. Unfortunately, the asset browser can only handle single objects, no hierarchies (at least for now). Therefore, only Models, Props, Lights, Particles, etc. but not Files are valid objects. 
If you want f.e. to use all the models you made somewhere in all your project files, just save all your .blend files in the same user-library directory and mark the models you want as assets. I'd suggest to add a duplicate of them that has no parent object as asset (to avoid confusion). So you can just extract all kinds of nice parts from the vanilla models, save them in your asset library and then use them whereever you want. 

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

There are quite a few weird reason for your model or parts of it becoming invisible in game. Most likely, it's related to something being wrong with the materials. Make sure that your material has the correct vertex format (same as your model rdm file)! Some models (those with animations) have a different vertex format than others. Animated models in general are quite tricky and not really supported by this tool - you'll have manually edit the files.
