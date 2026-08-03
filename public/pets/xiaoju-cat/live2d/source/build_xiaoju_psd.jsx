#target photoshop

app.displayDialogs = DialogModes.NO;

var root = new File($.fileName).parent;
var layerDir = new Folder(root.fsName + "/layers");
var output = new File(root.fsName + "/xiaoju-login-live2d-source.psd");
if (output.exists) {
  output.remove();
}
var orderedLayers = [
  "00_Body_Base.png",
  "10_Eye_L_Base.png",
  "11_Eye_R_Base.png",
  "20_Pupil_L.png",
  "21_Pupil_R.png",
  "30_Eyelid_L.png",
  "31_Eyelid_R.png",
  "40_Arm_L_Cover.png",
  "41_Arm_R_Cover.png"
];

for (var openIndex = app.documents.length - 1; openIndex >= 0; openIndex -= 1) {
  var openName = app.documents[openIndex].name;
  if (openName.indexOf("xiaoju-login-live2d-source") === 0 || orderedLayers.indexOf(openName) >= 0) {
    app.documents[openIndex].close(SaveOptions.DONOTSAVECHANGES);
  }
}

var logFile = new File(root.fsName + "/build_xiaoju_psd.log");
if (logFile.exists) {
  logFile.remove();
}

var document = app.documents.add(
  555,
  775,
  72,
  "xiaoju-login-live2d-source",
  NewDocumentMode.RGB,
  DocumentFill.TRANSPARENT
);

try {
  for (var i = 0; i < orderedLayers.length; i += 1) {
    var source = app.open(new File(layerDir.fsName + "/" + orderedLayers[i]));
    var importedLayer = source.activeLayer.duplicate(document, ElementPlacement.PLACEATBEGINNING);
    source.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = document;
    importedLayer.name = orderedLayers[i].replace(/^\d+_/, "").replace(/\.png$/, "");
  }
} catch (error) {
  logFile.open("w");
  logFile.write("Layer: " + orderedLayers[i] + "\n" + error.toString() + "\nLine: " + error.line);
  logFile.close();
  throw error;
}

var options = new PhotoshopSaveOptions();
options.layers = true;
options.embedColorProfile = true;
document.saveAs(output, options, false, Extension.LOWERCASE);
document.close(SaveOptions.SAVECHANGES);
