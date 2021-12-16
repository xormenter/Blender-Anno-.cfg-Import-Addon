# Blender-Anno-.cfg-Import/Export-Addon
Allows you to import from Anno (1800) .cfg files, make changes and export it to .cfg again.
Automatically positions all models, props, particles, decals, subfiles, ifo-blockers, and cf7 blockers in the scene.
When used with the rdm4 converter and texconv, it will automatically convert .rdm to .glb and .dds to .png for importing. Same goes for .fc files and the AnnoFCConverter.
Also capable of importing/exporting corresponding .ifo and .cf7 (converted from .fc) files.

# Requirements
Blender (tested with 2.93)
To use the automatic .rdm -> .glb and .dds -> .png conversion (optional), you need:
- rdm4 converter https://github.com/lukts30/rdm4
- texconv.exe https://github.com/microsoft/DirectXTex
- .fc Converter https://github.com/taubenangriff/AnnoFCConverter


# Installation
1. Put the python file into your blender addon directory (for example `C:\Program Files\Blender Foundation\Blender X.YZ\X.YZ\scripts\addons`).
2. Open blender, go to Edit->Preferences->Addons and enable the Annocfg addon.
3. If you haven't done so already, unpack the rda files (at least the data/graphics part of it) into a single folder. It should look something like this: `...rda\data\graphics\...`. 
4. In the addon preferences, set the rda path to the folder that contains your `data\graphics` folder with the unpacked rda files.
5. If you have the rdm4 converter and or texconv specify the paths to their executable. 

# Usage
## Importing 
1. With the addon enabled, go to Blender->Import->Anno (.cfg). Select the .cfg file that you want to import into blender. You'll want the boxes for .ifo and .cf7 checked for full functionality.
2. This may take some time. Tip: Use solid viewport shading during the import - generating the material shaders takes up the most time. Other tip: The import process currently creates a decent amount of garbage. In the outliner, under orphan data, click the purge button a few times.
3. It should look something like this now:
![Screenshot 2021-11-27 171306](https://user-images.githubusercontent.com/94999291/143691392-3ac47ca7-673e-40e2-9d08-faadb156af99.png)
4. Do not delete/move/edit the .cfg and .cf7 files that you imported from. The addon remembers where you imported from and needs the original file to export it again.


## Editing
First a few words to the scene structure. Your imported object is called MAIN_FILE_* and all other objects are (in)direct children of it, corresponding to the tree structure of the .cfg xml. Furthermore, the main file has two special children, the IFOFILE (blocking) and the CF7FILE (animated stuff), if you imported these files. 
Each object in the scene starts with some capitalized identifier (its config type). Generally speaking: Do not change their names, the name is used to map them back to existing objects in the .cfg file. When adding new objects to the scene, make sure that their names don't collide with existing objects. I'd also strongly advise you to only import one single .cfg file into a .blend file at once.
You can:
- Move everything (not sure if PropContainers support Transforms though, so keep them at 0,0,0). 
- Duplicate almost everything - EXCEPT for some ifo objects and ALL CF7DUMMYs. Currently if you want more people etc, you need to add them in the .cf7 file first.
- Delete objects.
- Edit values under "Object Properties->Custom Properties". For example, each model like object stores its file path there. Particles and materials have a lot of options here. Note that all properties are stored as strings!
![Screenshot 2021-11-27 172302t](https://user-images.githubusercontent.com/94999291/143703985-a10dc468-b76c-48ee-b4e1-b5cd299f6031.jpg)
- Import new props (.prp) files using the import menu. For this, first select the prop container you want the prop to be in.
- Add new models. This is a bit more involved: Add your object to the scene. Name it MODEL_whatever and make it a child of the MAIN_FILE object. Go to the custom properties, and add the FileName property (and insert the path to the .rdm as you would in a .cfg). You can also use imported models, edit them in edit mode, export them (and convert with the rdm4 converter). Then don't forget to change the FileName custom property!
- Change materials: You can also change the textures of an material directly in blender. For this, go to the shading tab and locate the texture nodes. Change the textures to whatever you want them to be (important: The files need to be somewhere inside the folder that contains your unpacked .rda and should have the same internal file path as the .dds you want to reference). Even more importantly, the texture file name needs to indicate if its a diff, norm, metal or height texture, so please name them e.g. "whatever_diff_0.png". Do not make changes to the shader graph, as the addon only looks up the used texture names without analysing the shader. If you want to tweak the material, you also have acces to the materials custom properties if you know what to do with them.
- Regarding the .ifo objects: There are three types of ifo objects. Cubes, planes and empties. Cubes: Move them around, scale them, rotate them. Planes: Do not scale them. Enter into edit mode and manually position the vertices. Empties: They just store data (Sequences) in their custom properties.
Tip: The .ifo and .cf7 objects might be distracting. If you shift click on the eye next to the IFOFILE or CF7FILE object, you can hide them all.

## Exporting
1. Select your MAIN_FILE object.
2. Go the Export->Anno (.cfg) and select where you want to export to. 
3. The exporter will create the .cfg (and .ifo and .cf7) file(s).
