#target photoshop

app.displayDialogs = DialogModes.NO;

var root = new File($.fileName).parent;
var layerDir = new Folder(root.fsName + "/layers-v2");
var output = new File(root.fsName + "/xiaoju-planet-login-live2d-v2-source.psd");
if (output.exists) output.remove();

var orderedLayers = [
  "00_Stars_Background.png",
  "10_Cat_Body_Base.png",
  "20_Eye_L_Whole.png",
  "21_Eye_R_Whole.png",
  "40_Eyelid_L.png",
  "41_Eyelid_R.png",
  "50_Planet_Foreground.png",
  "60_Rest_Paw_L.png",
  "61_Rest_Paw_R.png",
  "70_Cover_Foreleg_L.png",
  "71_Cover_Foreleg_R.png"
];

var document = app.documents.add(1370, 1148, 72, "xiaoju-planet-login-live2d-v2-source", NewDocumentMode.RGB, DocumentFill.TRANSPARENT);
for (var i = 0; i < orderedLayers.length; i += 1) {
  var source = app.open(new File(layerDir.fsName + "/" + orderedLayers[i]));
  var importedLayer = source.activeLayer.duplicate(document, ElementPlacement.PLACEATBEGINNING);
  source.close(SaveOptions.DONOTSAVECHANGES);
  app.activeDocument = document;
  importedLayer.name = orderedLayers[i].replace(/^\d+_/, "").replace(/\.png$/, "");
}

var options = new PhotoshopSaveOptions();
options.layers = true;
options.embedColorProfile = true;
document.saveAs(output, options, false, Extension.LOWERCASE);
document.close(SaveOptions.DONOTSAVECHANGES);
