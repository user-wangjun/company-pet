#target photoshop

app.displayDialogs = DialogModes.NO;

var root = new File($.fileName).parent;
var v2 = new Folder(root.fsName + "/layers-v2");
var v3 = new Folder(root.fsName + "/layers-v3");
var output = new File(root.fsName + "/xiaoju-planet-login-live2d-v3-source.psd");
if (output.exists) output.remove();

// Bottom-to-top. Forelegs are each one continuous shoulder-to-paw layer.
// The planet and soft shoulder patches hide their open roots without adding
// any duplicate rest-paw or cover-paw artwork.
var orderedLayers = [
  [v2, "00_Stars_Background.png"],
  [v2, "10_Cat_Body_Base.png"],
  [v2, "20_Eye_L_Whole.png"],
  [v2, "21_Eye_R_Whole.png"],
  [v2, "40_Eyelid_L.png"],
  [v2, "41_Eyelid_R.png"],
  [v3, "60_Foreleg_L_Complete.png"],
  [v3, "61_Foreleg_R_Complete.png"],
  [v2, "50_Planet_Foreground.png"],
  [v3, "30_Shoulder_Occluder_L.png"],
  [v3, "31_Shoulder_Occluder_R.png"]
];

var document = app.documents.add(
  1370,
  1148,
  72,
  "xiaoju-planet-login-live2d-v3-source",
  NewDocumentMode.RGB,
  DocumentFill.TRANSPARENT
);

for (var i = 0; i < orderedLayers.length; i += 1) {
  var folder = orderedLayers[i][0];
  var filename = orderedLayers[i][1];
  var source = app.open(new File(folder.fsName + "/" + filename));
  var importedLayer = source.activeLayer.duplicate(document, ElementPlacement.PLACEATBEGINNING);
  source.close(SaveOptions.DONOTSAVECHANGES);
  app.activeDocument = document;
  importedLayer.name = filename.replace(/^\d+_/, "").replace(/\.png$/, "");
}

var options = new PhotoshopSaveOptions();
options.layers = true;
options.embedColorProfile = true;
document.saveAs(output, options, false, Extension.LOWERCASE);
document.close(SaveOptions.DONOTSAVECHANGES);
