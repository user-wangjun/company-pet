#target photoshop

app.displayDialogs = DialogModes.NO;

var scriptFile = new File($.fileName);
var packageRoot = scriptFile.parent.parent;
var inputRoot = new Folder(packageRoot.fsName + "/inputs");
var outputFile = new File(packageRoot.fsName + "/psd/xiaoxing-arm-chain-v10-import.psd");
var auditFile = new File(packageRoot.fsName + "/audit/v10-psd-integrity-report.json");

var specsBackToFront = [
    ["02_upper_arm_engineering.png", "02_upper_arm_engineering"],
    ["04_whole_hand.png", "04_whole_hand"],
    ["03_forearm_including_bracelet.png", "03_forearm_including_bracelet"],
    ["01_sleeve.png", "01_sleeve"]
];

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
    for (index = 0; index < depth; index++) {
        indent += "  ";
    }
    childIndent = indent + "  ";
    if (value === null) {
        return "null";
    }
    if (typeof value == "string") {
        return jsonQuote(value);
    }
    if (typeof value == "number" || typeof value == "boolean") {
        return String(value);
    }
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
            objectRows.push(
                childIndent + jsonQuote(key) + ": " + jsonStringify(value[key], depth + 1)
            );
        }
    }
    return objectRows.length ? "{\n" + objectRows.join(",\n") + "\n" + indent + "}" : "{}";
}

var target = app.documents.add(
    512,
    1086,
    72,
    "xiaoxing_arm_chain_v10_import",
    NewDocumentMode.RGB,
    DocumentFill.TRANSPARENT
);

for (var index = 0; index < specsBackToFront.length; index++) {
    var sourceFile = new File(inputRoot.fsName + "/" + specsBackToFront[index][0]);
    if (!sourceFile.exists) {
        throw new Error("Missing V10 input: " + specsBackToFront[index][0]);
    }
    var source = app.open(sourceFile);
    source.activeLayer.duplicate(target, ElementPlacement.PLACEATBEGINNING);
    source.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = target;
    target.activeLayer.name = specsBackToFront[index][1];
}

if (target.layers.length > specsBackToFront.length) {
    target.layers[target.layers.length - 1].remove();
}

var options = new PhotoshopSaveOptions();
options.alphaChannels = true;
options.annotations = false;
options.embedColorProfile = true;
options.layers = true;
options.maximizeCompatibility = true;
options.spotColors = false;
target.saveAs(outputFile, options, true, Extension.LOWERCASE);

var layerRows = [];
for (var layerIndex = 0; layerIndex < target.layers.length; layerIndex++) {
    var layer = target.layers[layerIndex];
    var bounds = layer.bounds;
    layerRows.push({
        name: layer.name,
        visible: layer.visible,
        boundsCanvasPx: [
            bounds[0].as("px"),
            bounds[1].as("px"),
            bounds[2].as("px"),
            bounds[3].as("px")
        ]
    });
}

var audit = {
    schemaVersion: 1,
    status: (
        target.width.as("px") == 512 &&
        target.height.as("px") == 1086 &&
        target.layers.length == 4
    ) ? "pass_psd_structure" : "fail_psd_structure",
    canvas: [target.width.as("px"), target.height.as("px")],
    resolutionPpi: target.resolution,
    colorMode: "RGB",
    bitsPerChannel: target.bitsPerChannel.toString(),
    layerCount: target.layers.length,
    layerOrderFrontToBack: layerRows,
    expectedStableLayerOrderFrontToBack: [
        "01_sleeve",
        "03_forearm_including_bracelet",
        "04_whole_hand",
        "02_upper_arm_engineering"
    ],
    integerRegistrationChanged: false,
    resampled: false,
    translated: false,
    scaled: false,
    referenceMasterIncluded: false,
    fallbackLayerIncluded: false,
    sourceInputs: [
        "inputs/01_sleeve.png",
        "inputs/02_upper_arm_engineering.png",
        "inputs/03_forearm_including_bracelet.png",
        "inputs/04_whole_hand.png"
    ],
    output: "psd/xiaoxing-arm-chain-v10-import.psd",
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
