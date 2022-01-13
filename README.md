# Blender-Anno-.cfg-Import/Export-Addon
Allows you to import from Anno (1800) .cfg files, make changes and export it to .cfg again.
Automatically positions all models, props, particles, decals, subfiles, ifo-blockers, and cf7 blockers in the scene.
When used with the rdm4 converter and texconv, it will automatically convert .rdm to .glb and .dds to .png for importing. Same goes for .fc files and the AnnoFCConverter. It also has a export to .rda option for models.
This means that if you have all those tools, you don't have to convert anything manually and can edit everything directly in Blender.

# Requirements
Blender (tested with 2.93)
To use the automati conversion, you need:
- rdm4 converter https://github.com/lukts30/rdm4
- texconv.exe https://github.com/microsoft/DirectXTex
- .fc Converter (AnnoFCConverter.exe) https://github.com/taubenangriff/AnnoFCConverter
And of course the .rda explorer to unpack the game files: https://github.com/lysannschlegel/RDAExplorer

# Installation
1. Install the other tools.
2. Open blender, go to Edit->Preferences->Addons. Click `Install...` and select the downloaded `io_annocfg.zip` (https://github.com/xormenter/Blender-Anno-.cfg-Import-Addon/releases/tag/v.2.1).
3. If you haven't done so already, unpack the .rda files (at least the data/graphics part of it) into a single folder. It should look something like this: `...rda\data\graphics\...`.  
4. In the addon preferences, set the rda path to the folder that contains your `data\graphics` folder with the unpacked rda files.
5. Specify the paths to the `texconv.exe`, `rdm4-bin.exe`, `AnnoFCConverter.exe` executables.
You are now ready to go!

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
- Edit meshes. When done, keep the Model selected and go to Export->Anno Model (.rdm, .glb). You can directly safe it as .rdm. Please export it to a subfolder of the rda folder or your scenes mod folder.
- Edit the properties in the Anno Object Tab.
- Change material texture files - but make sure that the texture path is a subpath of either the rda folder or your current mod directory, otherwise the addon cannot convert the path to a relative /data/graphics/... path. The same goes for FileNames of other objects. If you want to add new materials, you need to duplicate existing materials imported from .cfg files and use that one. Otherwise it will lack important xml entries and will not work in the game itself.
- Add new props with the import prop functionality. For this, select the parent PropContainer first.
- Add subfiles by importing another .cfg file while the MAIN_FILE is selected and using the option "import as subfile".
- Regarding the .ifo objects: There are two types of ifo objects. Cubes and Planes. Cubes: Move them around, scale them, rotate them. Planes: Do not scale them! Enter into edit mode and manually position the vertices.
- If you want to add some assets from another .cfg file, simply import both. Then you change the parent to bring them into the other file.
Tip: The .ifo and .cf7 objects might be distracting. If you shift click on the eye next to the IFOFILE or CF7FILE object in the scene tree view, you can hide them all.

## Exporting
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

