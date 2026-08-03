#target photoshop

app.displayDialogs = DialogModes.NO;

var gate = File($.fileName).parent;
var root = new Folder(gate.parent.parent.parent);
var psd = new File(root + "/model/xiaoxing-material-master-v15.psd");
var preview = new File(gate + "/psd-default-preview.png");
var report = new File(gate + "/psd-layer-validation.txt");

var document = null;
var openedForValidation = false;
for (var openIndex = 0; openIndex < app.documents.length; openIndex++) {
    try {
        if (app.documents[openIndex].fullName.fsName == psd.fsName) {
            document = app.documents[openIndex];
            break;
        }
    } catch (ignored) {}
}
if (document === null) {
    document = app.open(psd);
    openedForValidation = true;
}
app.activeDocument = document;
var defaults = [];
var hidden = [];

for (var i = 0; i < document.layers.length; i++) {
    var item = document.layers[i];
    if (item.typename == "ArtLayer") {
        defaults.push(item.name + "|visible=" + item.visible);
    } else if (item.typename == "LayerSet" && item.name == "眼睛_建模隐藏材料") {
        for (var j = 0; j < item.artLayers.length; j++) {
            hidden.push(item.artLayers[j].name + "|visible=" + item.artLayers[j].visible);
        }
    }
}

var options = new ExportOptionsSaveForWeb();
options.format = SaveDocumentType.PNG;
options.PNG8 = false;
options.transparency = true;
options.interlaced = false;
document.exportDocument(preview, ExportType.SAVEFORWEB, options);

report.encoding = "UTF8";
report.open("w");
report.writeln("canvas=" + document.width.as("px") + "x" + document.height.as("px"));
report.writeln("topLevelDefaultLayers=" + defaults.length);
report.writeln("hiddenEyeMaterials=" + hidden.length);
report.writeln("defaultLayers:");
for (var d = 0; d < defaults.length; d++) {
    report.writeln(defaults[d]);
}
report.writeln("hiddenLayers:");
for (var h = 0; h < hidden.length; h++) {
    report.writeln(hidden[h]);
}
report.close();

if (openedForValidation) {
    document.close(SaveOptions.DONOTSAVECHANGES);
}
