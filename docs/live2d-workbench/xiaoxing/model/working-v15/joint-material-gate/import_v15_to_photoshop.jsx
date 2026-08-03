#target photoshop

app.bringToFront();
app.displayDialogs = DialogModes.NO;

var root = new Folder(File($.fileName).parent.parent.parent.parent);
var manifestFile = new File(File($.fileName).parent + "/material-manifest.json");
var outputFile = new File(root + "/model/xiaoxing-material-master-v15.psd");

function readJson(file) {
    file.encoding = "UTF8";
    if (!file.open("r")) {
        throw new Error("无法打开材料清单：" + file.fsName);
    }
    var text = file.read();
    file.close();
    return eval("(" + text + ")");
}

function importPng(target, file, layerName, visible, group) {
    if (!file.exists) {
        throw new Error("材料不存在：" + file.fsName);
    }
    var source = app.open(file);
    source.activeLayer.duplicate(target, ElementPlacement.PLACEATBEGINNING);
    source.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = target;
    var layer = target.activeLayer;
    layer.name = layerName;
    layer.visible = visible;
    if (group) {
        layer.move(group, ElementPlacement.INSIDE);
    }
    return layer;
}

var manifest = readJson(manifestFile);
var document = app.documents.add(
    512,
    1086,
    72,
    "小星_材料母版_v15",
    NewDocumentMode.RGB,
    DocumentFill.TRANSPARENT,
    1,
    BitsPerChannelType.EIGHT
);
var initialBlankLayer = document.activeLayer;

for (var i = 0; i < manifest.drawOrder.length; i++) {
    var item = manifest.drawOrder[i];
    var number = ("000" + item.index).slice(-3);
    importPng(
        document,
        new File(root + "/" + item.path),
        number + "_" + item.name,
        true,
        null
    );
}
initialBlankLayer.remove();

var eyeMaterials = document.layerSets.add();
eyeMaterials.name = "眼睛_建模隐藏材料";
eyeMaterials.visible = false;
for (var j = 0; j < manifest.alternateHiddenMaterials.length; j++) {
    var relative = manifest.alternateHiddenMaterials[j];
    var basename = decodeURI(relative.substring(relative.lastIndexOf("/") + 1));
    importPng(
        document,
        new File(root + "/" + relative),
        "隐藏_" + basename.replace(/\.png$/i, ""),
        false,
        eyeMaterials
    );
}
eyeMaterials.visible = false;

app.preferences.maximizeCompatibility = QueryStateType.ALWAYS;
var options = new PhotoshopSaveOptions();
options.layers = true;
options.embedColorProfile = true;
options.maximizeCompatibility = true;
document.saveAs(outputFile, options, true, Extension.LOWERCASE);

var logFile = new File(File($.fileName).parent + "/photoshop-import-result.txt");
logFile.encoding = "UTF8";
logFile.open("w");
logFile.writeln("PSD=" + outputFile.fsName);
logFile.writeln("defaultLayers=" + manifest.drawOrder.length);
logFile.writeln("hiddenEyeMaterials=" + manifest.alternateHiddenMaterials.length);
logFile.writeln("canvas=512x1086");
logFile.writeln("status=saved");
logFile.close();
