#target photoshop

(function () {
    if (!app.documents.length) return;
    var doc = app.activeDocument;
    if (doc.name !== "xiaoju-planet-login-gate3-working.psd") return;
    app.displayDialogs = DialogModes.NO;

    var outDir = Folder("D:/CodeWorkspace/电脑桌宠/public/pets/xiaoju-cat/live2d/gate3/qa");
    if (!outDir.exists) outDir.create();

    function writeLayers(container, depth, file) {
        for (var i = 0; i < container.layers.length; i++) {
            var layer = container.layers[i];
            var indent = "";
            for (var j = 0; j < depth; j++) indent += "  ";
            file.writeln(indent + (layer.visible ? "[V] " : "[ ] ") + layer.name + " | " + layer.typename);
            if (layer.typename === "LayerSet") writeLayers(layer, depth + 1, file);
        }
    }

    var inventory = File(outDir.fsName + "/gate3-layer-inventory.txt");
    inventory.open("w");
    inventory.writeln("document=" + doc.name);
    inventory.writeln("width=" + doc.width.as("px"));
    inventory.writeln("height=" + doc.height.as("px"));
    writeLayers(doc, 0, inventory);
    inventory.close();

    var qaDoc = doc.duplicate("gate3-qa-composite", true);
    qaDoc.flatten();
    var png = File(outDir.fsName + "/gate3-composite.png");
    var options = new PNGSaveOptions();
    options.compression = 6;
    options.interlaced = false;
    qaDoc.saveAs(png, options, true, Extension.LOWERCASE);
    qaDoc.close(SaveOptions.DONOTSAVECHANGES);

    function hideByPrefix(container, prefix) {
        for (var i = 0; i < container.layers.length; i++) {
            var layer = container.layers[i];
            if (layer.name.indexOf(prefix) === 0) layer.visible = false;
            if (layer.typename === "LayerSet") hideByPrefix(layer, prefix);
        }
    }

    function findNamed(container, name) {
        for (var i = 0; i < container.layers.length; i++) {
            var layer = container.layers[i];
            if (layer.name === name) return layer;
            if (layer.typename === "LayerSet") {
                var found = findNamed(layer, name);
                if (found) return found;
            }
        }
        return null;
    }

    function isolateRigMaster(targetDoc) {
        for (var i = 0; i < targetDoc.layers.length; i++) {
            targetDoc.layers[i].visible = targetDoc.layers[i].name === "GATE3_RIG_PARTS";
        }
        var master = findNamed(targetDoc, "GATE3_RIG_PARTS");
        if (master) master.visible = true;
    }

    var gazeDoc = doc.duplicate("gate3-qa-eye-base", false);
    hideByPrefix(gazeDoc, "Pupil_");
    hideByPrefix(gazeDoc, "Highlight_");
    gazeDoc.flatten();
    var gazePng = File(outDir.fsName + "/gate3-eye-base-no-pupil.png");
    gazeDoc.saveAs(gazePng, options, true, Extension.LOWERCASE);
    gazeDoc.close(SaveOptions.DONOTSAVECHANGES);

    // Prove that the importable rig layers can reproduce the approved rest
    // composition without depending on any locked SRC_* safety layers.
    var rigDoc = doc.duplicate("gate3-qa-rig-parts-only", false);
    isolateRigMaster(rigDoc);
    rigDoc.flatten();
    var rigPng = File(outDir.fsName + "/gate3-rig-parts-only.png");
    rigDoc.saveAs(rigPng, options, true, Extension.LOWERCASE);
    rigDoc.close(SaveOptions.DONOTSAVECHANGES);

    // Uncover the cat using only rig-owned layers. Removing source layers,
    // planet layers, the foreground occluder and forelimbs prevents an intact
    // source image from hiding missing anatomy or disconnected reconstruction.
    var hiddenDoc = doc.duplicate("gate3-qa-hidden-body", false);
    isolateRigMaster(hiddenDoc);
    var hiddenForeground = findNamed(hiddenDoc, "06_FOREGROUND_OVERLAY");
    if (hiddenForeground) hiddenForeground.visible = false;
    // BG_Stars is an opaque composition plate and already contains the planet,
    // so hiding only Planet_Base would still conceal missing cat pixels.
    var hiddenScene = findNamed(hiddenDoc, "01_SCENE_PLANET");
    if (hiddenScene) hiddenScene.visible = false;
    var hiddenArms = findNamed(hiddenDoc, "05_FORELIMBS_JOINTED");
    if (hiddenArms) hiddenArms.visible = false;
    var hiddenPng = File(outDir.fsName + "/gate3-hidden-body-uncovered.png");
    hiddenDoc.saveAs(hiddenPng, options, true, Extension.LOWERCASE);
    hiddenDoc.close(SaveOptions.DONOTSAVECHANGES);
}());
