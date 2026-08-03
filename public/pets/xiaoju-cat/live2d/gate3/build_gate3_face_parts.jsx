#target photoshop

(function () {
    if (!app.documents.length) return;
    var doc = app.activeDocument;
    if (doc.name !== "xiaoju-planet-login-gate3-working.psd") return;
    app.displayDialogs = DialogModes.NO;

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
    function polygon(points) {
        var region = [];
        for (var i = 0; i < points.length; i++) region.push([UnitValue(points[i][0], "px"), UnitValue(points[i][1], "px")]);
        return region;
    }
    function cut(source, parent, name, points, feather) {
        var old = findRecursive(parent, name) || findRecursive(parent, "TODO_HIDDEN_" + name);
        if (old) { old.allLocked = false; old.remove(); }
        var layer = source.duplicate();
        layer.allLocked = false;
        layer.name = name;
        layer.move(parent, ElementPlacement.INSIDE);
        doc.activeLayer = layer;
        doc.selection.select(polygon(points), SelectionType.REPLACE, 0, false);
        if (feather) doc.selection.feather(UnitValue(feather, "px"));
        doc.selection.invert();
        doc.selection.clear();
        doc.selection.deselect();
        return layer;
    }

    var master = findRecursive(doc, "GATE3_RIG_PARTS");
    var head = master && findRecursive(master, "03_HEAD_FACE_EARS");
    var eyes = master && findRecursive(master, "04_EYES_GAZE");
    var body = findRecursive(doc, "SRC_Cat_Body_Base");
    var eyeL = findRecursive(doc, "SRC_Eye_L_Whole");
    var eyeR = findRecursive(doc, "SRC_Eye_R_Whole");
    if (!head || !eyes || !body || !eyeL || !eyeR) return;

    // Visible facial material is separated without repainting it. Adjacent
    // plates overlap so blink, muzzle and whisker motion remain crack-free.
    cut(body, head, "Nose", [[800,545],[890,540],[920,610],[855,650],[790,610]], 3);
    cut(body, head, "Mouth_Line", [[735,610],[960,600],[995,715],[845,760],[705,700]], 4);
    cut(body, head, "Mouth_Inside", [[770,650],[940,645],[960,720],[845,746],[750,705]], 2);
    cut(body, head, "Chin_Fur", [[675,665],[1010,650],[1040,790],[835,840],[650,760]], 10);
    cut(body, head, "Whisker_L", [[420,535],[830,535],[850,735],[420,760]], 2);
    cut(body, head, "Whisker_R", [[835,500],[1185,465],[1200,700],[830,735]], 2);

    cut(body, eyes, "EyeSocket_Fur_L", [[610,445],[790,430],[815,630],[690,670],[585,585]], 8);
    cut(body, eyes, "EyeSocket_Fur_R", [[830,380],[1015,365],[1070,555],[955,615],[815,540]], 8);
    cut(eyeL, eyes, "LowerLid_L", [[640,545],[780,535],[790,610],[705,635],[625,600]], 3);
    cut(eyeR, eyes, "LowerLid_R", [[865,480],[1000,465],[1020,540],[935,570],[850,535]], 3);

    doc.activeLayer = master;
    doc.save();
}());
