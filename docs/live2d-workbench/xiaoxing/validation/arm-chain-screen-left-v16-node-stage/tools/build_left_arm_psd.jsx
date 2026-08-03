#target photoshop

app.displayDialogs = DialogModes.NO;

var scriptFile = new File($.fileName);
var stage = scriptFile.parent.parent;
var workbench = stage.parent.parent;
var inputRoot = new Folder(workbench.fsName + "/validation/arm-chain-screen-left-v14-complete-textures/materials");
var outputDir = new Folder(stage.fsName + "/psd");
if (!outputDir.exists) outputDir.create();
var auditDir = new Folder(stage.fsName + "/audit");
if (!auditDir.exists) auditDir.create();
var outputFile = new File(outputDir.fsName + "/xiaoxing-arm-chain-screen-left-v16-import.psd");
var auditFile = new File(auditDir.fsName + "/v16-psd-build-report.json");

var specsBackToFront = [
    ["upper_arm.png", "02_upper_arm_screen_left"],
    ["whole_hand.png", "04_whole_hand_screen_left"],
    ["forearm_bracelet.png", "03_forearm_bracelet_screen_left"],
    ["sleeve.png", "01_sleeve_screen_left"]
];

var target = app.documents.add(
    512,
    1086,
    72,
    "xiaoxing_arm_chain_screen_left_v16_import",
    NewDocumentMode.RGB,
    DocumentFill.TRANSPARENT
);

for (var index = 0; index < specsBackToFront.length; index++) {
    var sourceFile = new File(inputRoot.fsName + "/" + specsBackToFront[index][0]);
    if (!sourceFile.exists) throw new Error("Missing V14 material: " + sourceFile.fsName);
    var source = app.open(sourceFile);
    source.activeLayer.duplicate(target, ElementPlacement.PLACEATBEGINNING);
    source.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = target;
    target.activeLayer.name = specsBackToFront[index][1];
}

while (target.layers.length > specsBackToFront.length) {
    target.layers[target.layers.length - 1].remove();
}
var stableNamesFrontToBack = [
    "01_sleeve_screen_left",
    "03_forearm_bracelet_screen_left",
    "04_whole_hand_screen_left",
    "02_upper_arm_screen_left"
];
for (var stableIndex = 0; stableIndex < stableNamesFrontToBack.length; stableIndex++) {
    target.layers[stableIndex].name = stableNamesFrontToBack[stableIndex];
}

function jsonQuote(value) {
    return '"' + String(value)
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\r/g, "\\r")
        .replace(/\n/g, "\\n")
        .replace(/\t/g, "\\t") + '"';
}

function jsonStringify(value, depth) {
    var indent = "";
    var childIndent = "";
    var index;
    for (index = 0; index < depth; index++) indent += "  ";
    childIndent = indent + "  ";
    if (value === null) return "null";
    if (typeof value == "string") return jsonQuote(value);
    if (typeof value == "number" || typeof value == "boolean") return String(value);
    if (value instanceof Array) {
        var arrayRows = [];
        for (index = 0; index < value.length; index++) {
            arrayRows.push(childIndent + jsonStringify(value[index], depth + 1));
        }
        return arrayRows.length ? "[\n" + arrayRows.join(",\n") + "\n" + indent + "]" : "[]";
    }
    var objectRows = [];
    for (var key in value) {
        if (value.hasOwnProperty(key)) {
            objectRows.push(childIndent + jsonQuote(key) + ": " + jsonStringify(value[key], depth + 1));
        }
    }
    return objectRows.length ? "{\n" + objectRows.join(",\n") + "\n" + indent + "}" : "{}";
}

var options = new PhotoshopSaveOptions();
options.alphaChannels = true;
options.annotations = false;
options.embedColorProfile = true;
options.layers = true;
options.maximizeCompatibility = true;
options.spotColors = false;
target.saveAs(outputFile, options, true, Extension.LOWERCASE);

var audit = {
    schemaVersion: 1,
    status: (
        target.width.as("px") == 512 &&
        target.height.as("px") == 1086 &&
        target.layers.length == 4
    ) ? "pass_psd_structure" : "fail_psd_structure",
    canvas: [target.width.as("px"), target.height.as("px")],
    layerCount: target.layers.length,
    layerOrderFrontToBack: [
        "01_sleeve_screen_left",
        "03_forearm_bracelet_screen_left",
        "04_whole_hand_screen_left",
        "02_upper_arm_screen_left"
    ],
    sourceInputs: [
        "validation/arm-chain-screen-left-v14-complete-textures/materials/sleeve.png",
        "validation/arm-chain-screen-left-v14-complete-textures/materials/forearm_bracelet.png",
        "validation/arm-chain-screen-left-v14-complete-textures/materials/whole_hand.png",
        "validation/arm-chain-screen-left-v14-complete-textures/materials/upper_arm.png"
    ],
    output: "validation/arm-chain-screen-left-v16-node-stage/psd/xiaoxing-arm-chain-screen-left-v16-import.psd",
    integerRegistrationChanged: false,
    resampled: false,
    translated: false,
    scaled: false,
    privacy: {
        absolutePathsWritten: false,
        sourceFilesUploaded: false,
        cloudServicesUsed: false
    }
};

auditFile.encoding = "UTF8";
auditFile.open("w");
auditFile.write(jsonStringify(audit, 0) + "\n");
auditFile.close();
target.close(SaveOptions.DONOTSAVECHANGES);
