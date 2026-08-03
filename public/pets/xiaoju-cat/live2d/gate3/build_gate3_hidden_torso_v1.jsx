#target photoshop

// Gate 3 hidden-anatomy candidate, region 1 only.
// The generated full-body plate is never used as a replacement image. Only
// neck/chest/belly pixels are admitted beneath the original rig layers.

(function () {
    function writeStatus(message) {
        var status = File("D:/CodeWorkspace/电脑桌宠/public/pets/xiaoju-cat/live2d/gate3/gate3-hidden-torso-v1-status.txt");
        status.open("w");
        status.writeln(message);
        status.close();
    }

    if (!app.documents.length) return;
    var doc = app.activeDocument;
    if (doc.name !== "xiaoju-planet-login-gate3-working.psd") {
        writeStatus("WRONG_DOCUMENT=" + doc.name);
        return;
    }
    app.displayDialogs = DialogModes.NO;
    writeStatus("START");

    function findRecursive(container, name) {
        for (var i = 0; i < container.layers.length; i++) {
            var layer = container.layers[i];
            if (layer.name === name) return layer;
            if (layer.typename === "LayerSet") {
                var found = findRecursive(layer, name);
                if (found) return found;
            }
        }
        return null;
    }

    function removeNamed(container, name) {
        var layer = findRecursive(container, name);
        if (layer) {
            try { layer.allLocked = false; } catch (ignored) {}
            layer.remove();
        }
    }

    function selectPolygon(points, feather) {
        var region = [];
        for (var i = 0; i < points.length; i++) {
            region.push([UnitValue(points[i][0], "px"), UnitValue(points[i][1], "px")]);
        }
        doc.selection.select(region, SelectionType.REPLACE, feather || 0, true);
    }

    function moveToBack(layer, parent) {
        if (parent.layers.length > 1) {
            layer.move(parent.layers[parent.layers.length - 1], ElementPlacement.PLACEAFTER);
        }
    }

    function sliceFrom(source, parent, name, points) {
        var layer = source.duplicate();
        layer.name = name;
        layer.move(parent, ElementPlacement.INSIDE);
        doc.activeLayer = layer;
        selectPolygon(points, 5);
        doc.selection.invert();
        doc.selection.clear();
        doc.selection.deselect();
        moveToBack(layer, parent);
        layer.visible = true;
        return layer;
    }

    var master = findRecursive(doc, "GATE3_RIG_PARTS");
    var body = master && findRecursive(master, "02_BODY_REAR");
    if (!master || !body) {
        writeStatus("MISSING_MASTER_OR_BODY");
        return;
    }

    removeNamed(body, "Neck_Fill_v1_CANDIDATE");
    removeNamed(body, "Belly_Fill_v1_CANDIDATE");
    removeNamed(doc, "_HIDDEN_TORSO_SOURCE_v1");
    // Remove the unnamed top-level duplicate left by the first import probe.
    removeNamed(doc, "图层 2");

    var file = File("D:/CodeWorkspace/电脑桌宠/public/pets/xiaoju-cat/live2d/gate3/candidates/hidden-anatomy-fullbody-v1-alpha-ec1.png");
    if (!file.exists) {
        writeStatus("MISSING_CANDIDATE=" + file.fsName);
        return;
    }

    var candidateDoc = app.open(file);
    candidateDoc.activeLayer.name = "_HIDDEN_TORSO_SOURCE_v1";
    candidateDoc.activeLayer.duplicate(doc);
    candidateDoc.close(SaveOptions.DONOTSAVECHANGES);
    app.activeDocument = doc;
    var imported = findRecursive(doc, "_HIDDEN_TORSO_SOURCE_v1");
    if (!imported) {
        writeStatus("IMPORT_NOT_FOUND");
        return;
    }
    imported.translate(UnitValue(-20, "px"), UnitValue(140, "px"));

    // The top boundaries stay beneath the original jaw/neck pixels. The right
    // boundary stops before the generated foreground legs, preventing a second
    // forelimb set from entering the Live2D material.
    sliceFrom(imported, body, "Neck_Fill_v1_CANDIDATE", [
        [405, 575], [780, 560], [900, 690], [865, 910],
        [690, 1010], [405, 1000], [345, 790]
    ]);
    sliceFrom(imported, body, "Belly_Fill_v1_CANDIDATE", [
        [385, 760], [720, 700], [865, 870], [840, 1148],
        [360, 1148], [310, 955]
    ]);

    // Keep the uncut source hidden for audit/rework; only the two masked slices
    // are allowed to render in the rig group.
    imported.visible = false;
    removeNamed(body, "TODO_HIDDEN_Neck_Fill");
    removeNamed(body, "TODO_HIDDEN_Belly_Fill");

    doc.activeLayer = master;
    doc.save();
    writeStatus("OK");
}());
