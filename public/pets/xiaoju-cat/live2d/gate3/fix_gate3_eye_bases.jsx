#target photoshop

(function () {
    if (!app.documents.length) return;
    var doc = app.activeDocument;
    if (doc.name !== "xiaoju-planet-login-gate3-working.psd") return;
    app.displayDialogs = DialogModes.NO;

    function findTop(name) {
        for (var i = 0; i < doc.layers.length; i++) if (doc.layers[i].name === name) return doc.layers[i];
        return null;
    }
    function findGroup(parent, name) {
        for (var i = 0; i < parent.layerSets.length; i++) if (parent.layerSets[i].name === name) return parent.layerSets[i];
        return null;
    }
    function findLayer(parent, name) {
        for (var i = 0; i < parent.layers.length; i++) if (parent.layers[i].name === name) return parent.layers[i];
        return null;
    }
    function ellipse(cx, cy, rx, ry, steps) {
        var points = [];
        for (var i = 0; i < steps; i++) {
            var a = Math.PI * 2 * i / steps;
            points.push([UnitValue(cx + Math.cos(a) * rx, "px"), UnitValue(cy + Math.sin(a) * ry, "px")]);
        }
        return points;
    }
    function buildCleanEye(source, eyes, side, cx, cy, rx, ry) {
        var oldClean = findLayer(eyes, "Iris_" + side + "_Clean");
        if (oldClean) { oldClean.allLocked = false; oldClean.remove(); }
        var todo = findLayer(eyes, "TODO_HIDDEN_Iris_" + side + "_Clean");
        if (todo) { todo.allLocked = false; todo.remove(); }

        var clean = source.duplicate();
        clean.allLocked = false;
        clean.name = "Iris_" + side + "_Clean";
        clean.move(eyes, ElementPlacement.INSIDE);
        doc.activeLayer = clean;
        doc.selection.select(ellipse(cx, cy, rx, ry, 48), SelectionType.REPLACE, 0, false);
        doc.selection.feather(UnitValue(5, "px"));
        var amber = new SolidColor();
        amber.rgb.red = 202;
        amber.rgb.green = 128;
        amber.rgb.blue = 24;
        doc.selection.fill(amber, ColorBlendMode.NORMAL, 100, false);

        var upperShade = new SolidColor();
        upperShade.rgb.red = 126;
        upperShade.rgb.green = 73;
        upperShade.rgb.blue = 20;
        doc.selection.select(ellipse(cx, cy - 13, rx - 4, ry * 0.62, 40), SelectionType.REPLACE, 0, false);
        doc.selection.feather(UnitValue(9, "px"));
        doc.selection.fill(upperShade, ColorBlendMode.NORMAL, 34, false);

        var lowerGlow = new SolidColor();
        lowerGlow.rgb.red = 232;
        lowerGlow.rgb.green = 158;
        lowerGlow.rgb.blue = 42;
        doc.selection.select(ellipse(cx, cy + 14, rx - 5, ry * 0.55, 40), SelectionType.REPLACE, 0, false);
        doc.selection.feather(UnitValue(8, "px"));
        doc.selection.fill(lowerGlow, ColorBlendMode.NORMAL, 24, false);

        doc.selection.select(ellipse(cx, cy, rx, ry, 48), SelectionType.REPLACE, 0, false);
        doc.selection.feather(UnitValue(5, "px"));
        clean.applyAddNoise(2.2, NoiseDistribution.UNIFORM, true);
        clean.applyGaussianBlur(0.45);
        doc.selection.deselect();

        var pupil = findLayer(eyes, "Pupil_" + side);
        if (pupil) clean.move(pupil, ElementPlacement.PLACEAFTER);
        var underpaint = findLayer(eyes, "Eye_" + side + "_Underpaint_LOCKED");
        if (underpaint) underpaint.visible = false;
        return clean;
    }

    var master = findTop("GATE3_RIG_PARTS");
    var eyes = master ? findGroup(master, "04_EYES_GAZE") : null;
    var eyeL = findTop("SRC_Eye_L_Whole");
    var eyeR = findTop("SRC_Eye_R_Whole");
    if (!master || !eyes || !eyeL || !eyeR) return;

    buildCleanEye(eyeL, eyes, "L", 708, 549, 34, 40);
    buildCleanEye(eyeR, eyes, "R", 929, 484, 33, 39);
    doc.activeLayer = master;
    doc.save();
}());
