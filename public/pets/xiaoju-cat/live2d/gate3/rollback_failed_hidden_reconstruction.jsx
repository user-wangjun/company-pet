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
    function remove(parent, name) {
        var layer = findRecursive(parent, name);
        if (layer) { layer.allLocked = false; layer.remove(); }
    }
    function addTodo(parent, name) {
        var existing = findRecursive(parent, "TODO_HIDDEN_" + name);
        if (existing) { existing.visible = false; return; }
        var layer = doc.artLayers.add();
        layer.name = "TODO_HIDDEN_" + name;
        layer.move(parent, ElementPlacement.INSIDE);
        layer.visible = false;
    }

    var master = findRecursive(doc, "GATE3_RIG_PARTS");
    var body = master && findRecursive(master, "02_BODY_REAR");
    var eyes = master && findRecursive(master, "04_EYES_GAZE");
    if (!master || !body || !eyes) return;

    // The automated clone/transform reconstruction failed the uncovered-body
    // QA (detached paws, repeated torso contours and visible rest-pose leakage).
    // Remove it atomically so a failed candidate can never contaminate the
    // approved cover pose.
    var hidden = ["Belly_Fill", "Neck_Fill", "Hip_L", "Hip_R", "HindLeg_L", "HindLeg_R", "HindPaw_L", "HindPaw_R"];
    for (var i = 0; i < hidden.length; i++) {
        remove(body, hidden[i]);
        addTodo(body, hidden[i]);
    }

    // These source-derived socket plates covered the iris in rest pose. Keep
    // them explicitly pending until they are repainted as true under-eye fills.
    var eyePending = ["EyeSocket_Fur_L", "EyeSocket_Fur_R", "LowerLid_L", "LowerLid_R"];
    for (var j = 0; j < eyePending.length; j++) {
        remove(eyes, eyePending[j]);
        addTodo(eyes, eyePending[j]);
    }

    doc.activeLayer = master;
    doc.save();
}());
