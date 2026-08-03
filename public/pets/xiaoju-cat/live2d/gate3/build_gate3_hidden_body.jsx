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
    function ellipse(cx, cy, rx, ry, steps) {
        var p = [];
        for (var i = 0; i < steps; i++) {
            var a = Math.PI * 2 * i / steps;
            p.push([UnitValue(cx + Math.cos(a) * rx, "px"), UnitValue(cy + Math.sin(a) * ry, "px")]);
        }
        return p;
    }
    function polygon(points) {
        var region = [];
        for (var i = 0; i < points.length; i++) region.push([UnitValue(points[i][0], "px"), UnitValue(points[i][1], "px")]);
        return region;
    }
    function cut(source, parent, name, region, dx, dy, sx, sy, feather) {
        var layer = source.duplicate();
        layer.allLocked = false;
        layer.name = name;
        layer.move(parent, ElementPlacement.INSIDE);
        doc.activeLayer = layer;
        doc.selection.select(region, SelectionType.REPLACE, 0, false);
        if (feather && feather > 0) doc.selection.feather(UnitValue(feather, "px"));
        doc.selection.invert();
        doc.selection.clear();
        doc.selection.deselect();
        if (sx !== 100 || sy !== 100) layer.resize(sx, sy, AnchorPosition.MIDDLECENTER);
        if (dx !== 0 || dy !== 0) layer.translate(UnitValue(dx, "px"), UnitValue(dy, "px"));
        return layer;
    }
    function removeLayer(parent, name) {
        var layer = findRecursive(parent, name);
        if (layer) { layer.allLocked = false; layer.remove(); }
    }

    var master = findRecursive(doc, "GATE3_RIG_PARTS");
    var body = master ? findRecursive(master, "02_BODY_REAR") : null;
    var cat = findRecursive(doc, "SRC_Cat_Body_Base");
    var pawL = master ? findRecursive(master, "Paw_L") : null;
    var pawR = master ? findRecursive(master, "Paw_R") : null;
    if (!master || !body || !cat || !pawL || !pawR) return;

    var names = ["Belly_Fill", "Neck_Fill", "Hip_L", "Hip_R", "HindLeg_L", "HindLeg_R", "HindPaw_L", "HindPaw_R"];
    for (var n = 0; n < names.length; n++) {
        removeLayer(body, names[n]);
        removeLayer(body, "TODO_HIDDEN_" + names[n]);
    }

    // These are reconstruction plates, not visible-pose replacements. Generous
    // feathering and overlap keep rotation-deformer movement from exposing hard
    // cut edges; the planet hides their rest-pose seams.
    cut(cat, body, "Belly_Fill", polygon([[340,560],[790,500],[890,820],[760,1135],[390,1145],[280,850]]), 72, 82, 104, 110, 34);
    cut(cat, body, "Neck_Fill", polygon([[430,390],[980,340],[1040,720],[820,900],[430,800]]), 10, 44, 101, 106, 28);
    cut(cat, body, "Hip_L", ellipse(390, 860, 235, 270, 48), 125, 105, 101, 104, 42);
    cut(cat, body, "Hip_R", ellipse(520, 850, 230, 260, 48), 230, 100, 94, 104, 42);
    cut(cat, body, "HindLeg_L", polygon([[255,720],[540,690],[620,1010],[500,1148],[250,1110],[160,900]]), 165, 105, 88, 106, 32);
    cut(cat, body, "HindLeg_R", polygon([[300,700],[610,680],[720,1030],[600,1148],[320,1120],[230,890]]), 275, 92, 84, 106, 32);
    cut(pawL, body, "HindPaw_L", polygon([[500,315],[740,315],[745,540],[500,550]]), 52, 610, 92, 86, 18);
    cut(pawR, body, "HindPaw_R", polygon([[805,315],[1060,315],[1070,535],[800,545]]), -4, 602, 92, 86, 18);

    doc.activeLayer = master;
    doc.save();
}());
