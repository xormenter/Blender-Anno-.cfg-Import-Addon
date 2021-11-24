# Blender-Anno-.cfg-Import-Addon
Parses Anno (1800) .cfg files and automatically imports and positions all models, props, particles, subfiles and decals in the scene.
When available, the corresponding .glb file is used, otherwise a named empty serves as placeholder.
If the necessary textures can be found in .png format, they are used for the material.

# What this addon can and cannot do
- It can load .cfg files, allowing you to quickly check if you are happy with the .cfg file without going into the game itself.
- It cannot save your scene to .cfg files. 

# Installation
1. Put the python file into your blender addon directory (for example `C:\Program Files\Blender Foundation\Blender X.YZ\X.YZ\scripts\addons`).
2. Open blender, go to Edit->Preferences->Addons and enable the Annocfg addon.
3. If you haven't done so already, unpack the rda files (at least the data/graphics part of it) into a single folder. It should look something like this: `...rda\data\graphics\...`. 
4. In the addon preferences, set the rda path to the folder that contains your `data\graphics` folder with the unpacked rda files.
5. Convert all `.rda` files that you might need into `.glb` files. Convert the .dds files that you might need to `.png`.
6. You're ready. :-)

# Usage
With the addon enabled, go to Blender->Import->Anno (.cfg). Select the .cfg file that you want to import into blender. At the right side, you can choose to not load certain parts of the file (e.g. props).
Blender will take some time to load the files. 

